from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from scripts.initialize_database import DATABASE_PATH
from services.claim_submission_service import (
    CLAIM_FILES_ROOT,
    ClaimUpload,
    build_stored_filename,
    validate_claim_upload,
)


ACTION_STATUS = {
    "APPROVE": "APPROVED",
    "REJECT": "REJECTED",
    "REQUEST_MORE_INFORMATION": "NEEDS_INFORMATION",
    "INVESTIGATE": "INVESTIGATION",
}

EVIDENCE_LABELS = {
    "ktp": "KTP identity document",
    "sim": "SIM driver licence",
    "stnk": "STNK vehicle registration",
    "primary_damage": "Primary vehicle damage photo",
    "full_context": "Full vehicle and context photo",
    "damage_closeup": "Damage close-up",
    "alternate_angle": "Alternate damage angle",
    "additional_1": "Additional photo 1",
    "additional_2": "Additional photo 2",
}


@dataclass(frozen=True)
class CustomerClaimStatus:
    claim_id: str
    policy_number: str
    claimant_name: str
    incident_date: str
    incident_location: str
    claim_status: str
    customer_message: str
    requested_evidence: tuple[str, ...]
    updated_at: str


def _normalize_requested_evidence(values: list[str] | None) -> list[str]:
    normalized = list(dict.fromkeys(values or []))
    unknown = set(normalized) - EVIDENCE_LABELS.keys()
    if unknown:
        raise ValueError(
            "Unknown evidence request: " + ", ".join(sorted(unknown))
        )
    return normalized


def _customer_message(
    *,
    action: str,
    reason: str,
    requested_evidence: list[str],
) -> str:
    if action == "APPROVE":
        prefix = "Your claim passed the initial claims-agent review."
    elif action == "REJECT":
        prefix = "Your claim was not approved during the initial review."
    elif action == "INVESTIGATE":
        prefix = "Your claim requires additional investigation."
    else:
        labels = [EVIDENCE_LABELS[value] for value in requested_evidence]
        prefix = "Additional evidence is required: " + ", ".join(labels) + "."
    return f"{prefix} {reason.strip()}"


