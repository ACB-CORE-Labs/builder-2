## Summary

Adds local capability gates for the `mlx-lm` lane after PR #1 proved backend/chat transport but exposed two remaining boundaries:

- a healthy server on port 8080 may be serving the wrong model after alias switches;
- local Goose tool execution is not proven and should remain explicitly gated.

## Changes

- Adds served-model identity parsing for OpenAI-compatible `/v1/models` responses.
- Makes `builder start` refuse to continue if a running `mlx-lm` backend is serving a different model than the selected alias.
- Adds `builder capabilities` and `builder capabilities --chat`.
- Adds a live chat smoke helper for `/v1/chat/completions`.
- Marks local `mlx-lm` Goose tool execution as unsupported/unvalidated rather than silently implying `/implement` readiness.
- Extends `builder doctor` and `builder status` with served-model visibility.
- Adds focused tests for served-model identity matching/mismatch.
- Adds `docs/capability_gates.md`.

## Local validation to run

```bash
git fetch origin
git switch feat/local-model-capability-gates
git pull --ff-only
uv run pytest -q
builder doctor
builder capabilities
builder capabilities --chat
```

Model-switch mismatch smoke:

```bash
# With qwen-coder server running, this should refuse instead of silently reusing qwen:
builder start --model phi-reasoning --task "audit routing text-only"
```

Expected boundary:

- `qwen-coder` and `phi-reasoning` can be served and hit `/v1/chat/completions`.
- `builder start` now verifies the served model id before launching Goose.
- Tool execution remains blocked/unvalidated for local `mlx-lm` until a dedicated future smoke proves otherwise.
