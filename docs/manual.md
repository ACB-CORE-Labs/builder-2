# Builder Platform Manual

`builder-II` is a local CORE development platform for MacBook Pro M1 16GB. It combines Codename Goose, MLX-native model serving, CORE-specific skills, governed recipes, dynamic session context, and deterministic verification.

## M1 operating principle

The model, KV cache, Goose, Python, terminal buffers, macOS, browser tabs, and the target repository all share unified memory. A model that looks acceptable by weight size alone can still become unusable once a coding session accumulates context.

Use the smallest model that fits the task. Keep planner and execution on the same local model. Keep heavy aliases explicit.

## Setup

```bash
brew install block-goose-cli
cd builder-II
uv sync --extra mlx
cp .env.example .env
builder-setup plan --output /tmp/builder-ii-setup-plan.json
builder-setup validate-plan /tmp/builder-ii-setup-plan.json
builder-setup overlay-plan /tmp/builder-ii-setup-plan.json --output /tmp/builder-ii-setup-overlay.json
builder-setup validate-overlay-plan /tmp/builder-ii-setup-overlay.json
builder-setup rollback-snapshot /tmp/builder-ii-setup-overlay.json --output /tmp/builder-ii-setup-rollback-snapshot.json
builder-setup validate-rollback-snapshot /tmp/builder-ii-setup-rollback-snapshot.json
bash scripts/pull-roster.sh recommended
builder doctor
builder start --task "inspect CORE and suggest the smallest safe patch"
```

Legacy `builder setup` is a fail-closed redirect in R1.4. It no longer writes Goose config, `.goosehints`, skills, or recipes.

Default `.env` values:

```bash
CORE_REPO_PATH=../core
CORE_AGENT_BACKEND=mlx-lm
CORE_AGENT_MODEL_TIER=primary
CORE_AGENT_MODEL_ALIAS=qwen-coder
CORE_AGENT_BASE_URL=http://127.0.0.1:8080/v1
CORE_AGENT_TEMPERATURE=0.0
```

## Model aliases

| Alias | Use | Policy |
|---|---|---|
| `phi-reasoning` | audit, review, invariant checks, explanations | Recommended fast default |
| `qwen-coder` | targeted patches, tests, CLI wiring | Recommended implementation default |
| `gemma-fast` | broad explanation or fallback | Alternate |
| `gemma-primary` | heavier reasoning | Alternate; monitor swap |
| `llama` | complex instruction following | Alternate |
| `codegeex` | repository patching trial | Candidate; verify first |
| `qwen-coder-14b` | deep refactor trial | Explicit opt-in |
| `qwen3-coder-heavy` | advanced coding trial | Explicit opt-in |
| `deepseek` | repo-sweep trial | Explicit opt-in |

A public `Qwen3-Coder 14B` default is not assumed. The safer interpretation is that Qwen2.5-Coder 14B and Qwen3-Coder heavy lanes are candidates, while Qwen2.5-Coder 7B remains the default implementation lane for this machine.

## Downloading models

```bash
bash scripts/pull-roster.sh status
bash scripts/pull-roster.sh recommended
bash scripts/pull-roster.sh fast
bash scripts/pull-roster.sh primary
bash scripts/pull-roster.sh all-safe
bash scripts/pull-roster.sh alias phi-reasoning
bash scripts/pull-roster.sh alias qwen-coder
bash scripts/pull-roster.sh candidates
```

`candidates` may fail if an MLX community conversion was renamed or is unavailable. Override the corresponding environment variable in `.env` before retrying.

## Session routing

| Command | Typical alias | Use |
|---|---|---|
| `builder start --mode quick` | `phi-reasoning` | Read-only exploration |
| `builder start --mode deep` | `qwen-coder` | Implementation |
| `builder start --mode coding` | `qwen-coder` | Single coding recipe |
| `builder start --task "audit the invariant"` | `phi-reasoning` | Task-routed review |
| `builder start --task "implement the patch"` | `qwen-coder` | Task-routed implementation |

Prefer a specific task hint:

```bash
builder start --task "audit vault recall for approximate similarity violations"
builder start --task "implement focused tests for model alias routing"
```

Manual overrides:

```bash
builder switch-model phi-reasoning
builder switch-model qwen-coder
builder switch-model llama
builder start --model llama --task "review prompt adherence"
```

## Goose capabilities

| Feature | How |
|---|---|
| Orchestrator recipe | `recipes/core-platform.yaml` |
| Coding recipe | `recipes/core-coding.yaml` |
| Subrecipes | `explore`, `implement`, `review`, `verify`, `handoff`, `plan` |
| Skills | Planned in setup overlay artifacts; not copied by legacy `builder setup` |
| MOIM context | `.builder/session-context.md` for active operator-launched runtime sessions |
| Hints | Planned as `.goosehints` setup overlay candidates |

## Verification harness

```bash
builder verify algebra/versor.py
builder verify vault/store.py --fail-fast
builder verify --suite smoke
```

The harness selects the smallest relevant suite from the changed module path and prints the command, rationale, pytest summary, elapsed time when available, and a failure tail.

## Doctor and status

```bash
builder doctor
builder status
builder models
```

`doctor` checks CORE path, Goose availability, backend reachability, recipe validation, compliance probes, and the active model cache.

`status` projects the current governed run using `goal / now / needs-you / next / proof`.
Pass an exact run id when needed, `--watch` for change-driven snapshots, or
`--json` for the frontend-neutral payload. It launches no runtime and grants no
authority. Use `doctor`, not `status`, for environment diagnostics.

## M1 proficiency rules

1. Close memory-heavy apps before long sessions.
2. Use `phi-reasoning` for reading, review, and invariant checks.
3. Use `qwen-coder` for bounded implementation.
4. Do not start heavy candidates unless you are intentionally measuring them.
5. Stop and restart the backend after switching aliases.
6. Keep tasks narrow.
7. End non-trivial sessions with a handoff.

## Troubleshooting

| Problem | Action |
|---|---|
| Goose missing | `brew install block-goose-cli` |
| Selected model missing | `bash scripts/pull-roster.sh alias <alias>` |
| Partial model cache | Rerun the same pull command |
| Backend does not start | Run `builder models`, confirm active alias cache, then retry |
| System starts swapping | Stop, switch to `phi-reasoning` or `qwen-coder`, close heavy apps |
| Recipe validation skipped | Goose is not installed or unavailable |
| CORE repo not found | Fix `CORE_REPO_PATH` in `.env` |

## Command reference

```bash
builder-setup plan --output /tmp/builder-ii-setup-plan.json
builder-setup validate-plan /tmp/builder-ii-setup-plan.json
builder doctor
builder models
builder pull
builder start --task "..."
builder start --model phi-reasoning --task "..."
builder switch-model qwen-coder
builder verify <module>
builder benchmark -o scratch/report.txt
builder status
builder config
builder init-prompt
```
