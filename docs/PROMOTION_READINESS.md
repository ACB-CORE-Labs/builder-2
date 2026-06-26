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

## Validation boundary

The validator enforces these constraints:

| Field | Required value |
|---|---|
| `kind` | `builder_ii.promotion_readiness_record` |
| `schema_version` | `1` |
| `record_state` | `RECORDED_ONLY` |
| `current_state` | `DISABLED` |
| `capability_state` | `promotion_readiness_record` |
| `capability_name` | non-empty string |
| `target_state` | non-empty string |
| `status` | `ready` or `blocked` |
| `ready` | boolean, must match `status` |
| `missing` | list of non-empty strings; must contain all check-level missing items |
| `checks` | list of 8 required check objects |
| `performed_actions` | `[]` |
| `grants_runtime_authority` | `false` |
| `grants_action_authority` | `false` |

### Per-check validation

Each check object must have:

| Field | Type | Constraint |
|---|---|---|
| `name` | string | non-empty, one of the 8 required names |
| `refs` | list | non-empty string evidence references |
| `ready` | boolean | must match whether `refs` is non-empty |
| `missing` | list | non-empty strings; must be empty when `refs` present; must be non-empty when `refs` empty |

### Governance block

| Field | Required value |
|---|---|
| `capability_state` | `promotion_readiness_record` |
| `runtime_execution` | `DISABLED` |
| `model_execution` | `DISABLED` |
| `source_writes` | `DISABLED` |
| `memory_mutation` | `DISABLED` |
| `artifact_is_authority` | `false` |
| `core_workbench_coupling` | `NONE` |

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
