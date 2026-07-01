# B1.4A Validation Note

Run before marking the B1.4A PR ready:

```bash
CORE_REPO_PATH=. .venv/bin/python -m pytest \
  tests/test_verification_execution_ledger.py \
  tests/test_verification_execution_runner.py \
  tests/test_verification_execution_receipt.py \
  tests/test_verification_execution_receipt_cli.py \
  tests/test_verification_execution_approval_authority.py \
  tests/test_command_authority.py \
  tests/test_command_surface_audit.py \
  tests/test_artifact_index_records.py \
  tests/test_artifact_chain_verification.py \
  tests/test_platform_completion_truth.py \
  tests/test_platform_completion_audit.py \
  -q

CORE_REPO_PATH=. .venv/bin/builder-platform audit-docs
git diff --check
```

The PR should remain draft until command authority/docs wiring is complete and this suite is clean.