def save_agent_action(
    claim_id: str,
    *,
    action: str,
    reason: str,
    requested_evidence: list[str] | None = None,
    database_path: Path = DATABASE_PATH,
) -> str:
    normalized_action = action.strip().upper()
    if normalized_action not in ACTION_STATUS:
        raise ValueError("Unsupported agent action.")
    if not reason.strip():
        raise ValueError("A short reason is required.")

    requested = _normalize_requested_evidence(requested_evidence)
    if normalized_action == "REQUEST_MORE_INFORMATION" and not requested:
        raise ValueError("Select at least one item of evidence to replace.")
    if normalized_action != "REQUEST_MORE_INFORMATION":
        requested = []

    status = ACTION_STATUS[normalized_action]
    message = _customer_message(
        action=normalized_action,
        reason=reason,
        requested_evidence=requested,
    )
    timestamp = datetime.now(timezone.utc).isoformat()

    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT claim_status, processing_stage FROM claims WHERE claim_id = ?",
            (claim_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Claim {claim_id} was not found.")
        if row[0] != "READY_FOR_REVIEW":
            raise ValueError(
                f"Agent action is not allowed from status {row[0]}."
            )
        processing_stage = row[1] or "DOCUMENT_REVIEW"
        if normalized_action == "APPROVE" and processing_stage not in {
            "FINAL_REVIEW",
            "LEGACY_FINAL_REVIEW",
        }:
            raise ValueError(
                "Final approval is available only after vehicle-image assessment."
            )

        next_processing_stage = {
            "APPROVE": "COMPLETED",
            "REJECT": "COMPLETED",
            "REQUEST_MORE_INFORMATION": "WAITING_FOR_EVIDENCE",
            "INVESTIGATE": "INVESTIGATION",
        }[normalized_action]

        connection.execute(
            """
            UPDATE claims
            SET claim_status = ?,
                agent_decision = ?,
                agent_reason = ?,
                customer_message = ?,
                requested_evidence = ?,
                processing_stage = ?,
                updated_at = ?
            WHERE claim_id = ?
            """,
            (
                status,
                normalized_action,
                reason.strip(),
                message,
                json.dumps(requested),
                next_processing_stage,
                timestamp,
                claim_id,
            ),
        )
        connection.commit()

    return status


def save_document_review_decision(
    claim_id: str,
    *,
    action: str,
    reason: str,
    requested_evidence: list[str] | None = None,
    database_path: Path = DATABASE_PATH,
) -> str:
    normalized_action = action.strip().upper()
    if normalized_action not in {
        "PROCEED_TO_IMAGE_ASSESSMENT",
        "REQUEST_MORE_INFORMATION",
        "REJECT",
    }:
        raise ValueError("Unsupported document-review action.")
    if not reason.strip():
        raise ValueError("A short reason is required.")

    requested = _normalize_requested_evidence(requested_evidence)
    if normalized_action == "REQUEST_MORE_INFORMATION" and not requested:
        raise ValueError("Select at least one item of evidence to replace.")
    if normalized_action != "REQUEST_MORE_INFORMATION":
        requested = []

    if normalized_action == "PROCEED_TO_IMAGE_ASSESSMENT":
        claim_status = "READY_FOR_REVIEW"
        processing_stage = "IMAGE_QUEUED"
        agent_decision = "PROCEED_TO_IMAGE_ASSESSMENT"
        customer_message = "Your claim review is in progress."
    elif normalized_action == "REQUEST_MORE_INFORMATION":
        claim_status = "NEEDS_INFORMATION"
        processing_stage = "WAITING_FOR_EVIDENCE"
        agent_decision = "REQUEST_MORE_INFORMATION"
        labels = [EVIDENCE_LABELS[value] for value in requested]
        customer_message = (
            "Additional evidence is required: "
            + ", ".join(labels)
            + ". "
            + reason.strip()
        )
    else:
        claim_status = "REJECTED"
        processing_stage = "COMPLETED"
        agent_decision = "REJECT"
        customer_message = (
            "Your claim was not approved during the initial review. "
            + reason.strip()
        )

    timestamp = datetime.now(timezone.utc).isoformat()
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT processing_stage FROM claims WHERE claim_id = ?",
            (claim_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Claim {claim_id} was not found.")

        connection.execute(
            """
            UPDATE claims
            SET claim_status = ?,
                processing_stage = ?,
                agent_decision = ?,
                agent_reason = ?,
                customer_message = ?,
                requested_evidence = ?,
                updated_at = ?
            WHERE claim_id = ?
            """,
            (
                claim_status,
                processing_stage,
                agent_decision,
                reason.strip(),
                customer_message,
                json.dumps(requested),
                timestamp,
                claim_id,
            ),
        )
        connection.commit()

    return claim_status


def get_customer_claim_status(
    claim_id: str,
    *,
    database_path: Path = DATABASE_PATH,
) -> CustomerClaimStatus | None:
    normalized_claim_id = claim_id.strip().upper()
    if not normalized_claim_id or not database_path.exists():
        return None

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT
                claim_id,
                policy_number,
                COALESCE(claimant_name, '') AS claimant_name,
                incident_date,
                incident_location,
                claim_status,
                COALESCE(customer_message, '') AS customer_message,
                COALESCE(requested_evidence, '[]') AS requested_evidence,
                COALESCE(updated_at, created_at) AS updated_at
            FROM claims
            WHERE UPPER(claim_id) = ?
            """,
            (normalized_claim_id,),
        ).fetchone()

    if row is None:
        return None

    try:
        requested = tuple(json.loads(row["requested_evidence"]))
    except (TypeError, json.JSONDecodeError):
        requested = ()

    return CustomerClaimStatus(
        claim_id=row["claim_id"],
        policy_number=row["policy_number"],
        claimant_name=row["claimant_name"],
        incident_date=row["incident_date"],
        incident_location=row["incident_location"],
        claim_status=row["claim_status"],
        customer_message=row["customer_message"],
        requested_evidence=requested,
        updated_at=row["updated_at"],
    )


def _upload_key(upload: ClaimUpload) -> str:
    return (
        upload.image_slot
        if upload.evidence_type == "vehicle_image"
        else upload.evidence_type
    ) or ""


def _upload_for_requested_key(key: str, filename: str, content: bytes) -> ClaimUpload:
    if key in {"ktp", "sim", "stnk"}:
        return ClaimUpload(
            evidence_type=key,
            original_filename=filename,
            content=content,
        )
    return ClaimUpload(
        evidence_type="vehicle_image",
        image_slot=key,
        original_filename=filename,
        content=content,
    )


def make_replacement_upload(
    evidence_key: str,
    *,
    filename: str,
    content: bytes,
) -> ClaimUpload:
    if evidence_key not in EVIDENCE_LABELS:
        raise ValueError("Unknown evidence replacement.")
    return _upload_for_requested_key(evidence_key, filename, content)


def resubmit_claim_evidence(
    claim_id: str,
    *,
    uploads: list[ClaimUpload],
    database_path: Path = DATABASE_PATH,
    claim_files_root: Path = CLAIM_FILES_ROOT,
) -> str:
    status = get_customer_claim_status(claim_id, database_path=database_path)
    if status is None:
        raise ValueError(f"Claim {claim_id} was not found.")
    if status.claim_status != "NEEDS_INFORMATION":
        raise ValueError("This claim is not waiting for replacement evidence.")

    requested = set(status.requested_evidence)
    submitted = {_upload_key(upload) for upload in uploads}
    if submitted != requested:
        missing = requested - submitted
        extra = submitted - requested
        messages = []
        if missing:
            messages.append("missing: " + ", ".join(sorted(missing)))
        if extra:
            messages.append("not requested: " + ", ".join(sorted(extra)))
        raise ValueError("Replacement evidence does not match the request (" + "; ".join(messages) + ").")

    validated = [
        (upload, validate_claim_upload(upload))
        for upload in uploads
    ]
    claim_directory = claim_files_root / status.claim_id
    claim_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    obsolete_paths: list[Path] = []

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")

        for upload, extension in validated:
            stored_filename = build_stored_filename(upload, extension)
            destination = claim_directory / stored_filename
            destination.write_bytes(upload.content)
            relative_path = str(Path(status.claim_id) / stored_filename).replace("\\", "/")
            sha256 = hashlib.sha256(upload.content).hexdigest()

            if upload.evidence_type == "vehicle_image":
                existing = connection.execute(
                    """
                    SELECT file_id, relative_path FROM claim_files
                    WHERE claim_id = ? AND evidence_type = 'vehicle_image' AND image_slot = ?
                    LIMIT 1
                    """,
                    (status.claim_id, upload.image_slot),
                ).fetchone()
            else:
                existing = connection.execute(
                    """
                    SELECT file_id, relative_path FROM claim_files
                    WHERE claim_id = ? AND evidence_type = ?
                    LIMIT 1
                    """,
                    (status.claim_id, upload.evidence_type),
                ).fetchone()

            values = (
                upload.evidence_type,
                upload.image_slot,
                Path(upload.original_filename).name,
                stored_filename,
                relative_path,
                extension,
                len(upload.content),
                sha256,
                timestamp,
            )
            if existing:
                old_path = claim_files_root / existing["relative_path"]
                if old_path != destination:
                    obsolete_paths.append(old_path)
                connection.execute(
                    """
                    UPDATE claim_files
                    SET evidence_type = ?, image_slot = ?, original_filename = ?,
                        stored_filename = ?, relative_path = ?, file_extension = ?,
                        file_size_bytes = ?, sha256 = ?, uploaded_at = ?
                    WHERE file_id = ?
                    """,
                    values + (existing["file_id"],),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO claim_files (
                        evidence_type, image_slot, original_filename, stored_filename,
                        relative_path, file_extension, file_size_bytes, sha256,
                        uploaded_at, claim_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    values + (status.claim_id,),
                )

        connection.execute(
            "DELETE FROM assessments WHERE claim_id = ?",
            (status.claim_id,),
        )
        connection.execute(
            """
            UPDATE claims
            SET claim_status = 'SUBMITTED',
                processing_stage = 'DOCUMENT_QUEUED',
                agent_decision = NULL,
                agent_reason = NULL,
                requested_evidence = NULL,
                customer_message = ?,
                updated_at = ?
            WHERE claim_id = ?
            """,
            (
                "Your replacement evidence was received and is waiting for a claims agent to review it.",
                timestamp,
                status.claim_id,
            ),
        )
        connection.commit()

    for obsolete_path in obsolete_paths:
        if obsolete_path.is_file():
            obsolete_path.unlink()

    return "SUBMITTED"
