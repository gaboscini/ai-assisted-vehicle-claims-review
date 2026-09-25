import hashlib
import re
import shutil
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from scripts.initialize_database import (
    DATABASE_PATH,
    create_tables,
)
from services.claim_record_service import generate_claim_id


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLAIM_FILES_ROOT = PROJECT_ROOT / "data" / "claim_files"
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg"}
MAXIMUM_FILE_SIZE_BYTES = 10 * 1024 * 1024
REQUIRED_EVIDENCE = {
    ("ktp", None),
    ("sim", None),
    ("stnk", None),
}
PRIMARY_IMAGE_SLOTS = {
    "primary_damage",
    "damage_closeup",
    "full_context",
}


@dataclass(frozen=True)
class ClaimUpload:
    evidence_type: str
    original_filename: str
    content: bytes
    image_slot: str | None = None


@dataclass(frozen=True)
class ClaimSubmissionResult:
    claim_id: str
    claim_status: str
    customer_message: str
    stored_file_count: int


def _safe_component(value: str) -> str:
    normalized = re.sub(
        r"[^a-z0-9_-]+",
        "_",
        value.casefold(),
    ).strip("_")

    return normalized or "file"


def _validate_upload(upload: ClaimUpload) -> str:
    extension = Path(upload.original_filename).suffix.casefold()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"{upload.original_filename}: only PNG, JPG, and JPEG files are supported."
        )

    if not upload.content:
        raise ValueError(
            f"{upload.original_filename}: the uploaded file is empty."
        )

    if len(upload.content) > MAXIMUM_FILE_SIZE_BYTES:
        raise ValueError(
            f"{upload.original_filename}: the file is larger than 10 MB."
        )

    if upload.evidence_type == "vehicle_image" and not upload.image_slot:
        raise ValueError("Every vehicle image must have an image slot.")

    return extension


def validate_claim_upload(upload: ClaimUpload) -> str:
    return _validate_upload(upload)


def _validate_required_uploads(uploads: list[ClaimUpload]) -> None:
    submitted_evidence = {
        (upload.evidence_type, upload.image_slot)
        for upload in uploads
    }
    missing = REQUIRED_EVIDENCE - submitted_evidence

    if missing:
        missing_names = [
            image_slot or evidence_type.upper()
            for evidence_type, image_slot in sorted(
                missing,
                key=lambda value: (value[0], value[1] or ""),
            )
        ]
        raise ValueError(
            "Missing required evidence: "
            + ", ".join(missing_names)
            + "."
        )

    primary_images = [
        upload
        for upload in uploads
        if upload.evidence_type == "vehicle_image"
        and upload.image_slot in PRIMARY_IMAGE_SLOTS
    ]
    if not primary_images:
        raise ValueError("Missing required evidence: primary vehicle damage photo.")


def _build_stored_filename(
    upload: ClaimUpload,
    extension: str,
) -> str:
    name = (
        upload.image_slot
        if upload.evidence_type == "vehicle_image"
        else upload.evidence_type
    )
    return f"{_safe_component(name or 'file')}{extension}"


def build_stored_filename(
    upload: ClaimUpload,
    extension: str,
) -> str:
    return _build_stored_filename(upload, extension)


def submit_claim(
    *,
    claim_record: dict,
    phone_number: str,
    email_address: str,
    claim_category: str,
    uploads: list[ClaimUpload],
    database_path: Path = DATABASE_PATH,
    claim_files_root: Path = CLAIM_FILES_ROOT,
) -> ClaimSubmissionResult:
    if not uploads:
        raise ValueError("At least one uploaded file is required.")

    _validate_required_uploads(uploads)
    validated_uploads = [
        (upload, _validate_upload(upload))
        for upload in uploads
    ]

    claim_id = str(
        claim_record.get("claim_id")
        or generate_claim_id()
    )
    claim_directory = claim_files_root / claim_id

    if claim_directory.exists():
        raise ValueError(
            f"Claim {claim_id} has already been submitted."
        )

    customer_message = (
        "Your claim has been received and is pending initial review."
    )
    uploaded_at = datetime.now(timezone.utc).isoformat()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    claim_directory.mkdir(parents=True, exist_ok=False)

    try:
        with closing(sqlite3.connect(database_path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            create_tables(connection=connection)

            connection.execute(
                """
                INSERT INTO claims (
                    claim_id,
                    policy_number,
                    customer_id,
                    claimant_name,
                    phone_number,
                    email_address,
                    claim_category,
                    incident_date,
                    incident_location,
                    damage_description,
                    claim_status,
                    processing_stage,
                    customer_message,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim_id,
                    claim_record["policy_number"],
                    claim_record.get("customer_id"),
                    claim_record.get("submitted_claimant_name")
                    or claim_record.get("customer_name"),
                    phone_number.strip(),
                    email_address.strip() or None,
                    claim_category,
                    claim_record["incident_date"],
                    claim_record["incident_location"],
                    claim_record["damage_description"],
                    "SUBMITTED",
                    "DOCUMENT_QUEUED",
                    customer_message,
                    uploaded_at,
                ),
            )

            for upload, extension in validated_uploads:
                stored_filename = _build_stored_filename(
                    upload,
                    extension,
                )
                file_path = claim_directory / stored_filename
                file_path.write_bytes(upload.content)
                sha256 = hashlib.sha256(upload.content).hexdigest()
                relative_path = str(
                    Path(claim_id) / stored_filename
                ).replace("\\", "/")

                connection.execute(
                    """
                    INSERT INTO claim_files (
                        claim_id,
                        evidence_type,
                        image_slot,
                        original_filename,
                        stored_filename,
                        relative_path,
                        file_extension,
                        file_size_bytes,
                        sha256,
                        uploaded_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        claim_id,
                        upload.evidence_type,
                        upload.image_slot,
                        Path(upload.original_filename).name,
                        stored_filename,
                        relative_path,
                        extension,
                        len(upload.content),
                        sha256,
                        uploaded_at,
                    ),
                )

            connection.commit()
    except Exception:
        shutil.rmtree(claim_directory, ignore_errors=True)
        raise

    return ClaimSubmissionResult(
        claim_id=claim_id,
        claim_status="SUBMITTED",
        customer_message=customer_message,
        stored_file_count=len(validated_uploads),
    )
