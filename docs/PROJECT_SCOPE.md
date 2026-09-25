# Project scope

## Objective

Demonstrate how structured AI extraction and deterministic validation can support the initial review of a motor-vehicle claim package while preserving human decision ownership.

## Included capabilities

- Capture fictional policy, claimant, incident, and vehicle information
- Accept mock KTP, SIM, STNK, and vehicle-image evidence
- Route evidence through configurable AWS resources
- Validate required fields, confidence, matching, and document dates
- Evaluate required vehicle views, visual consistency, damage observations, and visible severity
- Consolidate document and image findings for reviewer inspection
- Record reviewer actions and customer-safe status messages
- Export a structured assessment workbook
- Provide optional retrieval-based guidance from sanitized local documents

## Exclusions

- Final automated claim approval or rejection
- Document authentication or identity verification against official systems
- Fraud determination
- Liability or policy-coverage determination
- Repair-cost estimation, payment, or settlement
- Production authentication and authorization
- Integration with insurer, government, workshop, payment, or notification platforms
- Production service-level commitments
- Training a proprietary model
- Use of real customer or claim data in this public repository

## Assumptions

- Operators provision and configure their own AWS resources.
- Submitted examples contain fictional data and authorized media.
- Bedrock Data Automation results conform to the schemas expected by the validators.
- Thresholds are demonstration defaults and require domain-owner validation before operational use.
- Human reviewers evaluate the original evidence and supporting findings before taking action.
