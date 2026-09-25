import json
import os
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from difflib import SequenceMatcher
from pathlib import PurePosixPath
from urllib.parse import unquote_plus

import boto3


EXTRACTED_DOCUMENT_BUCKET = os.environ["EXTRACTED_DOCUMENT_BUCKET"]
CLAIMS_DATA_BUCKET = os.environ["CLAIMS_DATA_BUCKET"]
CLAIMS_DATA_REGION = os.environ["CLAIMS_DATA_REGION"]
CLAIMS_TABLE = os.environ["CLAIMS_TABLE"]
DYNAMODB_REGION = os.environ["DYNAMODB_REGION"]
RESULTS_REGION = os.environ.get("RESULTS_REGION", DYNAMODB_REGION)

DOCUMENT_TYPES = ("ktp", "sim", "stnk")

DOCUMENT_TYPE_THRESHOLD = 80.0
NAME_MATCH_THRESHOLD = 90.0
ASSESSMENT_THRESHOLD = float(
    os.environ.get("ASSESSMENT_THRESHOLD", "80")
)

s3_results = boto3.client("s3", region_name=RESULTS_REGION)
s3_claims = boto3.client("s3", region_name=CLAIMS_DATA_REGION)

dynamodb = boto3.resource(
    "dynamodb",
    region_name=DYNAMODB_REGION,
)

claims_table = dynamodb.Table(CLAIMS_TABLE)


FIELD_RULES = {
    "ktp": {
        "identity_number": {
            "display_name": "Identity number",
            "threshold": 45.0,
            "rule": "exact",
        },
        "full_name": {
            "display_name": "Full name",
            "threshold": 80.0,
            "rule": "name",
        },
        "date_of_birth": {
            "display_name": "Date of birth",
            "threshold": 80.0,
            "rule": "exact_date",
        },
        "address": {
            "display_name": "Address",
            "threshold": 60.0,
            "rule": "informational",
        },
    },
    "sim": {
        "license_number": {
            "display_name": "SIM number",
            "threshold": 50.0,
            "rule": "exact",
        },
        "holder_name": {
            "display_name": "Driver name",
            "threshold": 80.0,
            "rule": "name",
        },
        "license_class": {
            "display_name": "Licence class",
            "threshold": 80.0,
            "rule": "exact",
        },
        "expiration_date": {
            "display_name": "Expiration date",
            "threshold": 80.0,
            "rule": "valid_on_incident_date",
        },
    },
    "stnk": {
        "owner_name": {
            "display_name": "Registered owner",
            "threshold": 80.0,
            "rule": "name",
        },
        "plate_number": {
            "display_name": "Vehicle plate number",
            "threshold": 50.0,
            "rule": "exact",
        },
        "vehicle_make": {
            "display_name": "Vehicle make",
            "threshold": 80.0,
            "rule": "exact",
        },
        "vehicle_model": {
            "display_name": "Vehicle model",
            "threshold": 80.0,
            "rule": "exact",
        },
        "vehicle_year": {
            "display_name": "Vehicle year",
            "threshold": 80.0,
            "rule": "exact",
        },
        "chassis_number": {
            "display_name": "Chassis number",
            "threshold": 50.0,
            "rule": "exact",
        },
        "engine_number": {
            "display_name": "Engine number",
            "threshold": 50.0,
            "rule": "exact",
        },
        "registration_expiration_date": {
            "display_name": "Registration expiration date",
            "threshold": 80.0,
            "rule": "valid_on_incident_date",
        },
    },
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def normalize_text(value):
    if value is None:
        return ""

    return re.sub(
        r"[^A-Z0-9]",
        "",
        str(value).upper(),
    )


def confidence_to_percentage(value):
    if value is None:
        return 0.0

    numeric_value = float(value)

    if numeric_value <= 1:
        numeric_value *= 100

    return round(numeric_value, 2)


def fuzzy_match_score(first_value, second_value):
    first = normalize_text(first_value)
    second = normalize_text(second_value)

    if not first or not second:
        return 0.0

    return round(
        SequenceMatcher(None, first, second).ratio() * 100,
        2,
    )


def parse_iso_date(value):
    if not value:
        return None

    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def read_json(bucket, key, client):
    response = client.get_object(
        Bucket=bucket,
        Key=key,
    )

    return json.loads(
        response["Body"].read().decode("utf-8")
    )


def write_json(bucket, key, payload):
    s3_results.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ).encode("utf-8"),
        ContentType="application/json",
    )


