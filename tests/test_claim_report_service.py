import unittest
from io import BytesIO
from zipfile import ZipFile

from services.claim_report_service import (
    agent_report_filename,
    build_agent_claim_assessment_report,
    build_customer_claim_report,
    customer_report_filename,
)


CLAIM_RECORD = {
    "claim_id": "CLM-DEMO-REPORT-001",
    "policy_number": "POL-DEMO-000001",
    "customer_id": "CUS-DEMO-000001",
    "customer_name": "Alex Rivera",
    "incident_date": "2026-07-28",
    "incident_location": "Example City",
    "damage_description": "Front bumper damage",
    "vehicle": {
        "plate_number": "EXAMPLE-1234",
        "year": 2022,
        "make": "Toyota",
        "model": "Avanza",
        "coverage_type": "Comprehensive",
    },
}

CLAIM_STATUS = {
    "claim_id": "CLM-DEMO-REPORT-001",
    "policy_number": "POL-DEMO-000001",
    "claim_status": "APPROVED",
    "processing_stage": "COMPLETED",
    "next_action": "NOTIFY_CUSTOMER",
    "customer_message": "Your vehicle-damage claim has been approved.",
    "updated_at": "2026-07-28T12:29:32+00:00",
}

DOCUMENT_RESULT = {
    "package_status": "valid",
    "next_action": "AWAIT_AGENT_DOCUMENT_APPROVAL",
    "threshold_profile": "provisional-bda-document-thresholds",
    "document_results": {
        "ktp": {
            "document_status": "valid",
            "document_type_confidence_score": 94.68,
            "document_type_confidence_threshold": 80,
            "field_results": [
                {
                    "field_name": "identity_number",
                    "display_name": "Identity number",
                    "extracted_value": "KTP-TEST-000001",
                    "expected_value": "KTP-TEST-000001",
                    "extraction_confidence_score": 85.5,
                    "confidence_threshold": 80,
                    "match_score": 100,
                    "status": "PASS",
                    "findings": [],
                }
            ],
            "findings": [],
        }
    },
}

IMAGE_RESULT = {
    "evidence_suitability_score": 98,
    "evidence_status": "eligible",
    "final_recommendation": "ESCALATE_FOR_REVIEW",
    "evidence_checks": [
        {
            "field": "image_type",
            "display_name": "Image type",
            "result": "real_photo",
            "expected": "real_photo",
            "confidence_score": 95,
            "confidence_threshold": 80,
            "status": "PASS",
        }
    ],
    "damage_assessment": {
        "damage_visible": True,
        "damage_location": ["front"],
        "damage_classification": ["collision_damage"],
        "damaged_parts": ["front_bumper", "grille"],
        "severity": "severe",
        "severity_confidence": 90,
        "repair_recommendation": "structural_inspection",
        "repair_recommendation_confidence": 85,
        "analyst_summary": "Severe front-end damage is visible.",
        "limitations": ["Hidden damage cannot be assessed."],
    },
}


def workbook_xml(report: bytes) -> str:
    with ZipFile(BytesIO(report)) as archive:
        return "\n".join(
            archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if name.endswith(".xml")
        )


class ClaimReportServiceTests(unittest.TestCase):
    def test_agent_report_contains_three_assessment_sheets(self):
        report = build_agent_claim_assessment_report(
            claim_id="CLM-DEMO-REPORT-001",
            claim_record=CLAIM_RECORD,
            claim_status=CLAIM_STATUS,
            document_result=DOCUMENT_RESULT,
            image_result=IMAGE_RESULT,
        )

        self.assertTrue(report.startswith(b"PK"))
        xml = workbook_xml(report)
        self.assertIn('name="Claim Summary"', xml)
        self.assertIn('name="Document Assessment"', xml)
        self.assertIn('name="Image Assessment"', xml)
        self.assertIn("Extraction confidence", xml)
        self.assertIn("Evidence suitability", xml)

    def test_customer_report_excludes_internal_assessment_fields(self):
        report = build_customer_claim_report(
            claim_id="CLM-DEMO-REPORT-001",
            claim_record=CLAIM_RECORD,
            claim_status=CLAIM_STATUS,
            display_status="Approved",
            status_message="Your vehicle-damage claim has been approved.",
        )

        self.assertTrue(report.startswith(b"PK"))
        xml = workbook_xml(report)
        self.assertIn('name="Claim Report"', xml)
        self.assertIn("Your vehicle-damage claim has been approved.", xml)
        self.assertNotIn("Extraction confidence", xml)
        self.assertNotIn("Evidence suitability", xml)
        self.assertNotIn("Synthetic-image screening", xml)

    def test_claim_text_cannot_be_written_as_an_excel_formula(self):
        record = {
            **CLAIM_RECORD,
            "damage_description": '=HYPERLINK("https://example.com")',
        }
        report = build_customer_claim_report(
            claim_id="CLM-DEMO-REPORT-001",
            claim_record=record,
            claim_status=CLAIM_STATUS,
            display_status="Approved",
            status_message="Claim approved.",
        )

        with ZipFile(BytesIO(report)) as archive:
            sheet_xml = "\n".join(
                archive.read(name).decode("utf-8")
                for name in archive.namelist()
                if name.startswith("xl/worksheets/")
                and name.endswith(".xml")
            )
        self.assertNotIn("<f>", sheet_xml)

    def test_report_filenames_are_safe_and_descriptive(self):
        self.assertEqual(
            agent_report_filename("CLM/001"),
            "CLM_001_assessment_report.xlsx",
        )
        self.assertEqual(
            customer_report_filename("CLM/001"),
            "CLM_001_claim_report.xlsx",
        )


if __name__ == "__main__":
    unittest.main()
