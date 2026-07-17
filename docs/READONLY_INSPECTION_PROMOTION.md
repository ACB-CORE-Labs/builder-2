# Read-Only Inspection Promotion

`readonly_inspection_report` is a runtime-candidate evidence artifact. It records only explicit metadata and hashes.

## Key Relationships and Invariants

1. **Evidence only, not Authority**
   - The `readonly_inspection_report` artifact is not authority by itself.
   - Promotion readiness/decision records remain the authority path.

2. **No Runtime Expansion**
   - Wires purely as optional evidence to support promotion compatibility.
   - Does not enable shell execution, model execution, repo traversal, hidden inspection, patching, Goose runtime, or deepagents runtime.

3. **Required vs. Allowed Support Artifacts**
   - The required baseline support set is always required to move past blocked status when support artifacts are provided.
   - `builder_ii.readonly_inspection_report` is an allowed optional support artifact, not a replacement for any required baseline support artifacts.

## Verification

```bash
TARGET_REPO_PATH=. uv run pytest tests/test_readonly_inspection_reports.py tests/test_promotion_compatibility.py tests/test_promotion_readiness_records.py tests/test_artifact_index_records.py tests/test_artifact_chain_verification.py tests/test_registry_closure.py -q
TARGET_REPO_PATH=. uv run pytest -q
```
