import copy
import json
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError


AWS_PROFILE_NAME = os.getenv("CLAIMS_AWS_PROFILE") or None
AWS_REGION_NAME = os.getenv("CLAIMS_AWS_REGION", "us-east-1")
AWS_BUCKET_NAME = os.getenv("CLAIMS_AWS_BUCKET", "example-claims-bucket")
CLAIMS_TABLE_NAME = os.getenv(
    "CLAIMS_AWS_CLAIMS_TABLE",
    "example-claims-assessments",
)

DOCUMENT_INGESTION_PREFIX = "claims-demo/ingestion/document-claims"
VEHICLE_INGESTION_PREFIX = "claims-demo/ingestion/vehicle-claims"

SUPPORTED_IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


@lru_cache(maxsize=1)
def get_aws_session() -> boto3.Session:
    return boto3.Session(
        profile_name=AWS_PROFILE_NAME,
        region_name=AWS_REGION_NAME,
    )


def get_aws_claim_status(claim_id: str) -> dict | None:
    normalized_claim_id = claim_id.strip().upper()

    if not normalized_claim_id:
        raise ValueError("Claim ID is required.")

    table = get_aws_session().resource("dynamodb").Table(
        CLAIMS_TABLE_NAME
    )

    response = table.get_item(
        Key={"claim_id": normalized_claim_id},
        ConsistentRead=True,
    )

    return response.get("Item")


def get_aws_claim_statuses(
    claim_ids: list[str] | tuple[str, ...],
) -> dict[str, dict]:
    normalized_claim_ids = list(
        dict.fromkeys(
            claim_id.strip().upper()
            for claim_id in claim_ids
            if claim_id and claim_id.strip()
        )
    )
    if not normalized_claim_ids:
        return {}

    dynamodb = get_aws_session().resource("dynamodb")
    statuses: dict[str, dict] = {}

    for start in range(0, len(normalized_claim_ids), 100):
        keys = [
            {"claim_id": claim_id}
            for claim_id in normalized_claim_ids[start : start + 100]
        ]
        request_items = {
            CLAIMS_TABLE_NAME: {
                "Keys": keys,
                "ConsistentRead": True,
            }
        }

        while request_items:
            response = dynamodb.batch_get_item(
                RequestItems=request_items
            )
            for item in response.get(
                "Responses",
                {},
            ).get(CLAIMS_TABLE_NAME, []):
                statuses[str(item["claim_id"])] = item

            request_items = response.get(
                "UnprocessedKeys",
                {},
            )

    return statuses


def load_s3_json(s3_uri: str) -> dict:
    parsed_uri = urlparse(s3_uri)

    if parsed_uri.scheme != "s3" or not parsed_uri.netloc:
        raise ValueError(f"Invalid S3 URI: {s3_uri}")

    response = get_aws_session().client("s3").get_object(
        Bucket=parsed_uri.netloc,
        Key=parsed_uri.path.lstrip("/"),
    )

    content = response["Body"].read().decode("utf-8")
    return json.loads(content)


def get_aws_claim_assessment(claim_id: str) -> dict | None:
    status = get_aws_claim_status(claim_id)

    if status is None:
        return None

    document_result = None
    image_result = None

    document_uri = status.get(
        "document_validation_result_s3_uri"
    )
    if document_uri:
        document_result = load_s3_json(document_uri)

    image_uri = status.get(
        "image_validation_result_s3_uri"
    )
    if image_uri:
        image_result = load_s3_json(image_uri)

    return {
        "summary": status,
        "document_result": document_result,
        "image_result": image_result,
    }


def get_aws_claim_record(claim_id: str) -> dict | None:
    normalized_claim_id = claim_id.strip().upper()
    if not normalized_claim_id:
        raise ValueError("Claim ID is required.")

    object_key = (
        f"{DOCUMENT_INGESTION_PREFIX}/"
        f"{normalized_claim_id}/claim_record.json"
    )

    s3_client = get_aws_session().client("s3")
    try:
        response = s3_client.get_object(
            Bucket=AWS_BUCKET_NAME,
            Key=object_key,
        )
    except AttributeError:
        return None
    except ClientError as error:
        error_code = str(
            error.response.get("Error", {}).get("Code", "")
        )
        if error_code in {"NoSuchKey", "404", "NotFound"}:
            return None
        raise

    return json.loads(
        response["Body"].read().decode("utf-8")
    )