def find_latest_result(claim_id, document_type):
    prefix = f"{claim_id}/{document_type}/"

    paginator = s3_results.get_paginator("list_objects_v2")

    matching_objects = []

    for page in paginator.paginate(
        Bucket=EXTRACTED_DOCUMENT_BUCKET,
        Prefix=prefix,
    ):
        for item in page.get("Contents", []):
            key = item["Key"]

            if key.endswith("/custom_output/0/result.json"):
                matching_objects.append(item)

    if not matching_objects:
        return None

    latest_object = max(
        matching_objects,
        key=lambda item: item["LastModified"],
    )

    return latest_object["Key"]


def get_field_confidence(payload, field_name):
    explainability = payload.get("explainability_info", [])

    if not explainability:
        return 0.0

    field_information = explainability[0].get(field_name, {})

    return confidence_to_percentage(
        field_information.get("confidence")
    )


def expected_value_for_field(claim_record, document_type, field_name):
    vehicle = claim_record.get("vehicle", {})

    mappings = {
        "ktp": {
            "identity_number": claim_record.get("identity_number"),
            "full_name": claim_record.get("customer_name"),
            "date_of_birth": claim_record.get("date_of_birth"),
            "address": claim_record.get("address"),
        },
        "sim": {
            "license_number": claim_record.get("sim_number"),
            "holder_name": claim_record.get("customer_name"),
            "license_class": claim_record.get("sim_class"),
            "expiration_date": claim_record.get("incident_date"),
        },
        "stnk": {
            "owner_name": claim_record.get("customer_name"),
            "plate_number": vehicle.get("plate_number"),
            "vehicle_make": vehicle.get("make"),
            "vehicle_model": vehicle.get("model"),
            "vehicle_year": vehicle.get("year"),
            "chassis_number": vehicle.get("chassis_number"),
            "engine_number": vehicle.get("engine_number"),
            "registration_expiration_date": claim_record.get(
                "incident_date"
            ),
        },
    }

    return mappings[document_type].get(field_name)


def validate_field(
    field_name,
    extracted_value,
    expected_value,
    confidence_score,
    rule_configuration,
):
    threshold = rule_configuration["threshold"]
    validation_rule = rule_configuration["rule"]

    findings = []
    match_score = None

    if extracted_value is None or str(extracted_value).strip() == "":
        return {
            "field_name": field_name,
            "display_name": rule_configuration["display_name"],
            "extracted_value": None,
            "expected_value": expected_value,
            "confidence_score": confidence_score,
            "confidence_threshold": threshold,
            "match_score": None,
            "status": "FAIL",
            "findings": ["MISSING_FIELD"],
        }

    if confidence_score < threshold:
        findings.append("LOW_CONFIDENCE")

    if validation_rule == "informational":
        match_score = None

    elif validation_rule == "name":
        match_score = fuzzy_match_score(
            extracted_value,
            expected_value,
        )

        if match_score < NAME_MATCH_THRESHOLD:
            findings.append("NAME_MISMATCH")

    elif validation_rule in {"exact", "exact_date"}:
        if normalize_text(extracted_value) == normalize_text(expected_value):
            match_score = 100.0
        else:
            match_score = 0.0
            findings.append("VALUE_MISMATCH")

    elif validation_rule == "valid_on_incident_date":
        expiration_date = parse_iso_date(extracted_value)
        incident_date = parse_iso_date(expected_value)

        if expiration_date is None or incident_date is None:
            match_score = 0.0
            findings.append("INVALID_DATE")
        elif expiration_date < incident_date:
            match_score = 0.0
            findings.append("EXPIRED_DOCUMENT")
        else:
            match_score = 100.0

    status = "PASS" if not findings else "REVIEW"

    return {
        "field_name": field_name,
        "display_name": rule_configuration["display_name"],
        "extracted_value": extracted_value,
        "expected_value": expected_value,
        "confidence_score": confidence_score,
        "confidence_threshold": threshold,
        "match_score": match_score,
        "status": status,
        "findings": findings,
    }


