# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Version control

**CRITICAL**: This repository is hosted on a private **Forgejo** server, NOT GitHub.
- Do NOT use the `gh` (GitHub) CLI, and do not push/pull/clone from `github.com`.
- Use the `tea` CLI (Gitea/Forgejo CLI) or the provided Forgejo MCP tools for issues, PRs, and repo management.

## What this is

`builder-II` is a generic **governed control plane** for local agent-assisted software development (Python 3.12, Typer/Rich/Textual CLI + TUI, optional PyO3/Rust validation accelerator). It is CORE-born but generic-first: CORE is one supported *target profile*, not builder-II's identity. Goose, deepagents, MCP, and model providers are not parallel authorities — they are wrapped as governed adapters underneath builder-II's policy/artifact/HITL boundary. See `README.md` and `docs/MANIFESTO.md` for the full philosophy; `docs/ROADMAP.md` tracks what is currently promoted vs. speculative.

The load-bearing distinctions the whole codebase enforces: **planned ≠ executed ≠ verified ≠ promoted**, **artifact ≠ authority**, **model output ≠ approval**, **subagent output ≠ truth**. Almost every subsystem exists to produce a reviewable JSON artifact (with a `kind` field) and a matching validator — not to take an autonomous action. Most write/execute/shell capabilities in this codebase are intentionally **not promoted**; check `docs/ROADMAP.md`'s "non-authority boundaries" and `docs/CAPABILITY_PROMOTION.md` before assuming a capability is live rather than a governed stub.

Primary hardware target is an Apple Silicon M1 with 16GB unified memory — keep local model footprints in the ~2–7GB range (see `docs/model_role_matrix.md`); heavier lanes are explicit opt-in candidates, not defaults.

## Reasoning & problem-solving discipline

For non-trivial design/R&D work — anything touching a load-bearing module (`command_authority.py`, `platform_completion_audit.py`, the verification/HITL lanes, promotion docs) or crossing a promotion boundary — work in this order (full version and rationale in `AGENTS.md` §6):

1. **Read the code first** — never reason from a file name or structure; trace imports/call sites and identify the invariant the module protects.
2. **Find the shape** — name the repeating structure before solving. The recurring one here is *build `kind`-tagged artifact → finalize/digest → paired `validate-*` → downstream consumes*; duplication is a symptom of an unnamed shape.
3. **Rank by leverage** (structural load removed ÷ effort) and do the high-leverage work first — not the easy work first.
4. **Enumerate every change precisely** — file, reason, and a commit message that reflects it; no "refactor"/"cleanup" on load-bearing modules.
5. **Prove against a real claim, not "tests pass"** — name the pinned assertion (a `platform_completion_audit.py` matrix row, a `test_platform_completion_truth.py` / `test_docs_truth_enforcement.py` pin, a `docs/CAPABILITY_PROMOTION.md` state, or a digest-bound artifact + `validate-*` lane) and the exact command that verifies it (smallest `uv run pytest …`, plus `builder-platform audit-docs`/`matrix` when docs/matrix change). No covering lane = a finding.
6. **Tie it to the governance model** — state which distinction it strengthens (**planned ≠ executed ≠ verified ≠ promoted**, **artifact ≠ authority**, **model output ≠ approval**) and whether it crosses a promotion boundary (which needs the eight gates + an evidence-backed matrix flip, never docs alone). builder-II has no internal cognition pipeline to map onto — this governance grammar is its model.
7. **Commit with discipline** — confirm branch, branch from `main`, PR via `tea` (never `gh`/`github.com`, never direct-to-`main`), run the smallest CI slice that proves the change.

## Commands

Environment is managed with `uv` (Python 3.12.13, locked via `uv.lock`).

```bash
uv sync --all-groups                # install deps (Python + dev group)
uv run pytest -q                    # full test suite (testpaths = tests/)
uv run pytest tests/test_foo.py -q  # single test file
uv run pytest tests/test_foo.py::test_name -q   # single test
uv run ruff check builder_ii tests  # lint (line-length 120, see pyproject [tool.ruff])
uv run mypy builder_ii/command_authority.py builder_ii/compliance.py builder_ii/hitl_patch_apply.py builder_ii/model_execution_gateway.py builder_ii/readonly_authority.py
                                     # targeted mypy — CI only type-checks these authority-sensitive modules
uv run bandit -q -r builder_ii -s B101,B105,B106,B110,B112,B404,B603,B607
uv run python -m compileall -q builder_ii tests
cargo build --manifest-path builder_ii_validation_rs/Cargo.toml   # optional Rust validation accelerator
uv run builder-platform audit-docs  # docs truth audit (fails CI if docs claim unproven capabilities)
uv run builder-platform matrix       # R0 completion truth matrix
uv run python scripts/verify_v0_release.py   # v0 structural/governance release proof harness
bash scripts/clean-clone-smoke.sh   # repeatable clean-clone onboarding + governed patch-loop smoke gate (plan 2.7)
```

`.github/workflows/ci.yml` is the authoritative gate list (Rust build → bytecode compile → docs truth audit → secret scan/gitleaks → ruff → targeted mypy → targeted bandit → full pytest). Reproduce that sequence locally before considering work done.

There is no Makefile/justfile — `uv run <tool>` and the `builder-*` console scripts (defined in `pyproject.toml [project.scripts]`, ~40 of them) are the whole surface.

## Architecture