def _upload_extension(upload: object) -> tuple[str, str]:
    original_filename = str(
        getattr(upload, "original_filename", "")
    )
    extension = Path(original_filename).suffix.casefold()

    if extension not in SUPPORTED_IMAGE_TYPES:
        raise ValueError(
            f"{original_filename}: unsupported image format."
        )

    content = getattr(upload, "content", b"")
    if not content:
        raise ValueError(
            f"{original_filename}: uploaded file is empty."
        )

    return extension, SUPPORTED_IMAGE_TYPES[extension]


def upload_aws_claim_package(
    *,
    claim_id: str,
    claim_record: dict,
    uploads: list[object],
) -> dict:
    normalized_claim_id = claim_id.strip().upper()

    documents: dict[str, object] = {}
    primary_vehicle_image = None

    for upload in uploads:
        evidence_type = str(
            getattr(upload, "evidence_type", "")
        )
        image_slot = getattr(upload, "image_slot", None)

        if evidence_type in {"ktp", "sim", "stnk"}:
            documents[evidence_type] = upload
        elif (
            evidence_type == "vehicle_image"
            and image_slot == "primary_damage"
        ):
            primary_vehicle_image = upload

    missing_documents = [
        document_type
        for document_type in ("ktp", "sim", "stnk")
        if document_type not in documents
    ]

    if missing_documents:
        raise ValueError(
            "Missing documents: "
            + ", ".join(missing_documents)
        )

    if primary_vehicle_image is None:
        raise ValueError(
            "The primary vehicle damage image is missing."
        )

    s3_client = get_aws_session().client("s3")
    document_keys: dict[str, str] = {}

    for document_type in ("ktp", "sim", "stnk"):
        upload = documents[document_type]
        extension, content_type = _upload_extension(upload)

        object_name = f"{document_type}{extension}"
        object_key = (
            f"{DOCUMENT_INGESTION_PREFIX}/"
            f"{normalized_claim_id}/{object_name}"
        )

        s3_client.put_object(
            Bucket=AWS_BUCKET_NAME,
            Key=object_key,
            Body=getattr(upload, "content"),
            ContentType=content_type,
        )

        document_keys[document_type] = object_key

    image_extension, image_content_type = _upload_extension(
        primary_vehicle_image
    )
    image_name = f"primary_damage{image_extension}"
    image_key = (
        f"{VEHICLE_INGESTION_PREFIX}/"
        f"{normalized_claim_id}/{image_name}"
    )

    s3_client.put_object(
        Bucket=AWS_BUCKET_NAME,
        Key=image_key,
        Body=getattr(primary_vehicle_image, "content"),
        ContentType=image_content_type,
    )

    aws_claim_record = copy.deepcopy(claim_record)
    aws_claim_record["claim_id"] = normalized_claim_id
    aws_claim_record["document_references"] = {
        document_type: Path(object_key).name
        for document_type, object_key in document_keys.items()
    }
    aws_claim_record["vehicle_image_reference"] = image_name

    claim_record_key = (
        f"{DOCUMENT_INGESTION_PREFIX}/"
        f"{normalized_claim_id}/claim_record.json"
    )

    s3_client.put_object(
        Bucket=AWS_BUCKET_NAME,
        Key=claim_record_key,
        Body=json.dumps(
            aws_claim_record,
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8"),
        ContentType="application/json",
    )

    return {
        "claim_id": normalized_claim_id,
        "document_keys": document_keys,
        "vehicle_image_key": image_key,
        "claim_record_key": claim_record_key,
    }


def upload_aws_replacement_evidence(
    *,
    claim_id: str,
    uploads: list[object],
) -> dict[str, str]:
    """Replace requested claim evidence in the existing AWS claim package."""
    normalized_claim_id = claim_id.strip().upper()
    if not normalized_claim_id:
        raise ValueError("Claim ID is required.")

    s3_client = get_aws_session().client("s3")
    uploaded_keys: dict[str, str] = {}

    for upload in uploads:
        evidence_type = str(getattr(upload, "evidence_type", ""))
        image_slot = str(getattr(upload, "image_slot", "") or "")
        extension, content_type = _upload_extension(upload)

        if evidence_type in {"ktp", "sim", "stnk"}:
            evidence_key = evidence_type
            object_key = (
                f"{DOCUMENT_INGESTION_PREFIX}/"
                f"{normalized_claim_id}/{evidence_type}{extension}"
            )
        elif evidence_type == "vehicle_image" and image_slot:
            evidence_key = image_slot
            object_key = (
                f"{VEHICLE_INGESTION_PREFIX}/"
                f"{normalized_claim_id}/{image_slot}{extension}"
            )
        else:
            raise ValueError("Unsupported replacement evidence type.")

        object_stem = object_key.rsplit(".", 1)[0]
        for stale_extension in SUPPORTED_IMAGE_TYPES:
            stale_key = f"{object_stem}{stale_extension}"
            if stale_key != object_key:
                s3_client.delete_object(
                    Bucket=AWS_BUCKET_NAME,
                    Key=stale_key,
                )

        s3_client.put_object(
            Bucket=AWS_BUCKET_NAME,
            Key=object_key,
            Body=getattr(upload, "content"),
            ContentType=content_type,
        )
        uploaded_keys[evidence_key] = object_key

    claim_record = get_aws_claim_record(normalized_claim_id)
    if claim_record is not None:
        document_references = dict(
            claim_record.get("document_references") or {}
        )
        for evidence_key, object_key in uploaded_keys.items():
            if evidence_key in {"ktp", "sim", "stnk"}:
                document_references[evidence_key] = Path(
                    object_key
                ).name
            elif evidence_key == "primary_damage":
                claim_record["vehicle_image_reference"] = Path(
                    object_key
                ).name

        claim_record["document_references"] = document_references
        claim_record_key = (
            f"{DOCUMENT_INGESTION_PREFIX}/"
            f"{normalized_claim_id}/claim_record.json"
        )
        s3_client.put_object(
            Bucket=AWS_BUCKET_NAME,
            Key=claim_record_key,
            Body=json.dumps(
                claim_record,
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8"),
            ContentType="application/json",
        )

    return uploaded_keys


def _archive_validation_result(
    s3_uri: str | None,
    *,
    claim_id: str,
    assessment_type: str,
    timestamp_token: str,
) -> str | None:
    if not s3_uri:
        return None

    parsed_uri = urlparse(s3_uri)
    if parsed_uri.scheme != "s3" or not parsed_uri.netloc:
        return None

    source_key = parsed_uri.path.lstrip("/")
    archive_key = (
        f"claims-demo/extracted/{assessment_type}-claims/"
        f"{claim_id}/validation/history/"
        f"{timestamp_token}_{Path(source_key).name}"
    )

    get_aws_session().client("s3").copy_object(
        Bucket=parsed_uri.netloc,
        CopySource={
            "Bucket": parsed_uri.netloc,
            "Key": source_key,
        },
        Key=archive_key,
        ContentType="application/json",
        MetadataDirective="REPLACE",
    )
    return f"s3://{parsed_uri.netloc}/{archive_key}"


def prepare_aws_claim_resubmission(
    claim_id: str,
    *,
    replaced_evidence: list[str] | tuple[str, ...],
) -> dict:
    """Reset only the AWS workflow stage affected by replacement evidence."""
    normalized_claim_id = claim_id.strip().upper()
    normalized_evidence = list(
        dict.fromkeys(
            value.strip()
            for value in replaced_evidence
            if value and value.strip()
        )
    )
    if not normalized_claim_id:
        raise ValueError("Claim ID is required.")
    if not normalized_evidence:
        raise ValueError("Replacement evidence is required.")

    status = get_aws_claim_status(normalized_claim_id)
    if status is None:
        raise ValueError(
            f"Claim {normalized_claim_id} was not found in AWS."
        )

    requested_evidence = {
        str(value)
        for value in status.get("requested_evidence", [])
    }
    submitted_evidence = set(normalized_evidence)
    if requested_evidence and submitted_evidence != requested_evidence:
        missing = requested_evidence - submitted_evidence
        extra = submitted_evidence - requested_evidence
        details = []
        if missing:
            details.append("missing: " + ", ".join(sorted(missing)))
        if extra:
            details.append(
                "not requested: " + ", ".join(sorted(extra))
            )
        raise ValueError(
            "Replacement evidence does not match the request ("
            + "; ".join(details)
            + ")."
        )

    document_replaced = bool(
        submitted_evidence & {"ktp", "sim", "stnk"}
    )
    vehicle_replaced = bool(
        submitted_evidence - {"ktp", "sim", "stnk"}
    )

    timestamp = datetime.now(timezone.utc)
    timestamp_iso = timestamp.isoformat()
    timestamp_token = timestamp.strftime("%Y%m%dT%H%M%S%fZ")

    archived_results: list[str] = []
    if document_replaced:
        archived_uri = _archive_validation_result(
            status.get("document_validation_result_s3_uri"),
            claim_id=normalized_claim_id,
            assessment_type="document",
            timestamp_token=timestamp_token,
        )
        if archived_uri:
            archived_results.append(archived_uri)

    if vehicle_replaced or document_replaced:
        archived_uri = _archive_validation_result(
            status.get("image_validation_result_s3_uri"),
            claim_id=normalized_claim_id,
            assessment_type="vehicle",
            timestamp_token=timestamp_token,
        )
        if archived_uri:
            archived_results.append(archived_uri)

    if document_replaced:
        set_values = {
            "claim_status": "SUBMITTED",
            "processing_stage": "DOCUMENT_RESUBMITTED",
            "document_processing_status": "PENDING",
            "next_action": "START_DOCUMENT_PROCESSING",
            "image_assessment_allowed": False,
            "agent_document_decision": "PENDING",
            "requested_evidence": [],
            "customer_message": (
                "Your replacement evidence was received and is "
                "under review."
            ),
            "updated_at": timestamp_iso,
        }
        remove_fields = {
            "document_validation_result_s3_uri",
            "document_bda_invocations",
            "document_package_fingerprint",
            "document_processing_started_at",
            "document_processing_completed_at",
            "image_validation_result_s3_uri",
            "image_bda_invocation_arn",
            "image_input_etag",
            "image_assessment_completed_at",
            "agent_final_decision",
            "agent_final_decision_at",
            "agent_final_decision_by",
            "agent_final_decision_reason",
        }
    else:
        set_values = {
            "claim_status": "SUBMITTED",
            "processing_stage": "IMAGE_RESUBMITTED",
            "image_processing_status": "PENDING",
            "next_action": "START_IMAGE_ASSESSMENT",
            "image_assessment_allowed": True,
            "requested_evidence": [],
            "customer_message": (
                "Your replacement vehicle photo was received and "
                "is under review."
            ),
            "updated_at": timestamp_iso,
        }
        remove_fields = {
            "image_validation_result_s3_uri",
            "image_bda_invocation_arn",
            "image_input_etag",
            "image_assessment_completed_at",
            "agent_final_decision",
            "agent_final_decision_at",
            "agent_final_decision_by",
            "agent_final_decision_reason",
        }

    expression_names: dict[str, str] = {}
    expression_values: dict[str, object] = {}
    set_parts: list[str] = []

    for index, (field_name, value) in enumerate(set_values.items()):
        name_token = f"#set{index}"
        value_token = f":value{index}"
        expression_names[name_token] = field_name
        expression_values[value_token] = value
        set_parts.append(f"{name_token} = {value_token}")

    remove_parts: list[str] = []
    for index, field_name in enumerate(sorted(remove_fields)):
        if field_name in set_values:
            continue
        name_token = f"#remove{index}"
        expression_names[name_token] = field_name
        remove_parts.append(name_token)

    update_expression = "SET " + ", ".join(set_parts)
    if remove_parts:
        update_expression += " REMOVE " + ", ".join(remove_parts)

    response = (
        get_aws_session()
        .resource("dynamodb")
        .Table(CLAIMS_TABLE_NAME)
        .update_item(
            Key={"claim_id": normalized_claim_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_names,
            ExpressionAttributeValues=expression_values,
            ReturnValues="ALL_NEW",
        )
    )

    return {
        "claim_id": normalized_claim_id,
        "document_replaced": document_replaced,
        "vehicle_replaced": vehicle_replaced,
        "archived_results": archived_results,
        "status": response.get("Attributes", {}),
    }
