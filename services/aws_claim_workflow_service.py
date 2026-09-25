import json
import os

from services.aws_claim_service import get_aws_session


DOCUMENT_PROCESSING_FUNCTION = os.getenv(
    "CLAIMS_AWS_DOCUMENT_PROCESSING_FUNCTION",
    "example-document-processing",
)

VEHICLE_IMAGE_PROCESSING_FUNCTION = os.getenv(
    "CLAIMS_AWS_VEHICLE_IMAGE_PROCESSING_FUNCTION",
    "example-vehicle-image-processing",
)

AGENT_DOCUMENT_APPROVAL_FUNCTION = os.getenv(
    "CLAIMS_AWS_AGENT_DOCUMENT_APPROVAL_FUNCTION",
    "example-agent-document-approval",
)

DEFAULT_DECISION_REASONS = {
    "APPROVE": "The submitted evidence was reviewed and accepted.",
    "REJECT": "The submitted evidence was reviewed and not accepted.",
    "REQUEST_MORE_INFORMATION": (
        "Replacement evidence is required to continue the review."
    ),
    "INVESTIGATE": (
        "The claim was marked for additional investigation."
    ),
}


def _invoke_agent_action(payload: dict, *, fallback_message: str) -> dict:
    response = get_aws_session().client("lambda").invoke(
        FunctionName=AGENT_DOCUMENT_APPROVAL_FUNCTION,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode("utf-8"),
    )

    if response.get("FunctionError"):
        raise RuntimeError(
            "The claims-agent action Lambda returned an error."
        )

    function_response = json.loads(
        response["Payload"].read().decode("utf-8")
    )
    body = function_response.get("body", {})
    if isinstance(body, str):
        body = json.loads(body)

    status_code = int(function_response.get("statusCode", 500))
    if status_code < 200 or status_code >= 300:
        message = body.get("message", fallback_message)
        raise RuntimeError(message)

    return {
        "status_code": status_code,
        "body": body,
    }


def verify_document_processing_permission() -> int:
    response = get_aws_session().client("lambda").invoke(
        FunctionName=DOCUMENT_PROCESSING_FUNCTION,
        InvocationType="DryRun",
    )

    return response["StatusCode"]


def start_document_processing(claim_id: str) -> dict:
    normalized_claim_id = claim_id.strip().upper()

    if not normalized_claim_id:
        raise ValueError("Claim ID is required.")

    response = get_aws_session().client("lambda").invoke(
        FunctionName=DOCUMENT_PROCESSING_FUNCTION,
        InvocationType="RequestResponse",
        Payload=json.dumps(
            {"claim_id": normalized_claim_id}
        ).encode("utf-8"),
    )

    if response.get("FunctionError"):
        raise RuntimeError(
            "The document-processing Lambda returned an error."
        )

    function_response = json.loads(
        response["Payload"].read().decode("utf-8")
    )

    body = function_response.get("body", {})
    if isinstance(body, str):
        body = json.loads(body)

    status_code = int(
        function_response.get("statusCode", 500)
    )

    if status_code < 200 or status_code >= 300:
        message = body.get(
            "message",
            "Document processing could not be started.",
        )
        raise RuntimeError(message)

    return {
        "status_code": status_code,
        "body": body,
    }


def start_vehicle_image_processing(claim_id: str) -> dict:
    normalized_claim_id = claim_id.strip().upper()

    if not normalized_claim_id:
        raise ValueError("Claim ID is required.")

    response = get_aws_session().client("lambda").invoke(
        FunctionName=VEHICLE_IMAGE_PROCESSING_FUNCTION,
        InvocationType="RequestResponse",
        Payload=json.dumps(
            {"claim_id": normalized_claim_id}
        ).encode("utf-8"),
    )

    if response.get("FunctionError"):
        raise RuntimeError(
            "The vehicle-image-processing Lambda returned an error."
        )

    function_response = json.loads(
        response["Payload"].read().decode("utf-8")
    )
    body = function_response.get("body", {})
    if isinstance(body, str):
        body = json.loads(body)

    status_code = int(function_response.get("statusCode", 500))
    if status_code < 200 or status_code >= 300:
        message = body.get(
            "message",
            "Vehicle-image processing could not be started.",
        )
        raise RuntimeError(message)

    return {
        "status_code": status_code,
        "body": body,
    }


def submit_agent_document_decision(
    claim_id: str,
    *,
    decision: str,
    reason: str = "",
    requested_evidence: list[str] | None = None,
    agent_id: str = "streamlit-claims-agent",
) -> dict:
    normalized_claim_id = claim_id.strip().upper()
    normalized_decision = decision.strip().upper()
    normalized_reason = reason.strip()
    normalized_agent_id = agent_id.strip() or "streamlit-claims-agent"
    normalized_requested_evidence = list(
        dict.fromkeys(requested_evidence or [])
    )

    if not normalized_claim_id:
        raise ValueError("Claim ID is required.")
    if normalized_decision not in {
        "APPROVE",
        "REQUEST_MORE_INFORMATION",
        "REJECT",
    }:
        raise ValueError("Unsupported document decision.")
    if not normalized_reason:
        normalized_reason = DEFAULT_DECISION_REASONS[
            normalized_decision
        ]
    if (
        normalized_decision == "REQUEST_MORE_INFORMATION"
        and not normalized_requested_evidence
    ):
        raise ValueError(
            "Select at least one item of evidence to replace."
        )

    return _invoke_agent_action(
        {
            "action_type": "DOCUMENT_DECISION",
            "claim_id": normalized_claim_id,
            "decision": normalized_decision,
            "reason": normalized_reason,
            "agent_id": normalized_agent_id,
            "requested_evidence": normalized_requested_evidence,
        },
        fallback_message=(
            "The document decision could not be saved in AWS."
        ),
    )


def submit_agent_final_decision(
    claim_id: str,
    *,
    decision: str,
    reason: str = "",
    requested_evidence: list[str] | None = None,
    agent_id: str = "streamlit-claims-agent",
) -> dict:
    normalized_claim_id = claim_id.strip().upper()
    normalized_decision = decision.strip().upper()
    normalized_reason = reason.strip()
    normalized_agent_id = agent_id.strip() or "streamlit-claims-agent"
    normalized_requested_evidence = list(
        dict.fromkeys(requested_evidence or [])
    )

    if not normalized_claim_id:
        raise ValueError("Claim ID is required.")
    if normalized_decision not in {
        "APPROVE",
        "REJECT",
        "REQUEST_MORE_INFORMATION",
        "INVESTIGATE",
    }:
        raise ValueError("Unsupported final claim decision.")
    if not normalized_reason:
        normalized_reason = DEFAULT_DECISION_REASONS[
            normalized_decision
        ]
    if (
        normalized_decision == "REQUEST_MORE_INFORMATION"
        and not normalized_requested_evidence
    ):
        raise ValueError(
            "Select at least one item of evidence to replace."
        )

    return _invoke_agent_action(
        {
            "action_type": "FINAL_DECISION",
            "claim_id": normalized_claim_id,
            "decision": normalized_decision,
            "reason": normalized_reason,
            "agent_id": normalized_agent_id,
            "requested_evidence": normalized_requested_evidence,
        },
        fallback_message=(
            "The final claim decision could not be saved in AWS."
        ),
    )