def validate_document(document_type, payload, claim_record):
    matched_blueprint = payload.get("matched_blueprint", {})
    inference_result = payload.get("inference_result", {})

    blueprint_name = str(
        matched_blueprint.get("name", "")
    ).lower()

    document_type_confidence = confidence_to_percentage(
        matched_blueprint.get("confidence")
    )

    type_matches = document_type in blueprint_name

    field_results = []

    for field_name, rule_configuration in FIELD_RULES[
        document_type
    ].items():
        extracted_value = inference_result.get(field_name)

        expected_value = expected_value_for_field(
            claim_record,
            document_type,
            field_name,
        )

        confidence_score = get_field_confidence(
            payload,
            field_name,
        )

        field_results.append(
            validate_field(
                field_name=field_name,
                extracted_value=extracted_value,
                expected_value=expected_value,
                confidence_score=confidence_score,
                rule_configuration=rule_configuration,
            )
        )

    findings = []

    if not type_matches:
        findings.append("DOCUMENT_TYPE_MISMATCH")

    if document_type_confidence < DOCUMENT_TYPE_THRESHOLD:
        findings.append("LOW_DOCUMENT_TYPE_CONFIDENCE")

    for field_result in field_results:
        findings.extend(field_result["findings"])

    failed_fields = [
        result["field_name"]
        for result in field_results
        if result["status"] == "FAIL"
    ]

    review_fields = [
        result["field_name"]
        for result in field_results
        if result["status"] == "REVIEW"
    ]

    if not type_matches or failed_fields:
        document_status = "invalid"
    elif (
        document_type_confidence < DOCUMENT_TYPE_THRESHOLD
        or review_fields
    ):
        document_status = "needs_review"
    else:
        document_status = "valid"

    return {
        "document_type": document_type,
        "matched_blueprint_name": matched_blueprint.get("name"),
        "document_type_confidence": document_type_confidence,
        "document_type_threshold": DOCUMENT_TYPE_THRESHOLD,
        "field_results": field_results,
        "failed_fields": failed_fields,
        "review_fields": review_fields,
        "findings": sorted(set(findings)),
        "document_status": document_status,
    }



def update_claim(claim_id, values):
    names = {}
    expression_values = {}
    assignments = []

    for index, (field_name, value) in enumerate(values.items()):
        name_token = f"#n{index}"
        value_token = f":v{index}"

        names[name_token] = field_name
        expression_values[value_token] = value
        assignments.append(f"{name_token} = {value_token}")

    claims_table.update_item(
        Key={"claim_id": claim_id},
        UpdateExpression="SET " + ", ".join(assignments),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=expression_values,
    )


def number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def status_token(value):
    if value is None:
        return ""

    return re.sub(
        r"[^A-Z0-9]+",
        "_",
        str(value).upper(),
    ).strip("_")


def calculate_document_confidence_score(
    document_results,
    package_status,
):
    confidence_scores = []

    for document_result in document_results.values():
        confidence_scores.append(
            number(
                document_result.get("document_type_confidence"),
                0.0,
            )
        )

        for field_result in document_result.get(
            "field_results",
            [],
        ):
            confidence_scores.append(
                number(
                    field_result.get("confidence_score"),
                    0.0,
                )
            )

    score = (
        round(
            sum(confidence_scores) / len(confidence_scores),
            2,
        )
        if confidence_scores
        else 0.0
    )

    if package_status == "invalid":
        score = min(score, 59.0)
    elif package_status == "needs_review":
        score = min(score, 79.0)

    return round(score, 2)


def has_critical_document_finding(findings):
    critical_markers = {
        "NAME_MISMATCH",
        "VALUE_MISMATCH",
        "IDENTITY_NUMBER_MISMATCH",
        "LICENSE_NUMBER_MISMATCH",
        "LICENSE_HOLDER_MISMATCH",
        "PLATE_NUMBER_MISMATCH",
        "CHASSIS_NUMBER_MISMATCH",
        "ENGINE_NUMBER_MISMATCH",
        "FRAUD_SIGNAL",
        "TAMPERING_SIGNAL",
    }

    return any(
        status_token(finding) in critical_markers
        for finding in findings
    )


