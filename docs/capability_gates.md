# Local capability gates

PR #2 adds runtime gates for the local MLX lane.

## Gates

- Served model identity: `/v1/models` must expose the selected model id before `builder start` proceeds.
- Chat smoke: `builder capabilities --chat` can run a live `/v1/chat/completions` text check.
- Tool execution: local `mlx-lm` Goose tool execution remains unsupported/unvalidated. Treat local sessions as review/planning unless a future tool smoke proves otherwise.

## Commands

```bash
builder capabilities
builder capabilities --chat
```

If a backend on port 8080 is serving the wrong model, stop it and restart builder with the selected alias.