### CLI: one lazy-loaded Typer app per concern

`builder_ii/cli/main.py` defines the `builder` root command using a custom `LazyGroup` that imports subcommand modules (e.g. `workflow`, `ledger`, `mcp`, `hitl`, `goose`, `code-vault`, `tui`) only when invoked, to keep CLI startup near-zero. Beyond the root `builder` command, `pyproject.toml` registers ~40 standalone `builder-*` console scripts (`builder-session`, `builder-hitl`, `builder-verify`, `builder-code-vault`, `builder-platform`, etc.), each backed by one `builder_ii/cli/*_cli.py` module wrapping a Typer app. When adding a new command surface, follow this pattern: a `*_cli.py` Typer app, a matching entry in `[project.scripts]`, and (if lazy) a registration in `LazyGroup`.

### Artifact-first data flow

Most non-trivial features in `builder_ii/` follow the same shape: build a governed artifact (Pydantic/dataclass model with a `kind` string) → write it as JSON → a paired `validate-*` command re-checks it (schema, digests, chain refs) → downstream commands consume it as input. Look at `docs/ARTIFACT_INDEX.md` for the registry of all artifact kinds and `docs/CAPABILITY_PROMOTION.md` / `docs/RUNTIME_PROMOTION.md` for the promotion states (`PLANNED_ONLY`, `PROPOSED_ONLY`, `SPECULATIVE`, etc.) that gate whether an artifact may ever trigger real execution.

Key artifact families (each documented under `docs/`, source mostly at repo root of `builder_ii/`):
- **Session prep**: `repo_map.py`, `context_pack.py`, `session_config.py`, `governed_prepare_package.py` — read-only repo scanning and context assembly.
- **Goose adapter**: `goose_projection.py`, `goose_wrapper_plan.py`, `goose_session.py`, `goose_readonly*.py`, `goose_launcher.py` — Goose is the operator runtime substrate; builder-II only projects governed session manifests into it.
- **HITL governance chain**: `hitl_execution_records.py`, `hitl_chain_binding.py`, `hitl_evidence_bundle.py`, `hitl_patch_proposal.py` / `hitl_patch_apply.py`, `hitl_command_execution.py` — request → receipt → postflight/verification → evidence → chain binding → (only then) an approved execution/patch candidate.
- **Verification**: `verification_execution_plan.py` → `verification_execution_approval.py` → `verification_execution_receipt.py` → `verification_execution_runner.py` (bounded to one approved `platform_status` profile, fixed argv, `shell=False`) → `verification_execution_ledger.py`.
- **Model/provider policy**: `model_client_registry.py`, `model_routing_policy.py`, `model_execution_gateway.py`, `model_router.py` — routing/capability metadata as policy artifacts; provider execution itself remains a gated, mostly-unpromoted surface.
- **deepagents adapter**: `deepagents_bridge*.py`, `deepagents_policy.py`, `deepagents_work_artifacts.py`, `deepagents_forge_*.py` (the interactive agent-creation wizard, `builder-deepagents forge`) — planning/delegation harness, governed the same way as Goose.
- **Command/capability governance**: `command_authority.py`, `capabilities.py`, `promotion_readiness_records.py`, `promotion_decision_records.py`, `governance_standard.py` — the authority-tier registry every command surface is checked against.

### CodeVault (`builder_ii/code_vault/`)

A deterministic, content-addressed "software geometry" recall substrate — coordinates derive only from stable layout identity (never source content, embeddings, or insertion order). Chain: `repo_map` → digest-bound artifacts → hierarchical frame → optional CGA lift into Cl(4,1) (`geometry/`) → optional exact recall backend (`backend/`, with a pure-NumPy reference and an optional Rust-accelerated adapter) → advisory findings (`reports/`) → context-pack projection. It is explicitly not a vector DB, not an autonomous engineer, and not a second CORE runtime — see `docs/CODE_VAULT.md` and `docs/CODE_VAULT_STAGED_ACCEPTANCE.md`. CLI surface is `builder-code-vault` (frame/digest/lint/recall/context + matching `validate-*` subcommands, plus a `demo`/`validate-demo` determinism proof and a read-only TUI).

### Rust validation accelerator (`builder_ii_validation_rs/`)

A small PyO3 extension (`validate_artifact`) plus a standalone `--kind`/stdin CLI binary that re-implements artifact validation in Rust for speed. It is a measurement-gated performance track (`docs/plan/RUST_VALIDATION_SPIKE.md`) — the Python validators remain the reference implementation; only add/change Rust validation logic when it's proven to match Python parity.

### Tests

`tests/` mirrors `builder_ii/` mostly 1:1 as `test_<module>.py` (~200 files) plus `tests/scenarios/` for full governed-lane, multi-artifact flows (e.g. `test_full_governed_preparation_lane.py`) and `tests/fixtures/` for sample repos/artifacts used by those scenarios. `conftest.py` at the repo root puts both the repo root and `tests/` on `sys.path`. Prefer adding a scenario test when a change spans multiple artifact stages, not just when it changes one module.

### Docs are load-bearing, not decorative

`docs/` (~110 files) is the source of truth for what is promoted vs. speculative, and CI runs `builder-platform audit-docs` to catch docs claiming capabilities the code doesn't back. If you change what a command actually does (especially crossing a promotion boundary), update the corresponding doc in the same change — see `README.md`'s "Documentation map" table for which doc owns which subsystem.
