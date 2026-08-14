# Phase 0 — Verification Report

**Status:** COMPLETE — construction permit issued (operator approved broader DDD + skeptic fixes).  
**Branch:** `feat/governance-proof-sprint-001`  
**Repo worktree:** this builder-II checkout  
**Date:** 2026-07-20  
**Sources:** Master Build Brief + `/Users/kaizenpro/Downloads/builder-II_multi-agent_critiques.md` vs live tree

**Doctrine:** Territory (codebase) wins when map (brief) conflicts; conflicts are logged, not rationalized.

---

## 1. Claim matrix (pre-refactor baseline, measured on main)

| # | Claim | Claimed | Confirmed | Status |
|---|---|---|---|---|
| C1 | Flat `builder_ii/` sprawl ~130+ files | ~130+ | **192** excl. `__init__.py` | CONFIRMED (worse) |
| C2 | `command_authority.py` ~300KB | ~300KB | **300065 bytes / 5409 LOC** | CONFIRMED |
| C3 | `deepagents_execution.py` ~157KB | ~157KB | **157803 bytes** | CONFIRMED |
| C4–C5 | Scenario tests exist | yes | `tests/scenarios/test_wrp_full_lane.py`, `test_hitl_orchestration.py` | CONFIRMED |
| C6–C10 | Ledger / HITL modules at flat root | yes | present pre-refactor | CONFIRMED |
| C11 | `builder_ii_validation_rs/` | yes | present | CONFIRMED |
| C12–C13 | `artifacts/`, `docs/audits/` populated | yes | real digests + audit markdown | CONFIRMED |
| C14–C16 | Root junk files | present | `commit_msg.txt`, `replace_script.py`, `patch_conflicts.sh` | CONFIRMED |
| C17 | `run_all_tests.py` | 85B stub | **85 bytes** (not the real suite) | CONFIRMED |
| C18–C20 | goose/hitl/model_router at flat root | yes | yes pre-refactor | CONFIRMED |
| C21 | `deepagents_forge_cli.py` at flat root | yes | **NO** — `builder_ii/cli/` | DISCREPANCY |
| C22 | Fully flat package | implied | **cli/, tui/, targets/, wrp/** already packages | DISCREPANCY |
| CI | “Create ci.yml” | create | **Already exists** → `scripts/ci.sh` | DISCREPANCY |
| Deps | `requirements.txt` | use it | **pyproject.toml + uv.lock only** | DISCREPANCY |
| Backend | Implement `BUILDER_MODEL_BACKEND` | implement | **Already present**; default was `mlx-lm` | PARTIAL |
| CodeVault | Upsell message | insert | Fail-closed seam existed; message refined | PARTIAL |

---

## 2. Architectural note (command_authority)

The monolith is a **static registry + check/enforce + assurance derivation + doc render**, not a crypto “Builder’s Signet verifier.”  
Sprint split (structure-true names):

| Module | Role |
|---|---|
| `tier_definitions.py` | Tier / promotion / approval constants |
| `authority_registry.py` | Records, registry table, validate, doc render body |
| `policy_evaluator.py` | `check_command_authority` / `enforce_command_authority` |
| `signet_verifier.py` | Assurance lattice derivation (**not** invented crypto) |

Public path: `builder_ii.governance.authority`  
Historical alias: `builder_ii.command_authority`  
**Not** a path: `builder_ii.authority` (skeptic-corrected false claim)

---

## 3. Post-sprint state (this branch)

- Zero loose `builder_ii/*.py` outside `__init__.py`
- DDD packages under adapters / governance / lifecycle / routing / validation / core
- Hygiene, QUICKSTART, LEXICON, README badge + trust call-outs
- Default + CI + docs path: `BUILDER_MODEL_BACKEND=ollama`; mlx via `[mlx]` / `[apple]` extras
- CodeVault: `CODEVAULT_URL`, truncation-only `upgrade_hint`, live CLI voice preserved

---

## 4. Additional defects fixed during reapply

1. Missing `@dataclass` on `CommandAuthorityRecord` after split  
2. `BUILDER_II_IMPORT_ROOT` parent depth after nesting under `lifecycle/candidate/`  
3. Artifact **kind** string inflation from import rewrite → demoted to stable short forms  
4. Corrupted `MODULE_ALIASES` self-maps → rebuilt from filesystem  
5. mypy “duplicate module” from listing a package directory + files  
6. Registry monkeypatch contract via `_live_registry()`  
7. `python -m builder_ii.<short>` SourceLoader alias (e.g. gate battery receipt)  
8. `target_profile_defaults` project-root depth  

---

*Territory wins. Permit executed on this branch.*
