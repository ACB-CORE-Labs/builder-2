# HANDOFF — grok43 — 2026-06-23

## Agent and Session

- **Agent:** grok43 / Grok Build
- **Date:** 2026-06-23
- **Reasoning effort used:** high (platform architecture)
- **Grok Build mode used:** Agent
- **Session entry point:** Build local AI coding platform (Goose + Gemma 4 MLX) for CORE on M1 16GB in builder-II

---

## Smoke Suite + Bootstrap Status

```
builder-II (this repo):
uv run pytest -q
...........                                                              [100%]
11 passed

goose recipe validate recipes/core-coding.yaml
✓ recipe file is valid

core-agent status
backend=rapid-mlx tier=primary url=http://127.0.0.1:8080/v1
health: DOWN (backend not started — expected before first model load)
goose: 1.38.0
compliance: literals=PASS refusal=PASS
```

CORE smoke not run as builder-II session gate (independent repo; harness invokes CORE on demand via `core-agent verify`).

---

## Modules Touched

| File | Change type | Summary |
|---|---|---|
| `core_agent/*` | created | Platform package: config, backends, routing, harness, benchmark, compliance, goose_launcher, cli |
| `recipes/core-coding.yaml` | created | Goose recipe with CORE invariants + developer extension |
| `scripts/install-goose.sh` | created | Install real Codename Goose CLI |
| `scripts/start-backend.sh` | created | Start configured MLX backend |
| `docs/manual.md` | created | Operator manual |
| `tests/*` | created | Unit tests (routing, harness parser, compliance, goose) |
| `pyproject.toml` | modified | core-agent entrypoint; removed goose-ai stub dep |
| `.env.example`, `.env` | modified | rapid-mlx default backend |
| `README.md` | modified | Quick start with real Goose |
| `HANDOFF-grok43-2026-06-23.md` | created | This file |

---

## Architectural Decisions Made This Session

1. **Codename Goose ≠ `goose-ai` PyPI package.** Real agent is `block-goose-cli` (AAIF, v1.38.0) via Homebrew or `scripts/install-goose.sh`. Removed `goose-ai` from dependencies.
2. **Default inference: Rapid-MLX** — best TTFT/tool-calling per eval; switch via `CORE_AGENT_BACKEND` (mlx-lm, ollama).
3. **Goose provider wiring:** OpenAI provider + `OPENAI_HOST` for rapid-mlx/mlx-lm; Ollama provider + `OLLAMA_HOST` for ollama backend. `GOOSE_TEMPERATURE=0.0`.
4. **Init artifact:** Goose recipe `recipes/core-coding.yaml` + `core_agent/init_content.py` single-source prompt (~175 tokens).
5. **builder-II smoke only** for platform commits; CORE tests via `core-agent verify <module>`.

---

## What Must Not Be Forgotten

Do not `pip install goose-ai` — it is an unrelated stub. Install **Codename Goose** with `brew install block-goose-cli`. Run `core-agent start` from builder-II; it loads the CORE recipe and points Goose at the local MLX server.

---

## Open Tasks / Next Session Entry Point

1. First run: download Gemma model (`rapid-mlx serve gemma-4-12b-4bit` pulls on first start).
2. Run `core-agent benchmark` with backend up to capture TTFT/tok/s evidence.
3. Optional: `goose configure` once to persist provider in `~/.config/goose/config.yaml`.