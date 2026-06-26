# builder-II

`builder-II` is a generic governed local agent/developer platform for MacBook Pro M1 work when cloud coding tools are unavailable. It wraps Codename Goose with practical development governance, MLX-native local models, task-aware model routing, resumable downloads, runtime controls, Goose recipes, skills, target profiles, agent profiles, and verification helpers.

The design goal is not to pretend a small local model is a frontier cloud system. The goal is to give the operator a usable local development platform with clear setup, prompts, recipes, tools, runtime boundaries, target boundaries, and validation commands.

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the current product scope: builder-II is a practical Goose/local-agent development platform, not CORE, not a second CORE runtime, and not CORE Workbench/UI.

## Documentation map

Start here if you are evaluating or sharing the project:

| Document | Purpose |
| --- | --- |
| [`docs/PROJECT_OVERVIEW.md`](docs/PROJECT_OVERVIEW.md) | Plain-English overview of the platform and its components. |
| [`docs/OPERATOR_GUIDE.md`](docs/OPERATOR_GUIDE.md) | Setup, daily workflow, Goose recipes, skills/extensions, and validation boundary. |
| [`docs/TARGETS.md`](docs/TARGETS.md) | Explicit target profiles: generic, builder, and core. |
| [`docs/AGENTS.md`](docs/AGENTS.md) | Generic agent profiles and authority contracts. |
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
- builder-II skills copied into the selected target repo;
- explicit target profiles via `builder-targets`;
- generic agent profiles via `builder-agent`;
- lane guides, personas, and capability boundaries for prompt/task organization;
- external tool registry via `builder-tools`;
- optional external tool installer via `scripts/install-tools.sh`;
- Repomix-backed context manifests via `builder-context`;
- verification routing for target repositories.

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
builder-targets validate
builder-targets list
builder-agent validate
builder-agent profiles
bash scripts/install-tools.sh required
builder-tools check --tier tier1
builder-context pack --target builder --no-repomix
builder start --task "audit the selected target repo and identify the safest next patch"
```

Task hints drive model routing:

```bash
builder start --task "explain how the selected repo is organized"
builder start --task "audit invariant boundaries"
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

## Target profiles

Inspect target profiles with:

```bash
builder-targets list
builder-targets show generic
builder-targets show builder
builder-targets show core
builder-targets validate
```

Initial targets:

```text
generic  normal software repo
builder  builder-II self-development
core     AssetOverflow/core as a target repo
```

CORE is a target profile, not builder-II's platform identity. CORE Workbench/UI remains separate from builder-II.

## Agent profiles

Inspect generic agent profiles with:

```bash
builder-agent profiles
builder-agent profiles --target builder
builder-agent show patch_planner
builder-agent render patch_planner --target generic
builder-agent render patch_planner --target builder
builder-agent render verification_planner --target core
builder-agent validate
```

Initial profiles:

```text
repo_mapper
context_planner
code_reviewer
patch_planner
verification_planner
handoff_scribe
```

These profiles only render prompt and authority contracts. They do not call models, invoke deepagents, edit files, execute shell commands, or write notes.

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

## Context packs

Use `builder-context` to create task-scoped context artifacts before Goose sessions, direct asks, reviews, and handoffs. The default target is `core`, meaning `CORE_REPO_PATH`. Use `--target builder` when packing this builder-II repository itself.

```bash
builder-context pack --target core --task "review CORE work"
builder-context pack --target core --changed --task "summarize current CORE work"
builder-context pack --target builder --module builder_ii/goose_setup.py
builder-context pack --target builder --module builder_ii/context_pack.py --no-repomix
```

Default outputs:

```text
.builder/context-pack.md
.builder/context-pack.xml
```

The Markdown file is a manifest showing the target repo, task, git status, selected files, and Repomix command. The XML file is generated by Repomix when `--no-repomix` is not used. Missing module paths fail closed instead of silently selecting files from the wrong repo.

## Goose workflow

`builder setup` writes Goose configuration and recipe wiring. In Goose, use the recipe commands:

```text
/plan describe the smallest safe patch before editing
/explore trace the call sites first
/review check for invariant or policy violations
/verify path/to/changed_file.py
/handoff write continuity notes before stopping
```

Use `/implement` only after the local provider's tool execution path is explicitly validated.

## Daily loop

```bash
git status --short --branch
builder-targets list
builder-agent profiles
builder status
builder doctor
builder-runtime status
builder-context pack --target builder --changed --task "current builder-II work"
builder-agent render patch_planner --target builder
builder start --task "<specific target task>"
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

`builder verify` maps a changed file to the smallest relevant configured suite.

```bash
builder verify algebra/versor.py
builder verify vault/store.py --fail-fast
builder verify --suite smoke
```

Path routing examples for the CORE target:

| Path | Suite |
|---|---|
| `algebra/` | `algebra` |
| `field/` | `algebra` |
| `generate/` | `cognition` |
| `vault/` | `teaching` |
| `workbench/` | `runtime` |
| `docs/` | `smoke` |

## CORE target posture

CORE-specific behavior belongs in the `core` target profile. builder-II must not conflate itself with CORE Workbench/UI, and it must not treat CORE as the platform identity.

When operating on the CORE target, the local tool must not trade correctness for convenience. It must reject edits that introduce approximate recall in `vault/`, stochastic temperature in CORE cognitive paths, unapproved normalization or hot-path repair, claim promotion outside the reviewed teaching lifecycle, or multi-model local planning on M1 16GB.

## Troubleshooting

Run these first:

```bash
builder doctor
builder status
builder models
builder-targets validate
builder-agent validate
builder-runtime status
bash scripts/pull-roster.sh status
builder-tools check
bash scripts/install-tools.sh status
builder-context pack --target builder --no-repomix
```

Common fixes:

| Symptom | Fix |
|---|---|
| `goose not found` | `brew install block-goose-cli` |
| backend unreachable | Download the selected model, then restart `builder start`. |
| model cache partial | Re-run `bash scripts/pull-roster.sh alias <alias>`. |
| session slows badly | Stop, switch to `phi-reasoning` or `qwen-coder`, and avoid heavy aliases. |
| CORE path wrong | Edit `CORE_REPO_PATH` in `.env`. |
| target unclear | Run `builder-targets list` and `builder-targets show <target>`. |
| agent profile unclear | Run `builder-agent profiles` and `builder-agent show <profile>`. |
| external tool missing | Run `builder-tools missing` and install the listed tool. |
| context pack fails | Confirm `--target core` versus `--target builder`, then run with `--no-repomix` to validate selection without Repomix. |
| local model emits JSON instead of using tools | Treat the session as text-only; do not accept autonomous edits until a tool smoke passes. |

## Command reference

```bash
builder setup
builder doctor
builder models
builder pull
builder ask --model qwen-coder --prompt "..."
builder-targets list
builder-targets show builder
builder-targets validate
builder-agent profiles
builder-agent show patch_planner
builder-agent render patch_planner --target builder
builder-agent validate
builder-lanes list
builder-lanes show draft_patch_plan --context "..."
builder-tools list
builder-tools check --tier tier1
builder-context pack --target core --changed --task "..."
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
