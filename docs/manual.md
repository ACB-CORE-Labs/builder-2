# CORE Agent Platform Manual

Local AI coding for [CORE](https://github.com/assetoverflow/core): **Codename Goose** + **Gemma 4** via MLX on M1 16GB.

## Prerequisites

1. **Python 3.12+** and `uv` (project venv in `.venv`)
2. **Codename Goose CLI** — the real agent from [AAIF/block-goose](https://goose-docs.ai), **not** the PyPI `goose-ai` stub:

```bash
brew install block-goose-cli
# or: ./scripts/install-goose.sh
goose --version   # expect 1.38.x+
```

3. **CORE repo** at `CORE_REPO_PATH` (default `../core`)

## Quick start

```bash
cd builder-II
uv sync
cp .env.example .env   # edit if needed
builder start
```

This starts the MLX backend (if down), then launches `goose session --recipe recipes/core-coding.yaml` in the CORE repo with governed instructions.

## Inference backends

Set `CORE_AGENT_BACKEND` in `.env`:

| Backend | Command | Notes |
|---------|---------|-------|
| `rapid-mlx` (default) | `rapid-mlx serve <alias>` | Best TTFT/tool-calling on M1 |
| `mlx-lm` | `mlx_lm.server --model <hf>` | 15–30% faster than Ollama, lower RAM |
| `ollama` | `ollama serve` | Fallback |

Switch model tier:

```bash
builder switch-model fast      # E4B (~5–6 GB)
builder switch-model primary   # 12B (~10–11 GB)
```

One model at a time on 16 GB.

## Goose + local MLX wiring

Goose talks to Rapid-MLX/mlx-lm via the **OpenAI provider**:

```
GOOSE_PROVIDER=openai
OPENAI_HOST=http://127.0.0.1:8080/v1
OPENAI_API_KEY=not-needed
GOOSE_MODEL=default
GOOSE_TEMPERATURE=0.0
```

For Ollama backend, Goose uses `GOOSE_PROVIDER=ollama` and `OLLAMA_HOST`.

Config file (shared CLI/Desktop): `~/.config/goose/config.yaml`

## Commands

| Command | Purpose |
|---------|---------|
| `builder start` | Backend + Goose session with CORE recipe |
| `builder verify algebra/versor.py` | Run CORE test suite for module |
| `builder benchmark` | TTFT, tool-call, compliance, memory report |
| `builder switch-model <tier>` | Show env for model swap |
| `builder status` | Health + goose + compliance |
| `builder init-prompt` | Print governed system prompt |

## Verification harness

Maps module paths to CORE CLI suites (`core test --suite <name> -q`). Invokes `core` on PATH, else `uv run --project $CORE_REPO python -m core.cli`.

## Recipes

`recipes/core-coding.yaml` — Goose recipe with CORE invariants, routing table, developer extension for edit-test-fix.

Validate: `goose recipe validate recipes/core-coding.yaml`

## Troubleshooting

- **`goose: command not found`** → `brew install block-goose-cli`
- **Backend OOM** → `builder switch-model fast`
- **Wrong package** → Do not `pip install goose-ai` (unrelated stub)