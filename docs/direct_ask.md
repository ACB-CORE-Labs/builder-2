# Direct local ask lane

`builder ask` is the review/probe path for local MLX chat models when a full Goose session is unnecessary.

It sends a direct OpenAI-compatible `/v1/chat/completions` request to the selected backend. It does not launch Goose and does not include tool fields in the request payload.

## Examples

```bash
builder ask --model phi-reasoning --prompt "Summarize this pytest failure in five bullets."
builder ask --model qwen-coder --prompt "Draft a minimal patch plan for this CLI bug."
```

## Intended roles

- `phi-reasoning`: cheap audits, summaries, invariant checks, refusal/safety review, context compression.
- `qwen-coder`: small implementation plans, patch reviews, CLI/test diagnosis.

## Boundaries

- This lane is read-only by construction: it only prints model text.
- It does not validate local tool execution.
- It still uses the backend served-model and marker gates.
- Gemma 4 sidecar models remain blocked from normal `mlx-lm` chat starts by model operating policy.
