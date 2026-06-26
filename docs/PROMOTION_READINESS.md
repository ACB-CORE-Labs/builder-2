# Promotion readiness

Promotion readiness records capture whether a capability has the required evidence to move toward a new state.

The record checks eight required areas:

- docs
- tests
- command-line surface
- failure mode
- approval boundary
- output artifact
- rollback path
- verification path

The record is metadata-only. It does not enable the capability and does not grant authority.

## CLI

```text
builder-promotion record --capability-name artifact_index --docs-ref docs/ARTIFACT_INDEX.md --tests-ref tests/test_artifact_index_records.py --cli-ref builder-index --failure-mode-ref incomplete-index --approval-boundary-ref artifact-is-not-authority --output-artifact-ref artifact-index.json --rollback-ref delete-artifact --verification-ref "uv run pytest -q" --output promotion-readiness.json
builder-promotion validate promotion-readiness.json
```

## Verification

```bash
uv run pytest tests/test_promotion_readiness_records.py tests/test_promotion_readiness_cli.py -q
uv run pytest -q
```
