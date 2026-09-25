# Roadmap

The following items are recommendations, not delivery commitments.

## Near term

- Add unit tests for the document and image validation handlers.
- Add sanitized expected-result JSON for each included fixture.
- Add a configuration validation command that fails fast when required AWS variables are missing.
- Add a safe demo mode that uses local fixture results without contacting AWS.
- Capture sanitized UI screenshots using fictional records.

## Platform completeness

- Add reviewed infrastructure-as-code for S3, DynamoDB, Lambda, IAM, and event routing.
- Add the missing Bedrock Data Automation invocation and status-processing components.
- Add schema contract tests between extraction output and validation handlers.
- Add durable orchestration, idempotency controls, retry policies, and dead-letter handling.

## Operational readiness

- Add authentication, reviewer roles, audit history, and data-retention controls.
- Add CloudWatch dashboards, structured logs, tracing, alarms, and cost monitoring.
- Measure extraction quality and routing behavior against an authorized labelled dataset.
- Benchmark end-to-end latency and concurrency in the intended AWS Region.
- Establish model, threshold, privacy, and human-override governance.
