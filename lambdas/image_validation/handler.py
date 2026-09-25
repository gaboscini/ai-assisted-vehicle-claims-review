import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import unquote_plus

import boto3


RESULTS_BUCKET = os.environ["RESULTS_BUCKET"]
CLAIMS_TABLE = os.environ["CLAIMS_TABLE"]
DYNAMODB_REGION = os.environ["DYNAMODB_REGION"]
RESULTS_REGION = os.environ.get("RESULTS_REGION", DYNAMODB_REGION)

EXPECTED_VIEWS = [
    view.strip()
    for view in os.environ.get(
        "EXPECTED_VIEWS",
        "front_left,front_right,rear_left,rear_right",
    ).split(",")
    if view.strip()
]

MIN_REQUIRED_IMAGES = int(os.environ.get("MIN_REQUIRED_IMAGES", "4"))
CONSISTENCY_PASS_THRESHOLD = float(
    os.environ.get("CONSISTENCY_PASS_THRESHOLD", "80")
)
CONSISTENCY_REVIEW_THRESHOLD = float(
    os.environ.get("CONSISTENCY_REVIEW_THRESHOLD", "60")
)
ASSESSMENT_THRESHOLD = float(
    os.environ.get("ASSESSMENT_THRESHOLD", "80")
)

MIN_COMPARISON_CONFIDENCE = 60.0

s3 = boto3.client("s3", region_name=RESULTS_REGION)
dynamodb = boto3.resource("dynamodb", region_name=DYNAMODB_REGION)
claims_table = dynamodb.Table(CLAIMS_TABLE)


MISSING_VALUES = {
    "",
    "unknown",
    "unreadable",
    "not_visible",
    "not visible",
    "none",
    "null",
    "n/a",
    "na",
    "unable_to_determine",
}


