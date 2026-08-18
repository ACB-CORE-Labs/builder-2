# builder-II Quickstart

Pure mechanics. v1 supports **Linux** and **macOS Apple Silicon**. Windows and WSL2
are not v1 release-parity targets.

## Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) (recommended) or pip
- Optional for model-backed demos: [Ollama](https://ollama.com)
- Git

## Install in 60 Seconds

```bash
git clone <this-repo-url> builder-II
cd builder-II
export BUILDER_MODEL_BACKEND=ollama   # recommended open-source / non-Apple path
uv sync --all-groups
# Full native-orchestration development lane:
uv sync --all-groups --extra deepagents
# Apple Silicon MLX (optional): uv sync --extra mlx   # or: pip install -e '.[apple]'
cp .env.example .env
```

## Boot builder-II

```bash
uv run builder-platform status
uv run builder doctor
# Optional TUI:
uv run builder-platform tui
```

## Watch Governance Work

Closed loop: **propose → intercept → approve → commit**.

Fastest proof (fixture repo, no live model required for the patch lane):

```bash
bash scripts/clean-clone-smoke.sh
```

That smoke gate runs onboarding plus one full generic governed patch loop
(propose → approve → verify → apply → rollback).

Scenario trust pins:

- `tests/scenarios/test_hitl_orchestration.py`
- `tests/scenarios/test_wrp_full_lane.py`
- `tests/scenarios/test_hitl_patch_lane_unmocked.py`

Longer walkthrough: [`FIRST_SESSION.md`](FIRST_SESSION.md).

## What Just Happened

An agent may only **propose** mutations as digest-bound artifacts; builder-II intercepts
unapproved writes, requires human approval bound to those digests, and only then executes —
planned ≠ executed ≠ verified ≠ promoted.

## Next Steps

- [`LEXICON.md`](LEXICON.md) — vocabulary translation table  
- [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md)  
- [`docs/OPERATOR_QUICKSTART.md`](docs/OPERATOR_QUICKSTART.md)
