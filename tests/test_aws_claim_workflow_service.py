import io
import json
import unittest
from unittest.mock import patch

from services.aws_claim_workflow_service import (
    submit_agent_document_decision,
    submit_agent_final_decision,
)


class FakeLambdaClient:
    def __init__(self) -> None:
        self.invocation = None

    def invoke(self, **kwargs):
        self.invocation = kwargs
        return {
            "StatusCode": 200,
            "Payload": io.BytesIO(
                json.dumps(
                    {
                        "statusCode": 202,
                        "body": json.dumps(
                            {
                                "claim_id": "CLM-DEMO-AWS-TEST",
                                "decision": "APPROVED",
                            }
                        ),
                    }
                ).encode("utf-8")
            ),
        }


class FakeSession:
    def __init__(self, lambda_client: FakeLambdaClient) -> None:
        self.lambda_client = lambda_client

    def client(self, service_name: str):
        if service_name != "lambda":
            raise AssertionError(f"Unexpected service: {service_name}")
        return self.lambda_client


class AwsClaimWorkflowServiceTests(unittest.TestCase):
    def test_submit_agent_document_decision_invokes_approval_lambda(self) -> None:
        lambda_client = FakeLambdaClient()
        session = FakeSession(lambda_client)

        with patch(
            "services.aws_claim_workflow_service.get_aws_session",
            return_value=session,
        ):
            result = submit_agent_document_decision(
                "clm-demo-aws-test",
                decision="approve",
                reason="Documents reviewed.",
                agent_id="test-agent",
            )

        self.assertEqual(result["status_code"], 202)
        self.assertEqual(
            lambda_client.invocation["FunctionName"],
            "example-agent-document-approval",
        )
        self.assertEqual(
            lambda_client.invocation["InvocationType"],
            "RequestResponse",
        )
        payload = json.loads(
            lambda_client.invocation["Payload"].decode("utf-8")
        )
        self.assertEqual(payload["claim_id"], "CLM-DEMO-AWS-TEST")
        self.assertEqual(payload["action_type"], "DOCUMENT_DECISION")
        self.assertEqual(payload["decision"], "APPROVE")
        self.assertEqual(payload["agent_id"], "test-agent")

    def test_submit_agent_final_decision_invokes_same_lambda(self) -> None:
        lambda_client = FakeLambdaClient()
        session = FakeSession(lambda_client)

        with patch(
            "services.aws_claim_workflow_service.get_aws_session",
            return_value=session,
        ):
            result = submit_agent_final_decision(
                "clm-demo-aws-test",
                decision="approve",
                reason="Evidence reviewed.",
                agent_id="test-agent",
            )

        self.assertEqual(result["status_code"], 202)
        self.assertEqual(
            lambda_client.invocation["FunctionName"],
            "example-agent-document-approval",
        )
        payload = json.loads(
            lambda_client.invocation["Payload"].decode("utf-8")
        )
        self.assertEqual(payload["action_type"], "FINAL_DECISION")
        self.assertEqual(payload["decision"], "APPROVE")
        self.assertEqual(payload["reason"], "Evidence reviewed.")

    def test_blank_reason_uses_a_default_audit_note(self) -> None:
        lambda_client = FakeLambdaClient()
        session = FakeSession(lambda_client)

        with patch(
            "services.aws_claim_workflow_service.get_aws_session",
            return_value=session,
        ):
            submit_agent_final_decision(
                "clm-demo-aws-test",
                decision="investigate",
                reason="",
                agent_id="test-agent",
            )

        payload = json.loads(
            lambda_client.invocation["Payload"].decode("utf-8")
        )
        self.assertEqual(payload["decision"], "INVESTIGATE")
        self.assertEqual(
            payload["reason"],
            "The claim was marked for additional investigation.",
        )

    def test_more_information_requires_replacement_evidence(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "at least one item",
        ):
            submit_agent_document_decision(
                "clm-demo-aws-test",
                decision="request_more_information",
                reason="",
                requested_evidence=[],
            )


if __name__ == "__main__":
    unittest.main()