def document_assessment_reason(package_status, findings):
    if package_status == "valid":
        return (
            "All required documents passed the configured validation rules."
        )

    if package_status == "needs_review":
        return (
            "One or more document checks require manual validation."
        )

    if findings:
        return (
            "The document package did not pass the configured validation "
            f"rules. Primary finding: {findings[0]}."
        )

    return (
        "The document package did not pass the configured validation rules."
    )


def stored_document_score(claim_item):
    score = claim_item.get("document_confidence_score")

    if score is not None:
        return number(score, 0.0)

    fallback = {
        "VALID": 100.0,
        "NEEDS_REVIEW": 70.0,
        "REVIEW": 70.0,
        "INVALID": 0.0,
        "INCOMPLETE": 0.0,
        "FAILED": 0.0,
    }

    return fallback.get(
        status_token(claim_item.get("document_package_status")),
        0.0,
    )


def final_assessment_score(document_score, image_score, consistency_score):
    score = (
        (document_score * 0.40)
        + (image_score * 0.40)
        + (consistency_score * 0.20)
    )
    return round(score, 2)


def finalize_assessment_if_ready(claim_id):
    claim_item = claims_table.get_item(
        Key={"claim_id": claim_id},
        ConsistentRead=True,
    ).get("Item")

    if not claim_item:
        return None

    document_ready = bool(claim_item.get("document_result_ready"))
    image_ready = bool(claim_item.get("image_result_ready"))

    if not document_ready or not image_ready:
        return None

    document_status = status_token(
        claim_item.get("document_package_status")
    )
    image_status = status_token(
        claim_item.get("image_evidence_status")
    )
    consistency_status = status_token(
        claim_item.get("vehicle_consistency_status")
    )

    document_findings = [
        status_token(value)
        for value in claim_item.get("document_findings", []) or []
    ]

    document_critical = bool(
        claim_item.get("document_critical_flag")
    ) or has_critical_document_finding(document_findings)

    image_critical = bool(claim_item.get("image_critical_flag"))

    document_invalid = document_status in {
        "INVALID",
        "INCOMPLETE",
        "FAILED",
        "INELIGIBLE",
    }
    image_invalid = image_status in {
        "INVALID",
        "INELIGIBLE",
        "FAILED",
    }

    manual_validation_required = (
        document_status in {
            "NEEDS_REVIEW",
            "REVIEW",
            "FOR_VALIDATION",
        }
        or image_status in {
            "NEEDS_REVIEW",
            "REVIEW",
            "FOR_VALIDATION",
        }
        or consistency_status in {
            "NEEDS_REVIEW",
            "INCONCLUSIVE",
            "UNKNOWN",
        }
        or bool(claim_item.get("document_review_required"))
        or bool(claim_item.get("image_review_required"))
    )

    if (
        document_critical
        or image_critical
        or consistency_status == "INCONSISTENT"
    ):
        classification = "FLAGGED_FOR_REVIEW"
        recommendation = "REFER_FOR_INVESTIGATION"
        reason = (
            "Critical identity, authenticity, or vehicle-consistency "
            "findings require investigation."
        )
    elif document_invalid or image_invalid:
        classification = "FOR_REJECTION"
        recommendation = "PROCEED_TO_AGENT_REJECTION_REVIEW"
        reason = (
            "Required claim evidence did not pass the configured "
            "eligibility rules."
        )
    elif manual_validation_required:
        classification = "FOR_VALIDATION"
        recommendation = "MANUAL_VALIDATION_REQUIRED"
        reason = (
            "One or more assessment results require manual validation."
        )
    elif (
        document_status == "VALID"
        and image_status == "ELIGIBLE"
        and consistency_status == "CONSISTENT"
    ):
        classification = "FOR_POSSIBLE_APPROVAL"
        recommendation = "PROCEED_TO_AGENT_APPROVAL_REVIEW"
        reason = (
            "Required documents and vehicle evidence passed the "
            "configured assessment rules."
        )
    else:
        classification = "FOR_VALIDATION"
        recommendation = "MANUAL_VALIDATION_REQUIRED"
        reason = (
            "The combined assessment is incomplete or does not meet all "
            "possible-approval conditions."
        )

    document_score = stored_document_score(claim_item)
    image_score = number(
        claim_item.get("image_assessment_score"),
        0.0,
    )
    consistency_score = number(
        claim_item.get("vehicle_consistency_score"),
        0.0,
    )

    assessment_score = final_assessment_score(
        document_score,
        image_score,
        consistency_score,
    )

    if classification in {
        "FOR_VALIDATION",
        "FLAGGED_FOR_REVIEW",
    }:
        assessment_score = min(assessment_score, 79.0)
    elif classification == "FOR_REJECTION":
        assessment_score = min(assessment_score, 59.0)

    completed_at = utc_now()

    update_claim(
        claim_id,
        {
            "assessment_classification": classification,
            "assessment_score": Decimal(str(round(assessment_score, 2))),
            "assessment_threshold": Decimal(
                str(round(ASSESSMENT_THRESHOLD, 2))
            ),
            "recommendation": recommendation,
            "recommendation_reason": reason,
            "assessment_completed": True,
            "assessment_completed_at": completed_at,
            "processing_stage": "READY_FOR_AGENT_REVIEW",
            "next_action": recommendation,
            "automated_claim_decision": False,
            "updated_at": completed_at,
        },
    )

    return {
        "assessment_classification": classification,
        "assessment_score": assessment_score,
        "assessment_threshold": ASSESSMENT_THRESHOLD,
        "recommendation": recommendation,
        "recommendation_reason": reason,
    }


