# builder-II

`builder-II` is the local CORE coding cockpit for MacBook Pro M1 work when cloud coding tools are unavailable. It wraps Codename Goose with practical CORE development governance, MLX-native local models, task-aware model routing, resumable downloads, runtime controls, Goose recipes, skills, and a verification harness aimed at `AssetOverflow/core`.

The design goal is not to pretend a small local model is a frontier cloud system. The goal is to give the operator a usable local development platform with clear setup, prompts, recipes, tools, runtime boundaries, and validation commands.

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the current product scope: builder-II is a practical Goose/local-agent development cockpit for CORE, not a second CORE runtime.

## Documentation map

Start here if you are evaluating or sharing the project:

| Document | Purpose |
| --- | --- |
| [`docs/PROJECT_OVERVIEW.md`](docs/PROJECT_OVERVIEW.md) | Plain-English overview of the platform and its components. |
| [`docs/OPERATOR_GUIDE.md`](docs/OPERATOR_GUIDE.md) | Setup, daily workflow, Goose recipes, skills/extensions, and validation boundary. |
| [`docs/TOOLING.md`](docs/TOOLING.md) | Tier 1/Tier 2 external engineering tools and Markdown vault strategy. |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Scope, non-goals, and near-term platform direction. |
| [`docs/model_role_matrix.md`](docs/model_role_matrix.md) | Model aliases, runtime lanes, recommended use, and avoid boundaries. |
| [`docs/lane_guides.md`](docs/lane_guides.md) | Reusable prompt lanes for direct ask and planning/review work. |
| [`docs/personas.md`](docs/personas.md) | Read-only persona definitions. |
| [`docs/role_gates.md`](docs/role_gates.md) | Capability boundaries for each persona. |
| [`docs/lane_checks.md`](docs/lane_checks.md) | Offline consistency checks for role/lane/gate wiring. |

## Hardware target

Primary target: Apple Silicon MacBook Pro M1 with 16GB unified memory.

The machine does not have 16GB free for weights. macOS, Goose, Python, terminal buffers, repository context, and KV cache all share the same memory pool. Productive coding sessions should prefer roughly 2GB to 7GB model footprints. Larger models are available as explicit opt-in experiments, not defaults.

## What is included

builder-II currently includes:

- CLI setup/doctor/status/model helpers;
- MLX-LM backend startup and served-model checks;
- direct local ask through an OpenAI-compatible local endpoint;
- runtime marker and listener reset helpers;
- model aliases and runtime policy;
- Goose config generation;
- Goose recipes for platform, coding, plan, explore, implement, review, verify, and handoff flows;
- builder-II skills copied into the target CORE repo;
- lane guides, personas, and capability boundaries for prompt/task organization;
- external tool registry via `builder-tools`;
- optional external tool installer via `scripts/install-tools.sh`;
- verification routing for CORE modules.

## Recommended model lanes

| Lane | Alias | Default repo | Purpose |
|---|---|---|---|
| Fast logic/review | `phi-reasoning` | `mlx-community/Phi-4-mini-reasoning-4bit` | Invariant checks, audits, explanations, proposal review. |
| Implementation | `qwen-coder` | `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` | Targeted patches, tests, CLI wiring, bounded refactors. |

Alternates: `gemma-fast`, `gemma-primary`, and `llama`.

Explicit opt-in candidate lanes: `codegeex`, `qwen-coder-14b`, `qwen3-coder-heavy`, and `deepseek`.

See [`docs/model_role_matrix.md`](docs/model_role_matrix.md) for the canonical operating matrix covering each alias, runtime, role, recommended use, and avoid boundary.

## Current validation boundary

Validated on the M1 `mlx-lm` lane:

- `builder doctor` configuration/compliance checks.
- MLX-LM backend startup.
- Health probe at `http://127.0.0.1:8080/v1/models`.
- OpenAI-compatible chat transport at `http://127.0.0.1:8080/v1/chat/completions`.
- Direct local ask through `builder ask`.
- Text-only audit/planning responses through `qwen-coder`.
- Runtime reset with `builder-runtime reset`.
- Goose recipe path wiring.

Not yet validated:

- Fully autonomous Goose tool execution through the local `mlx-lm` provider.
- File-modifying `/implement` sessions driven entirely by a local MLX model.
- Production-quality multimodal sidecar support.

Until a dedicated tool smoke proves otherwise, treat local MLX sessions as review/planning/reporting lanes. For code edits, require explicit human review and run deterministic verification before accepting changes.

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
bash scripts/install-tools.sh required
builder-tools check --tier tier1
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
builder-runtime reset
builder start --model phi-reasoning --task "review this proposal"
```

## External engineering tools

Inspect optional and required external tools with:

```bash
builder-tools list
builder-tools check
builder-tools check --tier tier1
builder-tools missing
bash scripts/install-tools.sh status
```

Install external tools with:

```bash
bash scripts/install-tools.sh required
bash scripts/install-tools.sh tier1
bash scripts/install-tools.sh tier2
bash scripts/install-tools.sh notes
bash scripts/install-tools.sh all
```

The notes backend is plain Markdown by default. You can open `.builder/notes/` with Logseq, Zettlr, Foam/VS Code, Obsidian, or no UI at all.

## Goose workflow

`builder setup` writes Goose configuration and recipe wiring. In Goose, use the recipe commands:

```text
/plan describe the smallest safe patch before editing
/explore trace the call sites first
/review check for CORE invariant violations
/verify workbench/journal.py
/handoff write continuity notes before stopping
```

Use `/implement` only after the local provider's tool execution path is explicitly validated.

## Daily loop

```bash
git -C ../core status --short --branch
builder status
builder doctor
builder-runtime status
builder start --task "<specific CORE task>"
```

## Direct local ask

Use `builder ask` for small local questions that do not need a Goose session.

```bash
builder-runtime reset
builder ask --model phi-reasoning --prompt "Summarize this failure."
builder ask --model qwen-coder --prompt "Draft a small patch plan."
```

Reusable prompt lanes are available with:

```bash
builder-lanes list
builder-lanes show draft_patch_plan --context "Add a small CLI option."
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
builder-runtime status
bash scripts/pull-roster.sh status
builder-tools check
bash scripts/install-tools.sh status
```

Common fixes:

| Symptom | Fix |
|---|---|
| `goose not found` | `brew install block-goose-cli` |
| backend unreachable | Download the selected model, then restart `builder start`. |
| model cache partial | Re-run `bash scripts/pull-roster.sh alias <alias>`. |
| session slows badly | Stop, switch to `phi-reasoning` or `qwen-coder`, and avoid heavy aliases. |
| CORE path wrong | Edit `CORE_REPO_PATH` in `.env`. |
| external tool missing | Run `builder-tools missing` and install the listed tool. |
| local model emits JSON instead of using tools | Treat the session as text-only; do not accept autonomous edits until a tool smoke passes. |

## Command reference

```bash
builder setup
builder doctor
builder models
builder pull
builder ask --model qwen-coder --prompt "..."
builder-lanes list
builder-lanes show draft_patch_plan --context "..."
builder-tools list
builder-tools check --tier tier1
bash scripts/install-tools.sh status
builder start --task "..."
builder start --model llama --task "..."
builder switch-model qwen-coder
builder verify <module>
builder benchmark -o scratch/benchmark.txt
builder status
builder-runtime status
builder-runtime reset
builder config
builder init-prompt
```
