# builder-II operator guide

builder-II is a generic governed local agent/developer platform. It helps an operator work against explicit target repositories with local model support, Goose recipes, artifacts, verification guidance, and promotion-gated runtime boundaries.

It is not CORE, not CORE Workbench/UI, and not a fully autonomous coding agent. CORE is available through the `core` target profile.

## Validated posture

The current validated use is governed local review, planning, direct ask, setup, artifact creation, artifact validation, runtime control, and verification assistance.

The current platform does not grant authority for:

- autonomous source writes;
- shell execution as an agent capability;
- hidden model execution;
- deepagents construction;
- Goose runtime activation from manifests alone;
- memory mutation;
- commits or pushes;
- pull request creation;
- source collection, web search, or MCP execution;
- CORE Workbench/UI coupling.

## What gets installed or configured

`builder setup` prepares the local platform environment and Goose support. Depending on target configuration, setup may write:

- Goose config at `~/.config/goose/config.yaml`;
- recipe path pointing to `recipes/`;
- slash commands for governed development recipes;
- `.goosehints` in the selected target repo;
- auto-generated session context under `.builder/session-context.md`;
- builder-II skills copied into the selected target repo under `.agents/skills`.

Target-specific behavior must remain isolated to the selected target profile.

## Normal artifact-first workflow

```bash
builder setup
builder doctor
builder-targets validate
builder-agent validate
builder-verification validate
builder-context pack --target builder --changed --task "describe the task"
builder-bundle create --target builder --agent patch_planner --task "describe the task" --output .builder/artifacts/target-bundle.json
builder-bundle validate .builder/artifacts/target-bundle.json
builder-quality plan --target builder --profile builder_full --task "describe the task" --output .builder/artifacts/quality-gate.json
builder-quality validate .builder/artifacts/quality-gate.json
builder-notes handoff --target builder --agent handoff_scribe --task "describe the task" --summary "current state" --output .builder/artifacts/handoff.json
builder-notes validate .builder/artifacts/handoff.json
builder-goose manifest --target builder --agent patch_planner --mode read_only --task "describe the task" --output .builder/artifacts/goose-session.json
builder-goose validate .builder/artifacts/goose-session.json
```

The explicit output artifacts above are review objects. They do not start Goose, construct agents, call models, execute commands, mutate files, or authorize future runtime work.

## Target profiles

The initial target profiles are:

- `generic` — any normal software repository with no project-specific doctrine.
- `builder` — builder-II self-development.
- `core` — AssetOverflow/core as a target repository.

Useful commands:

```bash
builder-targets list
builder-targets show generic
builder-targets show builder
builder-targets show core
builder-targets validate
```

## Goose recipes

The main recipes are:

- `recipes/core-platform.yaml` — current platform orchestration recipe name retained for compatibility;
- `recipes/core-coding.yaml` — current governed coding recipe name retained for compatibility;
- `recipes/subrecipes/plan.yaml` — plan before editing;
- `recipes/subrecipes/explore.yaml` — read-only exploration;
- `recipes/subrecipes/implement.yaml` — implementation lane, still verification-driven;
- `recipes/subrecipes/review.yaml` — invariant/compliance review;
- `recipes/subrecipes/verify.yaml` — verification command lane;
- `recipes/subrecipes/handoff.yaml` — end-of-session continuity.

Recipe names may still contain historical CORE wording. Platform identity does not follow those names; target-specific behavior belongs in target profiles.

Inside Goose, use the recipe commands only within the current validated operator boundary:

```text
/plan describe the smallest safe patch before editing
/explore trace files and call sites first
/review check for invariant, target, or setup violations
/verify identify the appropriate verification command
/handoff summarize exact state before stopping
```

## Skills and extensions

builder-II may configure Goose extensions for developer tools, skills, and summon-style workflows where available.

Local MLX chat is validated for text responses. Local Goose tool execution remains unpromoted until dedicated smoke tests, denied-action tests, audit artifacts, approval boundaries, rollback paths, and verification paths prove otherwise.

## Model lanes

The recommended local lanes are:

- `phi-reasoning` for quick review, failure summaries, invariant checks, and context compression;
- `qwen-coder` for targeted implementation planning, code review, and bounded patch work.

Gemma-style models are sidecar/multimodal lanes, not normal `mlx_lm.server` coding defaults. Heavy/candidate aliases are explicit opt-in only.

Future hybrid local/frontier routing must begin as a policy artifact. It must not silently call external models or create cost/privacy exposure without approval.

For small local questions that do not need Goose:

```bash
builder ask --model phi-reasoning --prompt "Summarize this failure."
builder ask --model qwen-coder --prompt "Draft a small patch plan."
```

## Verification

Use builder-II to route target verification commands when supported:

```bash
builder verify algebra/versor.py
builder verify vault/store.py --fail-fast
builder verify --suite smoke
```

Use repository tests for builder-II itself:

```bash
uv run pytest -q
```

## Current validation boundary

Validated:

- package install through `uv`;
- `builder doctor`;
- model roster and model policy;
- MLX-LM backend startup;
- served-model check at `/v1/models`;
- direct local ask through `/v1/chat/completions`;
- runtime marker reset and listener cleanup;
- Goose config generation;
- recipe path existence checks;
- artifact creation and validation for target bundles, verification profiles, quality gates, handoffs, research plans, and Goose session manifests.

Not yet validated/promoted:

- fully autonomous Goose tool execution through local MLX;
- unattended file modification by a local model;
- deepagents runtime orchestration;
- approved command execution artifacts;
- approved patch application artifacts;
- production-quality multimodal sidecar integration;
- heavy-model workflows on M1 16GB.

## Sharing posture

When sharing builder-II, describe it as a generic governed local agent/developer platform with Goose/MLX support and strong operator discipline.

Do not describe it as an autonomous engineer, CORE Workbench/UI, or CORE itself. The safe claim is that it organizes target profiles, local models, recipes, prompts, setup, runtime management, artifacts, verification, and governance boundaries for local development work.
