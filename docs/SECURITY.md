# Security and privacy

## Public repository rules

This repository must contain only fictional records, generated mock documents, and media with confirmed redistribution rights.

Never commit:

- AWS credentials, access tokens, passwords, or authentication headers
- AWS account IDs, resource ARNs, live bucket names, or private endpoints
- `.env` files, Streamlit secrets, or CLI credential files
- customer, employer, employee, or claimant information
- identity documents, licence images, registration records, or vehicle evidence from real claims
- database files, generated assessment reports, logs, caches, or model outputs
- contracts, proposals, pricing, internal requirements, or private architecture diagrams

## Credential handling

The application uses environment variables and Boto3's standard credential resolution. Local developers may use an AWS CLI profile, but profile names and credentials must remain outside Git. Workloads deployed to AWS should use IAM roles rather than static access keys.

## IAM guidance

Grant only the specific actions required for the configured S3 prefixes, DynamoDB table, Lambda functions, and Bedrock resources. Separate application, processing, and validation roles where practical. Avoid wildcard resource permissions unless the AWS service requires them and the exception is documented.

## Data protection requirements

Any non-demo implementation should add:

- encryption at rest and in transit
- authenticated user and reviewer identities
- role-based authorization
- malware and file-type validation
- explicit consent and purpose limitation
- retention and deletion controls
- immutable audit records
- logging with sensitive-field redaction
- backup, recovery, and incident-response procedures

## Reporting a security issue

Do not include sensitive values in an issue or pull request. Contact the repository owner privately and identify only the affected file and data type until a secure remediation channel is agreed.
