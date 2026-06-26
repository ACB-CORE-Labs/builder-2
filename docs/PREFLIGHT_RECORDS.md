# Preflight records

Preflight records capture the combined state of a proposed action and its corresponding approval decision. They represent a checkpoint verifying that the proposal is ready for future execution by checking for any outstanding validation errors, mismatches, or missing parameters (blockers).

They are record-only artifacts. They do not run or execute commands. They preserve:

- `record_state = RECORDED_ONLY`
- `current_runtime_state = DISABLED`
- `grants_runtime_authority = false`
- `grants_action_authority = false`
- `performed_actions = []`
- `governance.artifact_is_authority = false`
- `governance.core_workbench_coupling = NONE`

## Required Inputs

To create a preflight record, the following inputs are required:

1. **Proposal Artifact**: A valid Goose command proposal file.
2. **Approval Record**: A valid approval record file corresponding to the proposal.
3. **Verification Refs**: Executable verification strings that verify the state (passed via one or more `--verification-ref` options).

## Ready vs. Blocked Behavior

- **Ready**: A preflight record is marked as `ready` (`status = "ready"` and `ready = true`) if the proposal and approval are fully valid, the approval decision is `"approved"`, the approval's proposal digest matches the actual proposal digest, and at least one verification ref is provided.
- **Blocked**: If any validation issues or digest mismatches exist, if the approval decision is not `"approved"`, or if no verification refs are provided, the preflight record is marked as `blocked` (`status = "blocked"` and `ready = false`). Blocked records are still valid preflight record artifacts and carry a list of outstanding `blockers` detailing why the preflight is blocked.

## Commands

The `builder-preflight` command records and validates preflight artifacts.

Example record command (ready):

```bash
builder-preflight record .builder/artifacts/goose-command-proposal.json \
  .builder/artifacts/approval-record.json \
  --verification-ref "uv run pytest -q" \
  --output .builder/artifacts/preflight-record.json
```

Example record command (blocked):

```bash
builder-preflight record .builder/artifacts/goose-command-proposal.json \
  .builder/artifacts/approval-record.json \
  --output .builder/artifacts/preflight-record.json
```

Example validate command:

```bash
builder-preflight validate .builder/artifacts/preflight-record.json
```

## Verification

To run tests:

```bash
uv run pytest tests/test_preflight_records.py tests/test_preflight_app.py -q
uv run pytest -q
```
