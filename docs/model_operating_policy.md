# Model operating policy

builder-II is optimized for an M1 16GB machine. The default policy is to use the smallest model that can do the job and keep heavy models explicit opt-in.

## Validated/default lanes

- `phi-reasoning`: fast probe, review, invariant, refusal, and summary lane.
- `qwen-coder`: primary code/planning lane for targeted patches.

## Alternate and sidecar lanes

- `gemma-fast` and `gemma-primary`: Gemma 4 multimodal sidecars. These are not normal `mlx_lm.server` Goose chat targets until a dedicated `mlx-vlm` adapter exists.
- `llama`: instruction-following alternate.

## Heavy explicit opt-in lanes

- `qwen-coder-14b`
- `qwen3-coder-heavy`
- `deepseek`
- `codegeex`

These are candidates for rare validation runs, not daily defaults. Do not route to them automatically just because a task says whole repo, large refactor, or architecture-wide. First plan with the fast/default lanes, then opt in manually if the smaller lane fails.

## Research notes

- The current roster already includes real MLX IDs for Phi 4 mini reasoning, Qwen2.5 Coder 7B, Qwen3 Coder 30B-A3B, and Gemma 4 E4B.
- Do not add speculative IDs such as `Qwen3.5-9B-MLX-4bit` unless the exact repository exists and is validated locally.
- Gemma 4 E4B is treated as a multimodal sidecar because the public MLX usage path is `mlx-vlm`, not the normal `mlx_lm.server` Goose path.
