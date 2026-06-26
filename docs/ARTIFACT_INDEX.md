# Artifact index

Artifact index records scan a directory of JSON artifact files and record metadata for each known governed artifact.

The index records:

- relative path;
- SHA-256 digest;
- byte count;
- artifact kind;
- schema version;
- known/valid flags;
- validation errors.

It is metadata-only and does not activate artifact authority.

## Known artifact kinds

- `builder_ii.goose_command_proposal`
- `builder_ii.approval_record`
- `builder_ii.preflight_record`
- `builder_ii.receipt_record`
- `builder_ii.chain_summary_record`
- `builder_ii.handoff_bundle_record`
- `builder_ii.receive_record`
- `builder_ii.promotion_readiness_record`
- `builder_ii.promotion_decision_record`
- `builder_ii.state_ledger_record`
- `builder_ii.artifact_index_record`
- `builder_ii.snapshot_record`
- `builder_ii.target_profile`
- `builder_ii.verification_profile`
- `builder_ii.context_pack_record`
- `builder_ii.agent_profile_record`
- `builder_ii.git_state_record`

## CLI

```text
builder-index record .builder/artifacts --output .builder/artifacts/artifact-index.json
builder-index record .builder/artifacts --recursive --output .builder/artifacts/artifact-index.json
builder-index validate .builder/artifacts/artifact-index.json
```

## Verification

```bash
uv run pytest tests/test_artifact_index_records.py tests/test_artifact_index_cli.py -q
uv run pytest -q
```
