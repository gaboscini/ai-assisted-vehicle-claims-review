import unittest
from pathlib import Path

from scripts.initialize_database import initialize_database
from services.agent_claim_service import (
    get_agent_claim,
    list_agent_claims,
)
from services.claim_submission_service import (
    ClaimUpload,
    submit_claim,
)
from tests.test_support import (
    create_runtime_directory,
    remove_runtime_directory,
)


class AgentClaimServiceTests(unittest.TestCase):
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

    def submit_test_claim(self) -> str:
        claim_id = "CLM-DEMO-AGENT001"
        submit_claim(
            claim_record={
                "claim_id": claim_id,
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
                ClaimUpload("ktp", "ktp.png", b"ktp"),
                ClaimUpload("sim", "sim.png", b"sim"),
                ClaimUpload("stnk", "stnk.png", b"stnk"),
                ClaimUpload(
                    "vehicle_image",
                    "context.jpg",
                    b"context",
                    "full_context",
                ),
                ClaimUpload(
                    "vehicle_image",
                    "closeup.jpg",
                    b"closeup",
                    "damage_closeup",
                ),
                ClaimUpload(
                    "vehicle_image",
                    "alternate.jpg",
                    b"alternate",
                    "alternate_angle",
                ),
            ],
            database_path=self.database_path,
            claim_files_root=self.claim_files_root,
        )
        return claim_id

    def test_list_claims_returns_submitted_claim(self) -> None:
        claim_id = self.submit_test_claim()

        claims = list_agent_claims(self.database_path)

        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].claim_id, claim_id)
        self.assertEqual(claims[0].claimant_name, "Alex Rivera")
        self.assertEqual(claims[0].policy_number, "POL-DEMO-000001")
        self.assertEqual(claims[0].claim_status, "SUBMITTED")

    def test_get_claim_returns_details_and_evidence_paths(self) -> None:
        claim_id = self.submit_test_claim()

        claim = get_agent_claim(
            claim_id,
            database_path=self.database_path,
            claim_files_root=self.claim_files_root,
        )

        self.assertIsNotNone(claim)
        assert claim is not None
        self.assertEqual(claim.phone_number, "5550101001")
        self.assertEqual(claim.incident_location, "Example City")
        self.assertEqual(len(claim.files), 6)
        self.assertEqual(
            {item.evidence_type for item in claim.files},
            {"ktp", "sim", "stnk", "vehicle_image"},
        )
        self.assertTrue(all(item.absolute_path.is_file() for item in claim.files))

    def test_missing_claim_returns_none(self) -> None:
        self.assertIsNone(
            get_agent_claim(
                "CLM-DEMO-DOES-NOT-EXIST",
                database_path=self.database_path,
                claim_files_root=self.claim_files_root,
            )
        )

    def test_missing_database_returns_empty_list(self) -> None:
        missing_database = self.root / "missing.db"
        self.assertEqual(list_agent_claims(missing_database), [])


if __name__ == "__main__":
    unittest.main()
