# Manual checks

These scripts exercise AWS connectivity, fictional policy lookup, and the
optional local claims-guidance components.

Run them from the project root as Python modules. For example:

```powershell
python -m tests.manual.test_aws_connection
python -m tests.manual.test_policy_record
python -m tests.manual.test_rag
```

Configure the required environment variables before running AWS diagnostics.
These are diagnostic tools, not automated pass/fail unit tests.
