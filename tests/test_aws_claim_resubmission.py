from unittest import TestCase
from unittest.mock import MagicMock, patch

from services.aws_claim_service import (
    prepare_aws_claim_resubmission,
)


class AwsClaimResubmissionTests(TestCase):
    def _session_with_updated_item(self) -> tuple[MagicMock, MagicMock]:
        session = MagicMock()
        table = session.resource.return_value.Table.return_value
        table.update_item.return_value = {
            "Attributes": {"claim_id": "CLM-DEMO-TEST"}
        }
        return session, table

    @patch("services.aws_claim_service._archive_validation_result")
    @patch("services.aws_claim_service.get_aws_claim_status")
    @patch("services.aws_claim_service.get_aws_session")
    def test_document_replacement_returns_to_document_processing(
        self,
        get_session: MagicMock,
        get_status: MagicMock,
        archive_result: MagicMock,
    ) -> None:
        session, table = self._session_with_updated_item()
        get_session.return_value = session
        get_status.return_value = {
            "claim_id": "CLM-DEMO-TEST",
            "requested_evidence": ["ktp"],
            "document_validation_result_s3_uri": (
                "s3://example-claims-bucket/document-result.json"
            ),
        }
        archive_result.return_value = None

        result = prepare_aws_claim_resubmission(
            "clm-demo-test",
            replaced_evidence=["ktp"],
        )

        self.assertTrue(result["document_replaced"])
        self.assertFalse(result["vehicle_replaced"])
        update = table.update_item.call_args.kwargs
        self.assertIn(
            "DOCUMENT_RESUBMITTED",
            update["ExpressionAttributeValues"].values(),
        )
        self.assertIn(
            "START_DOCUMENT_PROCESSING",
            update["ExpressionAttributeValues"].values(),
        )

    @patch("services.aws_claim_service._archive_validation_result")
    @patch("services.aws_claim_service.get_aws_claim_status")
    @patch("services.aws_claim_service.get_aws_session")
    def test_vehicle_replacement_returns_to_image_processing(
        self,
        get_session: MagicMock,
        get_status: MagicMock,
        archive_result: MagicMock,
    ) -> None:
        session, table = self._session_with_updated_item()
        get_session.return_value = session
        get_status.return_value = {
            "claim_id": "CLM-DEMO-TEST",
            "requested_evidence": ["primary_damage"],
            "image_validation_result_s3_uri": (
                "s3://example-claims-bucket/image-result.json"
            ),
        }
        archive_result.return_value = None

        result = prepare_aws_claim_resubmission(
            "CLM-DEMO-TEST",
            replaced_evidence=["primary_damage"],
        )

        self.assertFalse(result["document_replaced"])
        self.assertTrue(result["vehicle_replaced"])
        update = table.update_item.call_args.kwargs
        self.assertIn(
            "IMAGE_RESUBMITTED",
            update["ExpressionAttributeValues"].values(),
        )
        self.assertIn(
            "START_IMAGE_ASSESSMENT",
            update["ExpressionAttributeValues"].values(),
        )

    @patch("services.aws_claim_service.get_aws_claim_status")
    def test_replacement_must_match_requested_evidence(
        self,
        get_status: MagicMock,
    ) -> None:
        get_status.return_value = {
            "claim_id": "CLM-DEMO-TEST",
            "requested_evidence": ["ktp", "sim"],
        }

        with self.assertRaisesRegex(
            ValueError,
            "Replacement evidence does not match",
        ):
            prepare_aws_claim_resubmission(
                "CLM-DEMO-TEST",
                replaced_evidence=["ktp"],
            )