SEVERITY_ORDER = {
    "none": 0,
    "minor": 1,
    "moderate": 2,
    "severe": 3,
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def response(status_code, body):
    return {
        "statusCode": status_code,
        "body": json.dumps(body),
    }


def normalize_text(value):
    if value is None:
        return ""

    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def usable_value(value):
    normalized = normalize_text(value)
    return bool(normalized) and normalized not in MISSING_VALUES


def number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def unique_values(values):
    output = []
    seen = set()

    for value in values:
        normalized = normalize_text(value)

        if not normalized or normalized in seen:
            continue

        seen.add(normalized)
        output.append(value)

    return output


def extract_claim_ids(event):
    claim_ids = set()

    if isinstance(event, dict) and event.get("claim_id"):
        claim_ids.add(str(event["claim_id"]).strip())

    for record in event.get("Records", []) if isinstance(event, dict) else []:
        if record.get("eventSource") != "aws:s3":
            continue

        key = unquote_plus(record["s3"]["object"]["key"])
        parts = key.split("/")

        if parts:
            claim_ids.add(parts[0])

    return sorted(claim_id for claim_id in claim_ids if claim_id)


def list_result_objects(claim_id):
    prefix = f"{claim_id}/"
    paginator = s3.get_paginator("list_objects_v2")

    latest_by_view = {}

    for page in paginator.paginate(Bucket=RESULTS_BUCKET, Prefix=prefix):
        for item in page.get("Contents", []):
            key = item["Key"]

            if not key.endswith("/custom_output/0/result.json"):
                continue

            parts = key.split("/")

            if len(parts) < 3:
                continue

            view = parts[1]

            if view not in EXPECTED_VIEWS:
                continue

            current = latest_by_view.get(view)

            if current is None or item["LastModified"] > current["LastModified"]:
                latest_by_view[view] = item

    return latest_by_view


def load_json(key):
    result = s3.get_object(Bucket=RESULTS_BUCKET, Key=key)
    return json.loads(result["Body"].read().decode("utf-8"))


def load_view_results(result_objects):
    results = {}

    for view, item in result_objects.items():
        payload = load_json(item["Key"])
        inference = payload.get("inference_result", {})

        results[view] = {
            "source_key": item["Key"],
            "matched_blueprint": payload.get("matched_blueprint", {}),
            "inference_result": inference,
        }

    return results


def confidence_for(inference, field_name):
    return number(inference.get(f"{field_name}_confidence"), 0.0)


def assess_scalar_field(view_results, field_name, display_name, weight):
    observations = []

    for view, result in view_results.items():
        inference = result["inference_result"]
        value = inference.get(field_name)
        confidence = confidence_for(inference, field_name)

        if not usable_value(value):
            continue

        if confidence < MIN_COMPARISON_CONFIDENCE:
            continue

        observations.append(
            {
                "view": view,
                "value": value,
                "normalized_value": normalize_text(value),
                "confidence": round(confidence, 2),
            }
        )

    if len(observations) < 2:
        return {
            "field": field_name,
            "display_name": display_name,
            "weight": weight,
            "comparable": False,
            "score": None,
            "observations": observations,
            "reason": "Fewer than two reliable observations were available.",
        }

    counts = Counter(item["normalized_value"] for item in observations)
    dominant_value, dominant_count = counts.most_common(1)[0]
    score = round((dominant_count / len(observations)) * 100, 2)

    return {
        "field": field_name,
        "display_name": display_name,
        "weight": weight,
        "comparable": True,
        "score": score,
        "dominant_value": dominant_value,
        "observations": observations,
        "reason": (
            f"{dominant_count} of {len(observations)} reliable observations agree."
        ),
    }


def wheel_signature(description):
    text = normalize_text(description)

    if not text:
        return set()

    signature = set()

    if "multi spoke" in text or "multispoke" in text:
        signature.add("multi_spoke")
    elif "five spoke" in text or "5 spoke" in text:
        signature.add("five_spoke")
    elif "six spoke" in text or "6 spoke" in text:
        signature.add("six_spoke")

    if "alloy" in text:
        signature.add("alloy")
    if "steel" in text:
        signature.add("steel")
    if "black" in text:
        signature.add("black")
    if "silver" in text:
        signature.add("silver")
    if "chrome" in text:
        signature.add("chrome")

    return signature


def assess_wheels(view_results):
    observations = []

    for view, result in view_results.items():
        inference = result["inference_result"]
        value = inference.get("wheel_description")
        confidence = confidence_for(inference, "wheel_description")

        if not usable_value(value):
            continue

        if confidence < MIN_COMPARISON_CONFIDENCE:
            continue

        signature = wheel_signature(value)

        observations.append(
            {
                "view": view,
                "value": value,
                "confidence": round(confidence, 2),
                "signature": sorted(signature),
            }
        )

    if len(observations) < 2:
        return {
            "field": "wheel_description",
            "display_name": "Wheel appearance",
            "weight": 20.0,
            "comparable": False,
            "score": None,
            "observations": observations,
            "reason": "Fewer than two reliable wheel observations were available.",
        }

    signatures = [set(item["signature"]) for item in observations]
    pair_scores = []

    for left_index in range(len(signatures)):
        for right_index in range(left_index + 1, len(signatures)):
            left = signatures[left_index]
            right = signatures[right_index]

            if not left or not right:
                continue

            intersection = left.intersection(right)
            union = left.union(right)

            if "multi_spoke" in intersection:
                pair_score = 90.0
            elif intersection:
                pair_score = max(60.0, (len(intersection) / len(union)) * 100)
            else:
                pair_score = 0.0

            pair_scores.append(pair_score)

    if not pair_scores:
        score = 50.0
    else:
        score = round(sum(pair_scores) / len(pair_scores), 2)

    return {
        "field": "wheel_description",
        "display_name": "Wheel appearance",
        "weight": 20.0,
        "comparable": True,
        "score": score,
        "observations": observations,
        "reason": "Wheel design and visible wheel characteristics were compared.",
    }


def physical_plate_values(view_results):
    observations = []

    for view, result in view_results.items():
        inference = result["inference_result"]
        value = inference.get("plate_number")
        confidence = confidence_for(inference, "plate_number")

        if not usable_value(value):
            continue

        if confidence < MIN_COMPARISON_CONFIDENCE:
            continue

        observations.append(
            {
                "view": view,
                "value": value,
                "normalized_value": normalize_text(value).replace(" ", ""),
                "confidence": round(confidence, 2),
            }
        )

    distinct_plates = sorted(
        {
            item["normalized_value"]
            for item in observations
            if item["normalized_value"]
        }
    )

    conflict = len(distinct_plates) > 1

    return {
        "observations": observations,
        "distinct_plate_numbers": distinct_plates,
        "conflict_detected": conflict,
    }


def assess_cross_image_consistency(view_results):
    components = [
        assess_scalar_field(
            view_results,
            "vehicle_make",
            "Vehicle make",
            30.0,
        ),
        assess_scalar_field(
            view_results,
            "vehicle_body_type",
            "Vehicle body type",
            20.0,
        ),
        assess_scalar_field(
            view_results,
            "vehicle_primary_color",
            "Vehicle colour",
            30.0,
        ),
        assess_wheels(view_results),
    ]

    comparable = [
        component
        for component in components
        if component["comparable"] and component["score"] is not None
    ]

    total_weight = sum(component["weight"] for component in comparable)

    if total_weight:
        weighted_score = sum(
            component["score"] * component["weight"]
            for component in comparable
        ) / total_weight
        consistency_score = round(weighted_score, 2)
    else:
        consistency_score = 0.0

    plate_assessment = physical_plate_values(view_results)

    if plate_assessment["conflict_detected"]:
        status = "inconsistent"
    elif consistency_score >= CONSISTENCY_PASS_THRESHOLD:
        status = "consistent"
    elif consistency_score >= CONSISTENCY_REVIEW_THRESHOLD:
        status = "needs_review"
    else:
        status = "inconsistent"

    supporting_features = []

    for view, result in view_results.items():
        inference = result["inference_result"]

        for feature in inference.get("distinctive_vehicle_features", []) or []:
            supporting_features.append(feature)

    return {
        "consistency_score": consistency_score,
        "pass_threshold": CONSISTENCY_PASS_THRESHOLD,
        "review_threshold": CONSISTENCY_REVIEW_THRESHOLD,
        "status": status,
        "comparison_components": components,
        "physical_plate_assessment": plate_assessment,
        "supporting_distinctive_features": unique_values(supporting_features),
        "limitations": [
            "Cross-image consistency does not prove vehicle identity.",
            "Unreadable or unavailable plate numbers are treated as limitations.",
            "Image angle, lighting, damage, and obstruction may affect comparisons.",
        ],
    }


def assess_evidence(view_results, consistency):
    hard_failures = []
    review_flags = []

    for view, result in view_results.items():
        inference = result["inference_result"]

        image_type = normalize_text(inference.get("image_type"))
        image_type_confidence = confidence_for(inference, "image_type")

        if image_type != "real photo" and image_type_confidence >= 80:
            hard_failures.append(
                f"{view}: the image is not classified as a real photograph."
            )

        vehicle_depicted = inference.get("vehicle_depicted")
        vehicle_confidence = confidence_for(inference, "vehicle_depicted")

        if vehicle_depicted is not True and vehicle_confidence >= 85:
            hard_failures.append(
                f"{view}: a vehicle was not reliably detected."
            )

        real_vehicle_visible = inference.get("real_vehicle_visible")
        real_vehicle_confidence = confidence_for(
            inference,
            "real_vehicle_visible",
        )

        if real_vehicle_visible is not True and real_vehicle_confidence >= 85:
            hard_failures.append(
                f"{view}: a real physical vehicle was not reliably visible."
            )

        watermark_detected = inference.get("watermark_detected")
        watermark_confidence = confidence_for(
            inference,
            "watermark_detected",
        )

        if watermark_detected is True and watermark_confidence >= 80:
            hard_failures.append(
                f"{view}: a watermark was detected."
            )

        synthetic_risk = normalize_text(
            inference.get("synthetic_image_risk")
        )

        if synthetic_risk == "high":
            hard_failures.append(
                f"{view}: a high synthetic-image risk was reported."
            )
        elif synthetic_risk in {"medium", "elevated", "inconclusive"}:
            review_flags.append(
                f"{view}: the synthetic-image result requires review."
            )

    if consistency["physical_plate_assessment"]["conflict_detected"]:
        hard_failures.append(
            "Conflicting readable physical plate numbers were detected."
        )

    if consistency["status"] == "inconsistent":
        hard_failures.append(
            "The submitted images do not provide sufficient evidence that "
            "they show the same vehicle."
        )
    elif consistency["status"] == "needs_review":
        review_flags.append(
            "Cross-image vehicle consistency is below the pass threshold."
        )

    comparable_components = [
        component
        for component in consistency["comparison_components"]
        if component["comparable"]
    ]

    if len(comparable_components) < 2:
        review_flags.append(
            "Too few reliable vehicle characteristics were available "
            "for comparison."
        )

    hard_failures = unique_values(hard_failures)
    review_flags = unique_values(review_flags)

    if hard_failures:
        evidence_status = "ineligible"
        recommendation = "REJECT_OR_INVESTIGATE_EVIDENCE"
    elif review_flags:
        evidence_status = "needs_review"
        recommendation = "ESCALATE_FOR_REVIEW"
    else:
        evidence_status = "eligible"
        recommendation = "READY_FOR_AGENT_REVIEW"

    return {
        "evidence_status": evidence_status,
        "hard_failures": hard_failures,
        "review_flags": review_flags,
        "final_recommendation": recommendation,
    }


def aggregate_damage(view_results):
    severity = "none"
    severity_confidence = 0.0
    damage_locations = []
    damage_classifications = []
    damaged_parts = []
    repair_recommendations = []
    summaries = []
    limitations = []

    for view, result in view_results.items():
        inference = result["inference_result"]

        current_severity = normalize_text(inference.get("severity"))

        if SEVERITY_ORDER.get(current_severity, 0) > SEVERITY_ORDER.get(
            severity,
            0,
        ):
            severity = current_severity
            severity_confidence = confidence_for(inference, "severity")

        damage_locations.extend(inference.get("damage_location", []) or [])
        damage_classifications.extend(
            inference.get("damage_classification", []) or []
        )
        damaged_parts.extend(inference.get("damaged_parts", []) or [])

        recommendation = inference.get("repair_recommendation")

        if usable_value(recommendation):
            repair_recommendations.append(recommendation)

        summary = inference.get("analyst_summary")

        if summary:
            summaries.append(
                {
                    "view": view,
                    "summary": summary,
                }
            )

        limitations.extend(inference.get("limitations", []) or [])

    return {
        "damage_visible": any(
            result["inference_result"].get("damage_visible") is True
            for result in view_results.values()
        ),
        "highest_visible_severity": severity,
        "severity_confidence": round(severity_confidence, 2),
        "damage_locations": unique_values(damage_locations),
        "damage_classifications": unique_values(damage_classifications),
        "damaged_parts": unique_values(damaged_parts),
        "repair_recommendations": unique_values(repair_recommendations),
        "view_summaries": summaries,
        "limitations": unique_values(limitations),
    }



def calculate_image_assessment_score(view_results, consistency, evidence):
    scores = []

    for result in view_results.values():
        inference = result["inference_result"]

        image_type = normalize_text(inference.get("image_type"))
        image_type_confidence = confidence_for(inference, "image_type")
        scores.append(
            image_type_confidence if image_type == "real photo" else 0.0
        )

        vehicle_depicted = inference.get("vehicle_depicted")
        vehicle_confidence = confidence_for(inference, "vehicle_depicted")
        scores.append(vehicle_confidence if vehicle_depicted is True else 0.0)

        real_vehicle_visible = inference.get("real_vehicle_visible")
        real_vehicle_confidence = confidence_for(
            inference,
            "real_vehicle_visible",
        )
        scores.append(
            real_vehicle_confidence
            if real_vehicle_visible is True
            else 0.0
        )

        watermark_detected = inference.get("watermark_detected")
        watermark_confidence = confidence_for(
            inference,
            "watermark_detected",
        )
        scores.append(
            watermark_confidence
            if watermark_detected is False
            else 0.0
        )

        synthetic_risk = normalize_text(
            inference.get("synthetic_image_risk")
        )
        synthetic_confidence = confidence_for(
            inference,
            "synthetic_image_assessment",
        )
        scores.append(
            synthetic_confidence
            if synthetic_risk == "low"
            else 0.0
        )

    scores.append(number(consistency.get("consistency_score"), 0.0))

    score = round(sum(scores) / len(scores), 2) if scores else 0.0

    # The score is an approval-readiness score. Hard rules still override it.
    if evidence["hard_failures"]:
        score = min(score, 59.0)
    elif evidence["review_flags"]:
        score = min(score, 79.0)

    return round(score, 2)


def select_primary_repair_recommendation(damage):
    recommendations = damage.get("repair_recommendations", []) or []

    priority = [
        "structural_inspection",
        "part_replacement",
        "damage_inspection",
        "repair",
        "cosmetic_repair",
        "none",
    ]

    normalized_recommendations = {
        normalize_text(value).replace(" ", "_"): value
        for value in recommendations
        if usable_value(value)
    }

    for candidate in priority:
        if candidate in normalized_recommendations:
            return candidate.upper()

    severity = normalize_text(damage.get("highest_visible_severity"))

    if severity == "severe":
        return "STRUCTURAL_INSPECTION"
    if severity == "moderate":
        return "DAMAGE_INSPECTION"
    if severity == "minor":
        return "COSMETIC_OR_PART_REPAIR"
    if severity == "none":
        return "NONE"

    return "UNABLE_TO_DETERMINE"


def has_critical_image_finding(consistency, evidence):
    if consistency.get("status") == "inconsistent":
        return True

    if consistency.get("physical_plate_assessment", {}).get(
        "conflict_detected"
    ):
        return True

    critical_terms = (
        "conflicting readable physical plate",
        "high synthetic-image risk",
        "watermark was detected",
        "not classified as a real photograph",
        "same vehicle",
    )

    for finding in evidence.get("hard_failures", []):
        normalized = normalize_text(finding)

        if any(term in normalized for term in critical_terms):
            return True

    return False


def document_assessment_score(claim_item):
    stored_score = claim_item.get("document_confidence_score")

    if stored_score is not None:
        return number(stored_score, 0.0)

    document_status = normalize_text(
        claim_item.get("document_package_status")
    ).replace(" ", "_")

    fallback_scores = {
        "valid": 100.0,
        "needs_review": 70.0,
        "review": 70.0,
        "invalid": 0.0,
        "incomplete": 0.0,
        "failed": 0.0,
    }

    return fallback_scores.get(document_status, 0.0)


def final_assessment_score(document_score, image_score, consistency_score):
    score = (
        (document_score * 0.40)
        + (image_score * 0.40)
        + (consistency_score * 0.20)
    )
    return round(score, 2)


def normalized_status(value):
    return normalize_text(value).replace(" ", "_")


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

    document_status = normalized_status(
        claim_item.get("document_package_status")
    )
    image_status = normalized_status(
        claim_item.get("image_evidence_status")
    )
    consistency_status = normalized_status(
        claim_item.get("vehicle_consistency_status")
    )

    document_findings = [
        normalized_status(value)
        for value in claim_item.get("document_findings", []) or []
    ]

    document_critical = bool(
        claim_item.get("document_critical_flag")
    ) or any(
        any(
            marker in finding
            for marker in (
                "mismatch",
                "fraud",
                "tamper",
                "identity_conflict",
            )
        )
        for finding in document_findings
    )

    image_critical = bool(claim_item.get("image_critical_flag"))

    document_invalid = document_status in {
        "invalid",
        "incomplete",
        "failed",
        "ineligible",
    }
    image_invalid = image_status in {
        "invalid",
        "ineligible",
        "failed",
    }

    manual_validation_required = (
        document_status in {"needs_review", "review", "for_validation"}
        or image_status in {"needs_review", "review", "for_validation"}
        or consistency_status in {
            "needs_review",
            "inconclusive",
            "unknown",
        }
        or bool(claim_item.get("image_review_required"))
        or bool(claim_item.get("document_review_required"))
    )

    if (
        document_critical
        or image_critical
        or consistency_status == "inconsistent"
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
        document_status == "valid"
        and image_status == "eligible"
        and consistency_status == "consistent"
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

    document_score = document_assessment_score(claim_item)
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


def validate_claim(claim_id):
    claim_item = claims_table.get_item(
        Key={"claim_id": claim_id},
        ConsistentRead=True,
    ).get("Item")

    if not claim_item:
        return {
            "status": "FAILED",
            "claim_id": claim_id,
            "message": "The claim record does not exist in DynamoDB.",
        }

    result_objects = list_result_objects(claim_id)
    received_views = sorted(result_objects)
    missing_views = sorted(set(EXPECTED_VIEWS) - set(received_views))

    if len(received_views) < MIN_REQUIRED_IMAGES or missing_views:
        update_claim(
            claim_id,
            {
                "image_processing_status": "IN_PROGRESS",
                "image_results_received": len(received_views),
                "image_expected_count": MIN_REQUIRED_IMAGES,
                "image_missing_views": missing_views,
                "updated_at": utc_now(),
            },
        )

        return {
            "status": "WAITING",
            "claim_id": claim_id,
            "received_views": received_views,
            "missing_views": missing_views,
        }

    view_results = load_view_results(result_objects)
    consistency = assess_cross_image_consistency(view_results)
    evidence = assess_evidence(view_results, consistency)
    damage = aggregate_damage(view_results)
    image_assessment_score = calculate_image_assessment_score(
        view_results,
        consistency,
        evidence,
    )
    image_critical_flag = has_critical_image_finding(
        consistency,
        evidence,
    )
    primary_repair_recommendation = (
        select_primary_repair_recommendation(damage)
    )

    if evidence["hard_failures"]:
        image_assessment_reason = evidence["hard_failures"][0]
    elif evidence["review_flags"]:
        image_assessment_reason = evidence["review_flags"][0]
    else:
        image_assessment_reason = (
            "The submitted vehicle images passed the configured "
            "evidence and consistency checks."
        )

    result = {
        "schema_version": "1.0.0-aws-parallel-image-reference",
        "claim_id": claim_id,
        "assessment_completed_at": utc_now(),
        "expected_views": EXPECTED_VIEWS,
        "received_views": sorted(view_results),
        "source_result_keys": {
            view: result_objects[view]["Key"]
            for view in sorted(result_objects)
        },
        "cross_image_vehicle_consistency": consistency,
        "evidence_assessment": evidence,
        "damage_assessment": damage,
        "overall_image_assessment": {
            "image_status": evidence["evidence_status"],
            "image_assessment_score": image_assessment_score,
            "image_assessment_threshold": ASSESSMENT_THRESHOLD,
            "vehicle_consistency_status": consistency["status"],
            "vehicle_consistency_score": consistency[
                "consistency_score"
            ],
            "visible_damage_severity": damage[
                "highest_visible_severity"
            ],
            "damage_severity_confidence": damage[
                "severity_confidence"
            ],
            "repair_recommendation": primary_repair_recommendation,
            "critical_flag": image_critical_flag,
            "review_required": bool(evidence["review_flags"]),
            "assessment_reason": image_assessment_reason,
        },
        "automated_claim_decision": False,
    }

    output_key = (
        f"{claim_id}/validation/image_validation_result.json"
    )

    s3.put_object(
        Bucket=RESULTS_BUCKET,
        Key=output_key,
        Body=json.dumps(result, indent=2).encode("utf-8"),
        ContentType="application/json",
    )

    document_ready = bool(claim_item.get("document_result_ready"))

    if document_ready:
        processing_stage = "READY_FOR_AGENT_REVIEW"
        next_action = "AGENT_REVIEW_REQUIRED"
    else:
        processing_stage = "WAITING_FOR_DOCUMENT_ASSESSMENT"
        next_action = "WAIT_FOR_DOCUMENT_ASSESSMENT"

    update_claim(
        claim_id,
        {
            "image_processing_status": "COMPLETED",
            "image_result_ready": True,
            "image_results_received": len(view_results),
            "image_expected_count": MIN_REQUIRED_IMAGES,
            "image_missing_views": [],
            "image_evidence_status": evidence["evidence_status"],
            "image_assessment_score": Decimal(
                str(image_assessment_score)
            ),
            "image_assessment_threshold": Decimal(
                str(round(ASSESSMENT_THRESHOLD, 2))
            ),
            "image_critical_flag": image_critical_flag,
            "image_review_required": bool(evidence["review_flags"]),
            "image_assessment_reason": image_assessment_reason,
            "image_hard_failure_count": len(
                evidence["hard_failures"]
            ),
            "image_review_flag_count": len(
                evidence["review_flags"]
            ),
            "vehicle_consistency_status": consistency["status"],
            "vehicle_consistency_score": Decimal(
                str(consistency["consistency_score"])
            ),
            "visible_damage_severity": damage["highest_visible_severity"],
            "damage_severity_confidence": Decimal(
                str(damage["severity_confidence"])
            ),
            "damaged_areas": damage["damage_locations"],
            "damaged_parts": damage["damaged_parts"],
            "repair_recommendation": primary_repair_recommendation,
            "image_validation_result_s3_uri": (
                f"s3://{RESULTS_BUCKET}/{output_key}"
            ),
            "processing_stage": processing_stage,
            "next_action": next_action,
            "automated_claim_decision": False,
            "image_validation_completed_at": utc_now(),
            "updated_at": utc_now(),
        },
    )

    final_assessment = finalize_assessment_if_ready(claim_id)

    return {
        "status": "COMPLETED",
        "claim_id": claim_id,
        "image_evidence_status": evidence["evidence_status"],
        "image_assessment_score": image_assessment_score,
        "vehicle_consistency_status": consistency["status"],
        "vehicle_consistency_score": consistency["consistency_score"],
        "visible_damage_severity": damage["highest_visible_severity"],
        "repair_recommendation": primary_repair_recommendation,
        "final_recommendation": evidence["final_recommendation"],
        "assessment_classification": (
            final_assessment["assessment_classification"]
            if final_assessment
            else "PENDING_OTHER_ASSESSMENT"
        ),
        "combined_assessment": final_assessment,
        "validation_result_s3_uri": (
            f"s3://{RESULTS_BUCKET}/{output_key}"
        ),
    }


def lambda_handler(event, context):
    claim_ids = extract_claim_ids(event)

    if not claim_ids:
        return response(
            400,
            {
                "message": "No claim ID could be determined from the event.",
            },
        )

    results = {}

    for claim_id in claim_ids:
        try:
            results[claim_id] = validate_claim(claim_id)
        except Exception as exc:
            results[claim_id] = {
                "status": "FAILED",
                "claim_id": claim_id,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }

    failed = any(
        result.get("status") == "FAILED"
        for result in results.values()
    )

    return response(
        207 if failed else 200,
        {
            "message": "Vehicle-image validation event completed.",
            "claims": results,
        },
    )
