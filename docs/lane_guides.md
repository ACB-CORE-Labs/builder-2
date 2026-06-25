# Lane guides

`builder-lanes` prints reusable prompts for common builder-II work lanes.

These guides do not grant tool access, edit files, or bypass verification. They are prompt templates for direct local ask or governed Goose planning sessions.

## Commands

```bash
builder-lanes list
builder-lanes show review_failure
builder-lanes show draft_patch_plan --context "Add a tiny CLI option."
```

## Guides

- `review_failure` uses `phi-reasoning` for failure diagnosis.
- `draft_patch_plan` uses `qwen-coder` for bounded patch planning.
- `audit_invariants` uses `phi-reasoning` for safety and invariant review.
- `summarize_diff` uses `phi-reasoning` for concise merge review.
- `prepare_handoff` uses `qwen-coder` for continuity notes.
- `probe_model_fit` uses `phi-reasoning` to choose the right local lane.

## Example flow

```bash
builder-lanes show review_failure --context "<paste failing command output>"
builder ask --model phi-reasoning --prompt "$(builder-lanes show review_failure --context '<paste failing command output>')"
```
