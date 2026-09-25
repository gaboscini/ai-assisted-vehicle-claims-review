import hashlib
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path

from scripts.initialize_database import initialize_database
from services.claim_submission_service import ClaimUpload, submit_claim
from services.claim_workflow_service import (
    get_customer_claim_status,
    make_replacement_upload,
    resubmit_claim_evidence,
    save_agent_action,
    save_document_review_decision,
)
from tests.test_support import (
    create_runtime_directory,
    remove_runtime_directory,
)


class ClaimWorkflowServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = create_runtime_directory()
        self.database_path = self.root / "claims_demo.db"
        self.claim_files_root = self.root / "claim_files"
        initialize_database(self.database_path, verbose=False)
        self.claim_id = "CLM-DEMO-WORKFLOW"
        submit_claim(
            claim_record={
                "claim_id": self.claim_id,
                "policy_number": "POL-DEMO-000001",
                "customer_id": "CUS-DEMO-000001",
                "customer_name": "Alex Rivera",
                "submitted_claimant_name": "Alex Rivera",
                "incident_date": "2026-07-18",
                "incident_location": "Example City",
                "damage_description": "Front bumper damage",
            },
            phone_number="5550101001",
            email_address="customer@example.com",
            claim_category="Partial loss (vehicle damage)",
            uploads=[
                ClaimUpload("ktp", "ktp.png", b"original-ktp"),
                ClaimUpload("sim", "sim.png", b"original-sim"),
                ClaimUpload("stnk", "stnk.png", b"original-stnk"),
                ClaimUpload("vehicle_image", "context.jpg", b"context", "full_context"),
                ClaimUpload("vehicle_image", "closeup.jpg", b"closeup", "damage_closeup"),
                ClaimUpload("vehicle_image", "alternate.jpg", b"alternate", "alternate_angle"),
            ],
            database_path=self.database_path,
            claim_files_root=self.claim_files_root,
        )
        self.mark_ready_for_review()

    def tearDown(self) -> None:
        remove_runtime_directory(self.root)

    def mark_ready_for_review(self) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                """
                UPDATE claims
                SET claim_status = 'READY_FOR_REVIEW',
                    processing_stage = 'LEGACY_FINAL_REVIEW'
                WHERE claim_id = ?
                """,
                (self.claim_id,),
            )
            connection.execute(
                """
                INSERT INTO assessments (claim_id, assessment_type, result_json)
                VALUES (?, 'claim_pre_assessment', '{}')
                """,
                (self.claim_id,),
            )
            connection.commit()

    def claim_row(self) -> sqlite3.Row:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            return connection.execute(
                "SELECT * FROM claims WHERE claim_id = ?",
                (self.claim_id,),
            ).fetchone()

    def test_approve_saves_final_status_reason_and_customer_message(self) -> None:
        status = save_agent_action(
            self.claim_id,
            action="APPROVE",
            reason="The submitted evidence passed the initial review.",
            database_path=self.database_path,
        )

        row = self.claim_row()
        customer = get_customer_claim_status(
            self.claim_id,
            database_path=self.database_path,
        )
        self.assertEqual(status, "APPROVED")
        self.assertEqual(row["agent_decision"], "APPROVE")
        self.assertIn("passed", row["agent_reason"])
        self.assertEqual(customer.claim_status, "APPROVED")
        self.assertIn("passed the initial", customer.customer_message)

    def test_reject_and_investigate_map_to_customer_statuses(self) -> None:
        status = save_agent_action(
            self.claim_id,
            action="REJECT",
            reason="The submitted evidence does not support this claim.",
            database_path=self.database_path,
        )
        self.assertEqual(status, "REJECTED")

        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                "UPDATE claims SET claim_status = 'READY_FOR_REVIEW' WHERE claim_id = ?",
                (self.claim_id,),
            )
            connection.commit()

        status = save_agent_action(
            self.claim_id,
            action="INVESTIGATE",
            reason="The evidence requires specialist verification.",
            database_path=self.database_path,
        )
        self.assertEqual(status, "INVESTIGATION")

    def test_request_information_requires_requested_evidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one"):
            save_agent_action(
                self.claim_id,
                action="REQUEST_MORE_INFORMATION",
                reason="A clearer image is required.",
                database_path=self.database_path,
            )

    def test_aws_document_approval_moves_local_claim_to_image_queue(self) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                """
                UPDATE claims
                SET claim_status = 'SUBMITTED',
                    processing_stage = 'DOCUMENT_QUEUED',
                    agent_decision = NULL
                WHERE claim_id = ?
                """,
                (self.claim_id,),
            )
            connection.commit()

        status = save_document_review_decision(
            self.claim_id,
            action="PROCEED_TO_IMAGE_ASSESSMENT",
            reason="The AWS document assessment was reviewed and accepted.",
            database_path=self.database_path,
        )

        row = self.claim_row()
        self.assertEqual(status, "READY_FOR_REVIEW")
        self.assertEqual(row["processing_stage"], "IMAGE_QUEUED")
        self.assertEqual(
            row["agent_decision"],
            "PROCEED_TO_IMAGE_ASSESSMENT",
        )

    def test_customer_resubmission_replaces_files_and_returns_to_submitted(self) -> None:
        save_agent_action(
            self.claim_id,
            action="REQUEST_MORE_INFORMATION",
            reason="Upload a clearer identity document and damage close-up.",
            requested_evidence=["ktp", "damage_closeup"],
            database_path=self.database_path,
        )
        customer = get_customer_claim_status(
            self.claim_id,
            database_path=self.database_path,
        )
        self.assertEqual(customer.claim_status, "NEEDS_INFORMATION")
        self.assertEqual(
            customer.requested_evidence,
            ("ktp", "damage_closeup"),
        )

        replacement_ktp = b"replacement-ktp"
        replacement_damage = b"replacement-damage"
        status = resubmit_claim_evidence(
            self.claim_id,
            uploads=[
                make_replacement_upload(
                    "ktp",
                    filename="clear_ktp.jpg",
                    content=replacement_ktp,
                ),
                make_replacement_upload(
                    "damage_closeup",
                    filename="clear_damage.png",
                    content=replacement_damage,
                ),
            ],
            database_path=self.database_path,
            claim_files_root=self.claim_files_root,
        )

        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            files = connection.execute(
                """
                SELECT evidence_type, image_slot, relative_path, sha256
                FROM claim_files
                WHERE claim_id = ? AND (
                    evidence_type = 'ktp' OR image_slot = 'damage_closeup'
                )
                ORDER BY evidence_type
                """,
                (self.claim_id,),
            ).fetchall()
            assessment_count = connection.execute(
                "SELECT COUNT(*) FROM assessments WHERE claim_id = ?",
                (self.claim_id,),
            ).fetchone()[0]

        row = self.claim_row()
        self.assertEqual(status, "SUBMITTED")
        self.assertEqual(row["claim_status"], "SUBMITTED")
        self.assertIsNone(row["agent_decision"])
        self.assertIsNone(row["requested_evidence"])
        self.assertEqual(assessment_count, 0)
        hashes = {item["sha256"] for item in files}
        self.assertEqual(
            hashes,
            {
                hashlib.sha256(replacement_ktp).hexdigest(),
                hashlib.sha256(replacement_damage).hexdigest(),
            },
        )
        self.assertTrue(
            all(
                (self.claim_files_root / item["relative_path"]).is_file()
                for item in files
            )
        )
        self.assertFalse(
            (self.claim_files_root / self.claim_id / "ktp.png").exists()
        )

    def test_resubmission_must_match_requested_items(self) -> None:
        save_agent_action(
            self.claim_id,
            action="REQUEST_MORE_INFORMATION",
            reason="Upload a clearer KTP.",
            requested_evidence=["ktp"],
            database_path=self.database_path,
        )

        with self.assertRaisesRegex(ValueError, "does not match"):
            resubmit_claim_evidence(
                self.claim_id,
                uploads=[
                    make_replacement_upload(
                        "sim",
                        filename="sim.png",
                        content=b"wrong-item",
                    )
                ],
                database_path=self.database_path,
                claim_files_root=self.claim_files_root,
            )


if __name__ == "__main__":
    unittest.main()
