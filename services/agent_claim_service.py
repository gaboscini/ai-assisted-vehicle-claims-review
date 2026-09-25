import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from scripts.initialize_database import DATABASE_PATH
from services.claim_submission_service import CLAIM_FILES_ROOT


@dataclass(frozen=True)
class AgentClaimSummary:
    claim_id: str
    claimant_name: str
    policy_number: str
    incident_date: str
    claim_status: str
    processing_stage: str
    created_at: str


@dataclass(frozen=True)
class AgentClaimFile:
    file_id: int
    evidence_type: str
    image_slot: str | None
    original_filename: str
    stored_filename: str
    relative_path: str
    file_extension: str
    file_size_bytes: int
    sha256: str
    uploaded_at: str
    absolute_path: Path


@dataclass(frozen=True)
class AgentClaimDetail:
    claim_id: str
    policy_number: str
    customer_id: str | None
    claimant_name: str
    phone_number: str
    email_address: str | None
    claim_category: str
    incident_date: str
    incident_location: str
    damage_description: str
    claim_status: str
    processing_stage: str
    customer_message: str | None
    agent_decision: str | None
    agent_reason: str | None
    requested_evidence: str | None
    created_at: str
    files: tuple[AgentClaimFile, ...]


def list_agent_claims(
    database_path: Path = DATABASE_PATH,
) -> list[AgentClaimSummary]:
    if not database_path.exists():
        return []

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT
                claim_id,
                COALESCE(claimant_name, '') AS claimant_name,
                policy_number,
                incident_date,
                claim_status,
                COALESCE(processing_stage, 'DOCUMENT_QUEUED') AS processing_stage,
                created_at
            FROM claims
            ORDER BY created_at DESC, claim_id DESC
            """
        ).fetchall()

    return [
        AgentClaimSummary(
            claim_id=row["claim_id"],
            claimant_name=row["claimant_name"],
            policy_number=row["policy_number"],
            incident_date=row["incident_date"],
            claim_status=row["claim_status"],
            processing_stage=row["processing_stage"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


def get_agent_claim(
    claim_id: str,
    *,
    database_path: Path = DATABASE_PATH,
    claim_files_root: Path = CLAIM_FILES_ROOT,
) -> AgentClaimDetail | None:
    if not database_path.exists():
        return None

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        claim_row = connection.execute(
            """
            SELECT
                claim_id,
                policy_number,
                customer_id,
                COALESCE(claimant_name, '') AS claimant_name,
                COALESCE(phone_number, '') AS phone_number,
                email_address,
                COALESCE(claim_category, '') AS claim_category,
                incident_date,
                incident_location,
                damage_description,
                claim_status,
                COALESCE(processing_stage, 'DOCUMENT_QUEUED') AS processing_stage,
                customer_message,
                agent_decision,
                agent_reason,
                requested_evidence,
                created_at
            FROM claims
            WHERE claim_id = ?
            """,
            (claim_id,),
        ).fetchone()

        if claim_row is None:
            return None

        file_rows = connection.execute(
            """
            SELECT
                file_id,
                evidence_type,
                image_slot,
                original_filename,
                stored_filename,
                relative_path,
                file_extension,
                file_size_bytes,
                sha256,
                uploaded_at
            FROM claim_files
            WHERE claim_id = ?
            ORDER BY
                CASE evidence_type
                    WHEN 'ktp' THEN 1
                    WHEN 'sim' THEN 2
                    WHEN 'stnk' THEN 3
                    ELSE 4
                END,
                file_id
            """,
            (claim_id,),
        ).fetchall()

    files = tuple(
        AgentClaimFile(
            file_id=row["file_id"],
            evidence_type=row["evidence_type"],
            image_slot=row["image_slot"],
            original_filename=row["original_filename"],
            stored_filename=row["stored_filename"],
            relative_path=row["relative_path"],
            file_extension=row["file_extension"],
            file_size_bytes=row["file_size_bytes"],
            sha256=row["sha256"],
            uploaded_at=row["uploaded_at"],
            absolute_path=claim_files_root / row["relative_path"],
        )
        for row in file_rows
    )

    return AgentClaimDetail(
        claim_id=claim_row["claim_id"],
        policy_number=claim_row["policy_number"],
        customer_id=claim_row["customer_id"],
        claimant_name=claim_row["claimant_name"],
        phone_number=claim_row["phone_number"],
        email_address=claim_row["email_address"],
        claim_category=claim_row["claim_category"],
        incident_date=claim_row["incident_date"],
        incident_location=claim_row["incident_location"],
        damage_description=claim_row["damage_description"],
        claim_status=claim_row["claim_status"],
        processing_stage=claim_row["processing_stage"],
        customer_message=claim_row["customer_message"],
        agent_decision=claim_row["agent_decision"],
        agent_reason=claim_row["agent_reason"],
        requested_evidence=claim_row["requested_evidence"],
        created_at=claim_row["created_at"],
        files=files,
    )
