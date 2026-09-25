import unittest
from dataclasses import dataclass
from unittest.mock import patch

from services.aws_claim_service import upload_aws_replacement_evidence


@dataclass
class FakeUpload:
    evidence_type: str
    original_filename: str
    content: bytes
    image_slot: str | None = None


class FakeS3Client:
    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.deletions: list[dict] = []

    def put_object(self, **kwargs):
        self.requests.append(kwargs)
        return {}

    def delete_object(self, **kwargs):
        self.deletions.append(kwargs)
        return {}


class FakeSession:
    def __init__(self, s3_client: FakeS3Client) -> None:
        self.s3_client = s3_client

    def client(self, service_name: str):
        if service_name != "s3":
            raise AssertionError(f"Unexpected service: {service_name}")
        return self.s3_client


class AwsClaimServiceTests(unittest.TestCase):
    def test_replacement_documents_are_uploaded_to_existing_claim_prefix(self):
        s3_client = FakeS3Client()
        session = FakeSession(s3_client)
        uploads = [
            FakeUpload(
                evidence_type="ktp",
                original_filename="replacement.png",
                content=b"image",
            )
        ]

        with patch(
            "services.aws_claim_service.get_aws_session",
            return_value=session,
        ):
            keys = upload_aws_replacement_evidence(
                claim_id="clm-demo-aws-test",
                uploads=uploads,
            )

        expected_key = (
            "claims-demo/ingestion/document-claims/"
            "CLM-DEMO-AWS-TEST/ktp.png"
        )
        self.assertEqual(keys, {"ktp": expected_key})
        self.assertEqual(s3_client.requests[0]["Key"], expected_key)
        self.assertEqual(
            s3_client.requests[0]["ContentType"],
            "image/png",
        )
        self.assertEqual(
            {request["Key"] for request in s3_client.deletions},
            {
                "claims-demo/ingestion/document-claims/"
                "CLM-DEMO-AWS-TEST/ktp.jpg",
                "claims-demo/ingestion/document-claims/"
                "CLM-DEMO-AWS-TEST/ktp.jpeg",
            },
        )


if __name__ == "__main__":
    unittest.main()
