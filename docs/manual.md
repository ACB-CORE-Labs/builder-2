# Builder Platform Manual

Local CORE coding on M1 16GB: **Codename Goose** + **Gemma 4** via **Rapid-MLX**.

## First-time setup

```bash
brew install block-goose-cli    # real Goose (NOT pip goose-ai)
cd builder-II && uv sync
cp .env.example .env
builder setup                   # Goose config, skills, hints, validate recipes
builder pull                    # download Gemma weights (~7–11 GB first time)
builder start                   # backend + orchestrated Goose session
```

## Goose capabilities wired in

| Feature | How |
|---------|-----|
| **Orchestrator recipe** | `recipes/core-platform.yaml` — main session with 5 subrecipes |
| **Subagents** | `core_explore`, `core_implement`, `core_review`, `core_verify`, `core_handoff` via summon/delegate |
| **Slash commands** | `/explore` `/implement` `/review` `/verify` `/handoff` `/platform` `/coding` |
| **Skills** | `.agents/skills/` → copied to CORE on `builder setup` |
| **Plan mode** | `/plan` in Goose CLI (planner shares same local model on 16GB) |
| **MOIM context** | Auto-injects `.builder/session-context.md` every turn |
| **`.goosehints`** | Written to CORE repo root on setup |
| **Developer MCP** | File + shell tools for edit-test-fix |
| **Summon platform** | Subrecipe delegation |

## Session modes (`builder start --mode`)

| Mode | Model tier | Recipe | Use |
|------|------------|--------|-----|
| `orchestrator` (default) | primary 12B | core-platform.yaml | Full subagent stack |
| `quick` | fast 4B | core-platform.yaml | Explain, search, read |
| `deep` | primary 12B | core-platform.yaml | Write, fix, test |
| `coding` | primary 12B | core-coding.yaml | Simple single-recipe session |

One model loaded at a time on 16GB. Switch tier:

```bash
builder switch-model fast    # edit .env, restart
builder start --mode quick
```

## Skills (auto-discovered in CORE repo)

- `core-governed-coding` — invariants + workflow
- `core-verify-loop` — edit → `builder verify` → fix
- `core-pre-edit-sweep` — trace before edit
- `core-handoff` — session continuity doc

Load explicitly: `/skills core-governed-coding core-verify-loop`

## Commands

```bash
builder setup          # config + skills + hints + recipe validation
builder pull           # pre-download models
builder start          # one-command morning startup
builder start -m quick -n my-session
builder verify algebra/versor.py
builder benchmark -o scratch/report.txt
builder status
builder config         # dump setup JSON
```

## Inference backends

`CORE_AGENT_BACKEND` in `.env`: `rapid-mlx` (default) | `mlx-lm` | `ollama`

Goose wiring:
- rapid-mlx/mlx-lm → `GOOSE_PROVIDER=openai` + `OPENAI_HOST`
- ollama → `GOOSE_PROVIDER=ollama` + `OLLAMA_HOST`

Config: `~/.config/goose/config.yaml` (merged on `builder setup`)

## In-session workflow

```
/plan Add test for near-null versor_condition     # plan first
/explore versor_apply call sites                  # read-only subagent
/implement add test in tests/test_versor...       # write + verify subagent
/verify algebra/versor.py                         # harness only
/review cosine similarity in vault proposal       # should REFUSE
/handoff                                          # end-of-session doc
```

## M1 memory notes

- Primary (~10–11 GB) + OS overhead ≈ tight on 16GB — close heavy apps
- Use `--mode quick` / `fast` tier for exploration
- Only one Rapid-MLX model loaded; swap requires backend restart

## Troubleshooting

- `goose not found` → `brew install block-goose-cli`
- Backend DOWN after start → model still downloading; wait or run `builder pull`
- Subrecipe fails → `goose recipe validate recipes/core-platform.yaml`
- Skills missing in CORE → re-run `builder setup`