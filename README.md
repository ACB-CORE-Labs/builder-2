# builder-II

`builder-II` is the local CORE coding cockpit for MacBook Pro M1 work when cloud coding tools are unavailable. It wraps Codename Goose with deterministic CORE governance, MLX-native local models, task-aware model routing, resumable downloads, and a verification harness aimed at `AssetOverflow/core`.

The design goal is not to pretend a small local model is a frontier cloud system. The goal is to place the local model inside strong rails: exact context injection, model memory discipline, read-before-write workflow, deterministic verification, and handoff continuity.

## Hardware target

Primary target: Apple Silicon MacBook Pro M1 with 16GB unified memory.

The machine does not have 16GB free for weights. macOS, Goose, Python, terminal buffers, repository context, and KV cache all share the same memory pool. Productive coding sessions should prefer roughly 2GB to 7GB model footprints. Larger models are available as explicit opt-in experiments, not defaults.

## Recommended model lanes

| Lane | Alias | Default repo | Purpose |
|---|---|---|---|
| Fast logic/review | `phi-reasoning` | `mlx-community/Phi-4-mini-reasoning-4bit` | Invariant checks, audits, explanations, proposal review. |
| Implementation | `qwen-coder` | `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` | Targeted patches, tests, CLI wiring, bounded refactors. |

Alternates: `gemma-fast`, `gemma-primary`, and `llama`.

Explicit opt-in candidate lanes: `codegeex`, `qwen-coder-14b`, `qwen3-coder-heavy`, and `deepseek`.

## Install

```bash
brew install block-goose-cli
cd builder-II
uv sync
cp .env.example .env
```

Edit `.env` if CORE is not at `../core`.

```bash
CORE_REPO_PATH=../core
CORE_AGENT_BACKEND=mlx-lm
CORE_AGENT_MODEL_ALIAS=qwen-coder
```

## Download models

The governed downloader is resumable. Re-run the same command after Wi-Fi drops or Hugging Face throttling.

```bash
bash scripts/pull-roster.sh status
bash scripts/pull-roster.sh recommended
```

Useful variants:

```bash
bash scripts/pull-roster.sh fast
bash scripts/pull-roster.sh primary
bash scripts/pull-roster.sh all-safe
bash scripts/pull-roster.sh alias llama
bash scripts/pull-roster.sh candidates
```

## First run

```bash
builder setup
builder doctor
builder models
builder start --task "audit the latest CORE branch and identify the safest next patch"
```

Task hints drive model routing:

```bash
builder start --task "explain how vault recall works"
builder start --task "audit versor_condition invariants"
builder start --task "implement tests for the routing harness"
builder start --task "refactor the CLI model selection path"
```

Manual model override:

```bash
builder switch-model phi-reasoning
builder switch-model qwen-coder
builder switch-model llama
builder start --model phi-reasoning --task "review this proposal"
```

## Daily loop

```bash
git -C ../core status --short --branch
builder status
builder doctor
builder start --task "<specific CORE task>"
```

Inside Goose, prefer the governed recipes and skills:

```text
/plan describe the smallest safe patch before editing
/explore trace the call sites first
/implement apply the patch and run verification
/verify workbench/journal.py
/review check for CORE invariant violations
/handoff write continuity notes before stopping
```

## Verification

`builder verify` maps a changed file to the smallest relevant CORE suite.

```bash
builder verify algebra/versor.py
builder verify vault/store.py --fail-fast
builder verify --suite smoke
```

Path routing examples:

| Path | Suite |
|---|---|
| `algebra/` | `algebra` |
| `field/` | `algebra` |
| `generate/` | `cognition` |
| `vault/` | `teaching` |
| `workbench/` | `runtime` |
| `docs/` | `smoke` |

## CORE invariant posture

The local tool must not trade correctness for convenience. It must reject edits that introduce approximate recall in `vault/`, stochastic temperature in CORE cognitive paths, unapproved normalization or hot-path repair, claim promotion outside the reviewed teaching lifecycle, or multi-model local planning on M1 16GB.

## Troubleshooting

Run these first:

```bash
builder doctor
builder status
builder models
bash scripts/pull-roster.sh status
```

Common fixes:

| Symptom | Fix |
|---|---|
| `goose not found` | `brew install block-goose-cli` |
| backend unreachable | Download the selected model, then restart `builder start`. |
| model cache partial | Re-run `bash scripts/pull-roster.sh alias <alias>`. |
| session slows badly | Stop, switch to `phi-reasoning` or `qwen-coder`, and avoid heavy aliases. |
| CORE path wrong | Edit `CORE_REPO_PATH` in `.env`. |

## Command reference

```bash
builder setup
builder doctor
builder models
builder pull
builder start --task "..."
builder start --model llama --task "..."
builder switch-model qwen-coder
builder verify <module>
builder benchmark -o scratch/benchmark.txt
builder status
builder config
builder init-prompt
```
