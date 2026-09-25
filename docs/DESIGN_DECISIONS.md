# Design decisions

## Human decision ownership

The application presents findings, confidence indicators, and routing recommendations. It does not make a binding claim decision. This reduces the risk of treating probabilistic extraction or image observations as policy determinations.

## Deterministic validation after extraction

Structured AI output is interpreted using explicit rules for required fields, confidence, matching, expiration, image completeness, and vehicle consistency. This keeps the decision-support logic inspectable and testable.

## Separate binary evidence from assessment state

S3 is used for files and structured result artifacts; DynamoDB is used for review state and summarized findings. This avoids embedding large binary evidence in the operational claim record.

## Hybrid local and cloud demonstration

SQLite supports a self-contained fictional policy and UI workflow. AWS services represent the evidence-processing path. The trade-off is that the repository is not a one-command cloud deployment.

## Synthetic public fixtures

Generated mock documents make validation behavior understandable without publishing real identity records. Vehicle photographs are intentionally omitted until redistribution rights and sanitization are confirmed.

## Explicitly documented gaps

The project does not claim that missing orchestration or infrastructure components are included. Deployment prerequisites and integration gaps are documented so that the repository remains technically accurate.
