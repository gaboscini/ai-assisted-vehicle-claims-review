# Testing

## Test strategy

The repository separates automated unit tests from manual integration diagnostics.

### Automated tests

The automated suite exercises:

- local claim creation and evidence metadata
- workflow status changes and reviewer actions
- AWS S3 upload key construction
- Lambda invocation payloads
- replacement-evidence handling
- report generation and spreadsheet-formula protection
- DynamoDB assessment parsing through mocked clients

Run the suite from the repository root:

```powershell
python -m unittest `
  tests.test_agent_claim_service `
  tests.test_aws_claim_resubmission `
  tests.test_aws_claim_service `
  tests.test_aws_claim_workflow_service `
  tests.test_claim_report_service `
  tests.test_claim_submission_service `
  tests.test_claim_workflow_service
```

### Manual diagnostics

Scripts under `tests/manual/` exercise AWS connectivity and the optional local RAG components. They depend on local services or operator-owned AWS resources and must not be treated as automated unit tests.

## Fixtures

Document fixtures under `tests/fixtures/document_claims/` are generated mock records. They are visibly labelled as synthetic and do not represent official documents.

The public scenarios cover:

| Scenario | Expected condition |
| --- | --- |
| Valid document set | Required values are present and consistent |
| Name mismatch | Identity name conflicts with the fictional claim record |
| Expired driver licence | Licence date is invalid for the incident date |
| Plate mismatch | Registration plate conflicts with the fictional vehicle record |
| Missing driver licence | Required evidence is incomplete |

## Integration-test gaps

The repository does not include an automated deployment of S3, DynamoDB, Lambda, or Bedrock resources. Therefore, end-to-end cloud execution, service quotas, throughput, and latency must be tested in an authorized AWS environment.

Recommended additions include schema contract tests, idempotency tests, retry and partial-failure tests, and measured end-to-end latency under controlled concurrent loads.