def validate_document_package(claim_id):
    result_keys = {}

    for document_type in DOCUMENT_TYPES:
        result_key = find_latest_result(
            claim_id,
            document_type,
        )

        if result_key:
            result_keys[document_type] = result_key

    missing_results = [
        document_type
        for document_type in DOCUMENT_TYPES
        if document_type not in result_keys
    ]

    if missing_results:
        claims_table.update_item(
            Key={"claim_id": claim_id},
            UpdateExpression=(
                "SET document_processing_status = :status, "
                "updated_at = :updated_at"
            ),
            ExpressionAttributeValues={
                ":status": "WAITING_FOR_RESULTS",
                ":updated_at": utc_now(),
            },
        )

        return {
            "status": "WAITING",
            "claim_id": claim_id,
            "missing_results": missing_results,
            "found_results": sorted(result_keys),
        }

    claim_record_key = (
        f"claims/{claim_id}/claim_record.json"
    )

    claim_record = read_json(
        CLAIMS_DATA_BUCKET,
        claim_record_key,
        s3_claims,
    )

    document_results = {}

    for document_type, result_key in result_keys.items():
        payload = read_json(
            EXTRACTED_DOCUMENT_BUCKET,
            result_key,
            s3_results,
        )

        document_results[document_type] = validate_document(
            document_type,
            payload,
            claim_record,
        )

    document_statuses = [
        result["document_status"]
        for result in document_results.values()
    ]

    all_findings = sorted({
        finding
        for result in document_results.values()
        for finding in result["findings"]
    })

    if "invalid" in document_statuses:
        package_status = "invalid"
        document_next_action = "REQUEST_CORRECTED_DOCUMENTS"
    elif "needs_review" in document_statuses:
        package_status = "needs_review"
        document_next_action = "REVIEW_DOCUMENTS"
    else:
        package_status = "valid"
        document_next_action = "DOCUMENTS_VALID"

    document_confidence_score = calculate_document_confidence_score(
        document_results,
        package_status,
    )
    document_critical_flag = has_critical_document_finding(
        all_findings
    )
    document_review_required = package_status == "needs_review"
    assessment_reason = document_assessment_reason(
        package_status,
        all_findings,
    )

    validation_result = {
        "schema_version": "1.0.0-parallel-reference",
        "claim_id": claim_id,
        "policy_number": claim_record.get("policy_number"),
        "document_results": document_results,
        "document_package_status": package_status,
        "document_findings": all_findings,
        "document_next_action": document_next_action,
        "overall_document_assessment": {
            "document_status": package_status,
            "document_confidence_score": document_confidence_score,
            "document_confidence_threshold": ASSESSMENT_THRESHOLD,
            "documents_checked": len(document_results),
            "documents_required": len(DOCUMENT_TYPES),
            "critical_flag": document_critical_flag,
            "review_required": document_review_required,
            "assessment_reason": assessment_reason,
        },
        "automated_claim_decision": False,
        "completed_at": utc_now(),
    }

    validation_key = (
        f"{claim_id}/validation/"
        "document_validation_result.json"
    )

    write_json(
        EXTRACTED_DOCUMENT_BUCKET,
        validation_key,
        validation_result,
    )

    validation_uri = (
        f"s3://{EXTRACTED_DOCUMENT_BUCKET}/{validation_key}"
    )

    claims_table.update_item(
        Key={"claim_id": claim_id},
        UpdateExpression=(
            "SET document_processing_status = :processing_status, "
            "document_package_status = :package_status, "
            "document_result_ready = :result_ready, "
            "document_validation_result_s3_uri = :result_uri, "
            "document_findings = :findings, "
            "document_next_action = :next_action, "
            "document_confidence_score = :confidence_score, "
            "document_confidence_threshold = :confidence_threshold, "
            "documents_checked = :documents_checked, "
            "documents_required = :documents_required, "
            "document_critical_flag = :critical_flag, "
            "document_review_required = :review_required, "
            "document_assessment_reason = :assessment_reason, "
            "ktp_document_status = :ktp_status, "
            "sim_document_status = :sim_status, "
            "stnk_document_status = :stnk_status, "
            "document_validation_completed_at = :completed_at, "
            "automated_claim_decision = :automated_decision, "
            "updated_at = :updated_at"
        ),
        ExpressionAttributeValues={
            ":processing_status": "COMPLETED",
            ":package_status": package_status,
            ":result_ready": True,
            ":result_uri": validation_uri,
            ":findings": all_findings,
            ":next_action": document_next_action,
            ":confidence_score": Decimal(
                str(document_confidence_score)
            ),
            ":confidence_threshold": Decimal(
                str(round(ASSESSMENT_THRESHOLD, 2))
            ),
            ":documents_checked": len(document_results),
            ":documents_required": len(DOCUMENT_TYPES),
            ":critical_flag": document_critical_flag,
            ":review_required": document_review_required,
            ":assessment_reason": assessment_reason,
            ":ktp_status": document_results["ktp"]["document_status"],
            ":sim_status": document_results["sim"]["document_status"],
            ":stnk_status": document_results["stnk"]["document_status"],
            ":completed_at": validation_result["completed_at"],
            ":automated_decision": False,
            ":updated_at": utc_now(),
        },
    )

    final_assessment = finalize_assessment_if_ready(claim_id)

    return {
        "status": "COMPLETED",
        "claim_id": claim_id,
        "document_package_status": package_status,
        "document_confidence_score": document_confidence_score,
        "document_next_action": document_next_action,
        "assessment_classification": (
            final_assessment["assessment_classification"]
            if final_assessment
            else "PENDING_OTHER_ASSESSMENT"
        ),
        "combined_assessment": final_assessment,
        "validation_result_s3_uri": validation_uri,
    }


def lambda_handler(event, context):
    processed_claims = {}

    if isinstance(event, dict) and event.get("claim_id"):
        claim_id = str(event["claim_id"]).strip()

        if claim_id:
            processed_claims[claim_id] = validate_document_package(
                claim_id
            )

    for record in event.get("Records", []):
        if record.get("eventSource") != "aws:s3":
            continue

        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])

        if bucket != EXTRACTED_DOCUMENT_BUCKET:
            continue

        parts = PurePosixPath(key).parts

        if not parts:
            continue

        claim_id = parts[0]

        if claim_id in processed_claims:
            continue

        processed_claims[claim_id] = validate_document_package(
            claim_id
        )

    response = {
        "message": "Document validation event completed.",
        "claims": processed_claims,
    }

    print(json.dumps(response))

    return {
        "statusCode": 200,
        "body": json.dumps(response),
    }
