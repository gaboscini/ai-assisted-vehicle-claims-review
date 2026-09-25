import hashlib
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path

from scripts.initialize_database import initialize_database
from services.claim_submission_service import (
    ClaimUpload,
    submit_claim,
)
from tests.test_support import (
    create_runtime_directory,
    remove_runtime_directory,
)


class ClaimSubmissionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = create_runtime_directory()
        self.database_path = self.root / "claims_demo.db"
        self.claim_files_root = self.root / "claim_files"
        initialize_database(
            self.database_path,
            verbose=False,
        )

    def tearDown(self) -> None:
        remove_runtime_directory(self.root)

    @staticmethod
    def claim_record(claim_id: str = "CLM-DEMO-TEST0001") -> dict:
        return {
            "claim_id": claim_id,
            "policy_number": "POL-DEMO-000001",
            "customer_id": "CUS-DEMO-000001",
            "customer_name": "Alex Rivera",
            "submitted_claimant_name": "Alex Rivera",
            "incident_date": "2026-07-18",
            "incident_location": "Example City",
            "damage_description": "Front bumper damage",
        }

    @staticmethod
    def required_uploads(extension: str = ".png") -> list[ClaimUpload]:
        return [
            ClaimUpload("ktp", f"identity{extension}", b"ktp-image"),
            ClaimUpload("sim", "licence.png", b"sim-image"),
            ClaimUpload("stnk", "registration.png", b"stnk-image"),
            ClaimUpload(
                "vehicle_image",
                "context.jpg",
                b"context-image",
                "full_context",
            ),
            ClaimUpload(
                "vehicle_image",
                "damage.jpg",
                b"damage-image",
                "damage_closeup",
            ),
            ClaimUpload(
                "vehicle_image",
                "alternate.jpeg",
                b"alternate-image",
                "alternate_angle",
            ),
        ]

    def test_submission_saves_claim_and_required_files_without_assessment(self) -> None:
        uploads = self.required_uploads()

        result = submit_claim(
            claim_record=self.claim_record(),
            phone_number="5550101001",
            email_address="customer@example.com",
            claim_category="Partial loss (vehicle damage)",
            uploads=uploads,
            database_path=self.database_path,
            claim_files_root=self.claim_files_root,
        )

        self.assertEqual(result.claim_id, "CLM-DEMO-TEST0001")
        self.assertEqual(result.claim_status, "SUBMITTED")
        self.assertEqual(result.stored_file_count, 6)

        with closing(sqlite3.connect(self.database_path)) as connection:
            claim = connection.execute(
                """
                SELECT claim_status, phone_number, customer_message
                FROM claims
                WHERE claim_id = ?
                """,
                (result.claim_id,),
            ).fetchone()
            stored_files = connection.execute(
                """
                SELECT original_filename, stored_filename, relative_path,
                       file_size_bytes, sha256
                FROM claim_files
                WHERE claim_id = ?
                ORDER BY file_id
                """,
                (result.claim_id,),
            ).fetchall()
            assessment_count = connection.execute(
                "SELECT COUNT(*) FROM assessments WHERE claim_id = ?",
                (result.claim_id,),
            ).fetchone()[0]

        self.assertEqual(claim[0], "SUBMITTED")
        self.assertEqual(claim[1], "5550101001")
        self.assertIn("pending initial review", claim[2])
        self.assertEqual(len(stored_files), 6)
        self.assertEqual(assessment_count, 0)

        first_file = stored_files[0]
        self.assertEqual(first_file[0], "identity.png")
        self.assertEqual(first_file[3], len(b"ktp-image"))
        self.assertEqual(
            first_file[4],
            hashlib.sha256(b"ktp-image").hexdigest(),
        )
        self.assertTrue(
            (self.claim_files_root / first_file[2]).is_file()
        )

    def test_submission_rejects_unsupported_file_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "only PNG, JPG, and JPEG"):
            submit_claim(
                claim_record=self.claim_record("CLM-DEMO-TEST0002"),
                phone_number="5550101001",
                email_address="",
                claim_category="Partial loss (vehicle damage)",
                uploads=self.required_uploads(extension=".pdf"),
                database_path=self.database_path,
                claim_files_root=self.claim_files_root,
            )

        self.assertFalse(
            (self.claim_files_root / "CLM-DEMO-TEST0002").exists()
        )

    def test_submission_generates_claim_id_when_missing(self) -> None:
        claim_record = self.claim_record()
        claim_record.pop("claim_id")

        result = submit_claim(
            claim_record=claim_record,
            phone_number="5550101001",
            email_address="",
            claim_category="Partial loss (vehicle damage)",
            uploads=self.required_uploads(),
            database_path=self.database_path,
            claim_files_root=self.claim_files_root,
        )

        self.assertRegex(result.claim_id, r"^CLM-DEMO-[A-F0-9]{8}$")
        self.assertTrue(
            (self.claim_files_root / result.claim_id).is_dir()
        )

    def test_submission_requires_one_primary_vehicle_photo(self) -> None:
        uploads = [
            upload
            for upload in self.required_uploads()
            if upload.evidence_type != "vehicle_image"
        ]

        with self.assertRaisesRegex(ValueError, "primary vehicle damage photo"):
            submit_claim(
                claim_record=self.claim_record("CLM-DEMO-TEST0003"),
                phone_number="5550101001",
                email_address="",
                claim_category="Partial loss (vehicle damage)",
                uploads=uploads,
                database_path=self.database_path,
                claim_files_root=self.claim_files_root,
            )


if __name__ == "__main__":
    unittest.main()
