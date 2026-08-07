# Model role matrix

This is the canonical operating matrix for builder-II local models on an M1 16GB machine.

The rule is: use the smallest validated lane that can answer the question, keep runtime switches explicit, and never treat a candidate or sidecar model as a default execution path.

## Default lanes

| Alias | Runtime | Role | Use for | Avoid |
| --- | --- | --- | --- | --- |
| `phi-reasoning` | `mlx-lm` | Fast probe / review lane | quick audits, summaries, invariant checks, refusal/safety review, context compression | heavy implementation, long Goose sessions, autonomous edits |
| `qwen-coder` | `mlx-lm` | Primary code / planning lane | targeted Python, CLI, tests, patch planning, bounded refactors, direct code review | whole-repo sweeps, giant-context rewrites, unsupervised execution |

## Sidecar lanes

| Alias | Runtime | Role | Use for | Avoid |
| --- | --- | --- | --- | --- |
| `gemma-fast` | `mlx-vlm-sidecar` | Fast multimodal sidecar | UI screenshots, visual inspection, multimodal experiments after adapter support | normal Goose coding through `mlx_lm.server` |
| `gemma-primary` | `mlx-vlm-sidecar` | Heavy multimodal sidecar | harder visual/multimodal experiments when memory allows | default routing, long coding sessions, background M1 use |

## Alternate and candidate lanes

| Alias | Runtime | Role | Use for | Avoid |
| --- | --- | --- | --- | --- |
| `llama` | `mlx-lm` | Constraint alternate | instruction-following comparison, negative-constraint checks, prompt robustness | default code implementation when Qwen is available |
| `codegeex` | `mlx-lm-candidate` | Candidate code lane | agentic coding experiments after local smoke validation | trusted edits before dedicated validation |

## Heavy explicit opt-in lanes

| Alias | Runtime | Role | Use for | Avoid |
| --- | --- | --- | --- | --- |
| `qwen-coder-14b` | `mlx-lm-heavy` | Heavy code lane | rare harder refactors after 7B fails and memory headroom is confirmed | default or routine tasks on 16GB |
| `qwen3-coder-heavy` | `mlx-lm-heavy` | Heavy agentic coder | rare hard coding benchmarks and agentic coding comparisons | normal local Goose work on 16GB |
| `deepseek` | `mlx-lm-heavy` | Heavy repo-sweep candidate | manual repo-sweep experiments after memory validation | daily operation or default routing |

## Operator routing doctrine

1. Start with `phi-reasoning` for cheap review/probe work when no code generation is needed.
2. Use `qwen-coder` for direct code planning, small patch review, and targeted implementation work.
3. Use Goose only when the task needs a governed session shell, not for every local question.
4. Treat Gemma as a future visual sidecar until the `mlx-vlm` adapter exists.
5. Treat heavy and candidate lanes as explicit opt-in experiments, never automatic router outcomes.
6. Clear or reset the local runtime before switching models.

## Command examples

```bash
builder ask --model phi-reasoning --prompt "Summarize this failure."
builder ask --model qwen-coder --prompt "Draft a small patch plan."
builder-runtime reset
builder-goose run-governed --manifest .builder/goose/session.json \
  --task "review a targeted CLI patch"
```

## Cloud Egress Lanes

| Provider | Alias | Role | Use for | Avoid |
| --- | --- | --- | --- | --- |
| OpenAI | `gpt-5.5` | Flagship reasoning / agentic | Deep reasoning, autonomous workflows | High-frequency low-latency loops |
| Anthropic | `claude-opus-4.8` | Flagship reasoning / coding | Heavy agentic coding work | Local-only offline work |
| Anthropic | `claude-sonnet-5` | High-throughput agentic | High-frequency agentic loops | Local-only offline work |
| xAI | `grok-build-0.1` | Agentic Coding | Agentic coding workflows | Local-only offline work |
| xAI | `grok-4.3` | Flagship Chat/Reasoning | Fast and deep reasoning | Local-only offline work |
| Groq | `groq-llama` | High-speed Llama | Speculative decoding, high-throughput | Tasks needing 1M+ context |
| Google | `gemini-3.5-flash` | Multimodal agentic | Multimodal inputs, large context | Local-only offline work |
