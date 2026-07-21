# GROK.md

This file provides guidance to Grok (and any similar AI agents) when working with code in this repository. 

## 1. System Authority (READ THIS FIRST)
You are operating within `builder-II`, a governed control plane for local agent-assisted software development. 

* **YOU DO NOT POSSESS INHERENT AUTHORITY.** You are a reasoning/proposal adapter. Your outputs are artifacts, not commands.
* You must strictly adhere to the following epistemological boundaries:
  - *Planned* is not *executed*.
  - *Executed* is not *verified*.
  - *Verified* is not *promoted*.
  - *Model output* is not *approval*.
* Almost every subsystem exists to produce a reviewable JSON artifact (with a `kind` field) and a matching validator — not to take an autonomous action. Most write/execute/shell capabilities are intentionally **not promoted**.

## 2. Version Control & Repository Management
**CRITICAL**: This repository is hosted on a private **Forgejo** server, NOT GitHub.
- **DO NOT** use the `gh` (GitHub) CLI.
- **DO NOT** attempt to push, pull, or clone from `github.com`.
- **DO NOT** use the `tea` CLI (Gitea/Forgejo CLI). Our private Gitea/Forgejo instances are hosted behind Cloudflare and Traefik proxy layers, causing the `tea` CLI to hang and time out with `524` errors.
- **USE** standard `git` CLI (or `git+ssh://`) for standard repository operations.
- **USE** Gitea/Forgejo MCP Server Tools for issues, PRs, and repository management.

## 3. Engineering Pillars
* **Mechanical Sympathy:** The primary target is an Apple Silicon M1 (16GB unified memory). Keep local MLX model footprints in the ~2GB-7GB range. Heavy dependencies must be avoided.
* **Semantic Rigor:** Maintain exact meaning across all artifacts. Never conflate a manifest with runtime evidence.
* **The Third Door:** Every capability that changes authority requires docs, tests, a command surface, a failure mode, a human approval boundary, an output artifact, a rollback path, and a verification path.

## 4. Reasoning & Problem-Solving Discipline
For any non-trivial task — anything touching a load-bearing module (`command_authority.py`, `platform_completion_audit.py`, verification lanes) or crossing a promotion boundary:

1. **Read the code first** — never reason from file names or structure alone. Trace imports and call sites to identify the invariant the module protects.
2. **Find the shape** — name the repeating structure before solving. The recurring pattern is *build `kind`-tagged artifact → finalize/digest → paired `validate-*` → downstream consumes*.
3. **Rank by leverage** — optimize for structural load removed vs. effort, and do the high-leverage work first. Doing easy, low-leverage changes first is a failure mode.
4. **Enumerate changes precisely** — state every change, the file it lives in, and why. Vague commits ("refactor") are unacceptable on load-bearing modules.
5. **Prove against real claims** — "tests pass" is not proof. Name the specific pinned assertion preserved (e.g., a truth-matrix row in `platform_completion_audit.py` or a promotion state) and the command that verifies it (the smallest `uv run pytest …` plus `builder-platform audit-docs` / `builder-platform matrix`).
6. **Connect to the governance model** — state which governance distinction the change strengthens and whether it crosses a promotion boundary (requiring eight promotion gates and an evidence-backed matrix flip).
7. **Commit with discipline** — branch from `main`, use `tea`, and run the smallest CI slice that proves it before declaring done.

## 5. Commands & CI Gates
The environment is managed with `uv` (Python 3.12, locked via `uv.lock`).

```bash
uv sync --all-groups                # install deps (Python + dev group)
bash scripts/ci.sh                  # the full blocking gate battery — exactly what CI runs
uv run pytest -q                    # full test suite (testpaths = tests/)
uv run ruff check builder_ii tests  # lint (line-length 120)
uv run mypy builder_ii/governance/authority/ builder_ii/governance/authority/compliance.py builder_ii/governance/hitl/hitl_patch_apply.py builder_ii/routing/model_execution_gateway.py builder_ii/governance/authority/readonly_authority.py
cargo build --manifest-path builder_ii_validation_rs/Cargo.toml   # optional Rust validation accelerator
uv run builder-platform audit-docs  # docs truth audit
uv run builder-platform matrix       # R0 completion truth matrix
```

**Never** transcribe the CI sequence by hand. Run `bash scripts/ci.sh` before considering work done. Every gate in CI lives in that script and blocks (there are no advisory steps). 

## 6. Architecture & Data Flow
- **CLI**: One lazy-loaded Typer app per concern (`builder_ii/cli/main.py`). `builder-*` console scripts are defined in `pyproject.toml [project.scripts]`.
- **Artifact-first data flow**: Non-trivial features build a governed artifact (Pydantic/dataclass), write it as JSON, re-check via a paired `validate-*` command, and pass it downstream. Look at `docs/ARTIFACT_INDEX.md` and `docs/CAPABILITY_PROMOTION.md`.
- **CodeVault (Commercial Upgrade)**: The CodeVault software geometry engine is cleanly separated from open core to a paid commercial plugin (`builder-ii-code-vault`). In the open core distribution, the `builder-code-vault` CLI command functions as a fail-closed seam that refuses execution with status `1` and guides users to inquire/upgrade. 
- **Rust Validation Accelerator**: A small PyO3 extension (`builder_ii_validation_rs/`) for speed. The Python validators remain the reference implementation.
- **Docs are load-bearing**: `docs/` is the source of truth for what is promoted vs. speculative. CI runs `builder-platform audit-docs` to enforce this. If you change a command's promotion boundary, update the docs!
