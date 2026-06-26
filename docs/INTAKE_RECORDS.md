# Intake records

Intake records capture receiver-side review of a handoff bundle.

They record the bundle path, bundle digest, artifact digests, receiver identity, notes, and an accepted or blocked decision.

They do not copy files or grant authority.

A clean intake requires a complete handoff bundle and a receiver identifier. If the bundle is incomplete, the record is blocked and carries blockers.

## CLI

```text
builder-intake record HANDOFF_JSON --decision accepted --received-by receiver --notes reviewed --output INTAKE_JSON
builder-intake validate INTAKE_JSON
```

## Verification

```bash
uv run pytest tests/test_receive_records.py tests/test_intake_cli.py -q
uv run pytest -q
```
