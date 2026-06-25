# builder-II operator guide

builder-II is a practical local development cockpit for CORE work. It configures Codename Goose, local MLX models, reusable prompts, recipes, skills, runtime helpers, and verification commands.

It is not a replacement for CORE, and it is not presented as a fully autonomous coding agent. The current validated use is governed local review, planning, direct ask, setup, and verification assistance.

## What gets installed or configured

`builder setup` prepares the local Goose environment by writing:

- Goose config at `~/.config/goose/config.yaml`;
- recipe path pointing to `recipes/`;
- slash commands for the CORE work recipes;
- `.goosehints` in the CORE repo;
- auto-generated session context under `.builder/session-context.md`;
- builder-II skills copied into the CORE repo under `.agents/skills`.

## Goose recipes

The main recipes are:

- `recipes/core-platform.yaml` — platform orchestration recipe;
- `recipes/core-coding.yaml` — governed coding recipe;
- `recipes/subrecipes/plan.yaml` — plan before editing;
- `recipes/subrecipes/explore.yaml` — read-only exploration;
- `recipes/subrecipes/implement.yaml` — implementation lane, still verification-driven;
- `recipes/subrecipes/review.yaml` — invariant/compliance review;
- `recipes/subrecipes/verify.yaml` — verification command lane;
- `recipes/subrecipes/handoff.yaml` — end-of-session continuity.

Goose slash commands are wired to these recipes by `builder_ii/goose_setup.py`.

## Skills and extensions

builder-II uses the following Goose extension setup:

- `developer` — bundled filesystem/shell tools for edit-test-fix loops;
- `skills` — platform skill support for builder-II governed coding skills;
- `summon` — platform support for sub-agent style flows where Goose supports it.

The important skills are stored in `.agents/skills/`, then copied into the target CORE repo by `builder setup`.

## Model lanes

The recommended local lanes are:

- `phi-reasoning` for quick review, failure summaries, invariant checks, and context compression;
- `qwen-coder` for targeted implementation planning, code review, and bounded patch work.

Gemma-style models are sidecar/multimodal lanes, not normal `mlx_lm.server` coding defaults. Heavy/candidate aliases are explicit opt-in only.

## Normal workflow

```bash
builder setup
builder doctor
builder models
builder-runtime reset
builder start --task "describe the CORE task here"
```

Inside Goose, use the recipe commands:

```text
/plan describe the smallest safe patch before editing
/explore trace files and call sites first
/review check for invariant or setup violations
/verify run the appropriate verification command
/handoff summarize exact state before stopping
```

For small local questions that do not need Goose:

```bash
builder ask --model phi-reasoning --prompt "Summarize this failure."
builder ask --model qwen-coder --prompt "Draft a small patch plan."
```

## Verification

Use builder-II to route CORE verification commands:

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
- recipe path existence checks.

Not yet validated:

- fully autonomous Goose tool execution through local MLX;
- unattended file modification by a local model;
- production-quality multimodal sidecar integration;
- heavy-model workflows on M1 16GB.

## Sharing posture

When sharing builder-II, describe it as a local Goose/MLX development platform prototype with strong operator discipline. Do not describe it as an autonomous engineer. The safe claim is that it organizes local models, recipes, prompts, setup, runtime management, and verification around CORE development.
