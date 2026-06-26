# builder-II

`builder-II` is a generic governed local agent/developer platform for working with target repositories through explicit profiles, artifacts, model policy, verification guidance, and operator-controlled workflows. It wraps Codename Goose, MLX-native local models, task-aware model policy, resumable downloads, runtime controls, Goose recipes, skills, target profiles, agent profiles, and verification helpers.

The design goal is not to pretend a small local model is a frontier cloud system. The goal is to give the operator a usable local development platform with clear setup, prompts, recipes, tools, runtime boundaries, target boundaries, audit artifacts, and validation commands.

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the current product scope: builder-II is a practical Goose/local-agent development platform, not CORE, not a second CORE runtime, and not CORE Workbench/UI. CORE is one target profile.

## Documentation map

Start here if you are evaluating or sharing the project:

| Document | Purpose |
| --- | --- |
| [`docs/PROJECT_OVERVIEW.md`](docs/PROJECT_OVERVIEW.md) | Plain-English overview of the generic governed platform and its components. |
| [`docs/OPERATOR_GUIDE.md`](docs/OPERATOR_GUIDE.md) | Setup, daily workflow, Goose recipes, skills/extensions, and validation boundary. |
| [`docs/TARGETS.md`](docs/TARGETS.md) | Explicit target profiles: generic, builder, and core. |
| [`docs/AGENTS.md`](docs/AGENTS.md) | Generic agent profiles and authority contracts. |
| [`docs/TARGET_BUNDLES.md`](docs/TARGET_BUNDLES.md) | Governed target bundle JSON artifact creation and validation. |
| [`docs/VERIFICATION_PROFILES.md`](docs/VERIFICATION_PROFILES.md) | Target-scoped verification profile artifacts and validation. |
| [`docs/QUALITY_GATES.md`](docs/QUALITY_GATES.md) | Artifact-only quality gate planning and validation. |
| [`docs/HANDOFF_ARTIFACTS.md`](docs/HANDOFF_ARTIFACTS.md) | Artifact-only handoff capture and validation. |
| [`docs/RESEARCH_PLANS.md`](docs/RESEARCH_PLANS.md) | Artifact-only research planning and source-strategy boundaries. |
| [`docs/GOOSE_RUNTIME.md`](docs/GOOSE_RUNTIME.md) | Goose runtime design boundary and promotion requirements. |
| [`docs/GOOSE_SESSION.md`](docs/GOOSE_SESSION.md) | Goose session manifest artifacts; no runtime activation. |
| [`docs/GOOSE_READONLY.md`](docs/GOOSE_READONLY.md) | Goose read-only runtime candidate audit artifacts; no repository inspection yet. |
| [`docs/GOOSE_INSPECTION.md`](docs/GOOSE_INSPECTION.md) | Bounded read-only inspection artifacts for explicit operator-requested files. |
| [`docs/DEEPAGENTS_POLICY.md`](docs/DEEPAGENTS_POLICY.md) | Governed deepagents policy artifacts; no agent construction. |
| [`docs/DEEPAGENTS_READINESS.md`](docs/DEEPAGENTS_READINESS.md) | Optional deepagents dependency-readiness artifacts; no runtime authority. |
| [`docs/CAPABILITY_PROMOTION.md`](docs/CAPABILITY_PROMOTION.md) | Capability promotion states and non-authority rule. |
| [`docs/RUNTIME_PROMOTION.md`](docs/RUNTIME_PROMOTION.md) | Runtime-specific promotion gates for Goose, deepagents, commands, and patches. |
| [`docs/TOOLING.md`](docs/TOOLING.md) | Tier 1/Tier 2 external engineering tools and Markdown vault strategy. |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Scope, non-goals, and near-term platform direction. |
| [`docs/plan/MASTERPIECE_PLAN.md`](docs/plan/MASTERPIECE_PLAN.md) | End-to-end implementation vision. |
| [`docs/plan/PERFORMANCE_AND_EFFICIENCY_AMENDMENT.md`](docs/plan/PERFORMANCE_AND_EFFICIENCY_AMENDMENT.md) | Performance, model routing, and integration amendment. |
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
- governed target bundle artifacts via `builder-bundle`;
- verification profile artifacts via `builder-verification`;
- quality gate artifacts via `builder-quality`;
- handoff artifacts via `builder-notes`;
- research planning artifacts via `builder-research`;
- Goose session manifest artifacts via `builder-goose`;
- Goose read-only candidate audit artifacts via `builder-goose`;
- bounded Goose read-only inspection artifacts via `builder-goose`;
- governed deepagents policy and dependency-readiness artifacts via `builder-deepagents`;
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

Future hybrid local/frontier routing must begin as a governed policy artifact. It must not silently call external models or bypass target profiles, approvals, audit artifacts, or verification requirements.

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
- Artifact creation and validation for target bundles, verification profiles, quality gates, handoffs, research plans, Goose session manifests, Goose read-only candidate audits, bounded read-only inspection artifacts, governed deepagents policies, and deepagents dependency-readiness artifacts.

Not yet validated/promoted:

- Fully autonomous Goose tool execution through the local `mlx-lm` provider.
- Actual read-only repository inspection by Goose runtime.
- Goose process-backed read-only runtime inspection.
- File-modifying `/implement` sessions driven entirely by a local MLX model.
- deepagents runtime orchestration.
- approved command execution artifacts.
- approved patch application artifacts.
- Production-quality multimodal sidecar support.

Until a dedicated promotion path proves otherwise, treat local MLX sessions as review/planning/reporting lanes. For code edits, require explicit human review and run deterministic verification before accepting changes.

## Install

```bash
brew install block-goose-cli
cd builder-II
uv sync
cp .env.example .env
```

Edit `.env` for target repo paths as needed. If using the `core` target, set the CORE repo path explicitly when it is not at `../core`.

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
