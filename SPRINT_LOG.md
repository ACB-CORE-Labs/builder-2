# SPRINT_LOG — feat/governance-proof-sprint-001

Governance proof sprint (reapply of broader DDD work + skeptic fixes + reapply defect fixes).

## 2026-08-20 — Open-Source V1 Plan Set 3C1

- Added passive MCP `patch_proposal`, sharing one canonical exact-digest and exact-scope proposal
  binder with `builder-hitl propose-patch`; MCP binds only its configured target and controlled
  verification-receipt bytes, chooses Builder-II artifact output, returns
  `HUMAN_APPROVAL_REQUIRED`, and stops.
- Retired the legacy MCP `propose_patch -> run_gated_patch_apply` mutation bridge, advertised
  `run_shell`, `BUILDER_MCP_GOVERNED_APPLY` reactivation path, adapter, and obsolete G4 tests.
  Canonical operator-side HITL approval/apply/rollback remains separate and unchanged.
- Adversarial qualification pins digest changes, traversal/symlink/oversize/corrupt evidence
  refusal, controlled output, exact target identity, target fingerprint invariance, zero calls to
  approval/apply/rollback/subprocess boundaries, and inventory-first denial of retired tools.
- Local qualification: focused MCP/HITL/authority suite passed; Ruff passed; documentation truth
  audit passed; platform matrix passed without promotion; `bash scripts/ci.sh` passed with 2,820
  tests passed, 1 skipped, and all blocking gates passed.
- State remains implementation working tree only: no commit, push, PR, merge, capability
  promotion, approval minting, MCP patch application, or Plan Set 3C2 authority.

## Phase 0 — Territory verification
- Wrote `VERIFICATION_REPORT.md` (claimed vs confirmed vs discrepancy).
- Key territory wins: CI already exists; no `requirements.txt`; `deepagents_forge_cli` under `cli/`; partial packages already present; default backend was `mlx-lm`.

## Phase 1 — DDD layout + authority shatter
- Vertically sliced flat modules into:
  - `adapters/{goose,deepagents,openai_compat}`
  - `governance/{hitl,authority,ledger}`
  - `lifecycle/{setup,candidate}`
  - `routing/`, `validation/`, `core/`
  - preserved `cli/`, `tui/`, `targets/`, `wrp/`
- Zero loose `builder_ii/*.py` outside `__init__.py`.
- Split `command_authority` monolith into:
  - `tier_definitions.py`
  - `authority_registry.py`
  - `policy_evaluator.py`
  - `signet_verifier.py` (assurance lattice only — not crypto)
- Compat: meta-path aliases + `builder_ii.command_authority` → `builder_ii.governance.authority`.
- `REFACTOR_MAP.md` origin → destination.

### Skeptic fixes
- Regen/docs/tests: `python -m builder_ii.governance.authority` (not `builder_ii.authority`).
- `docs/COMMAND_AUTHORITY.md` regenerated from generator.
- `artifacts/opus_phase_4_evidence/reproduce.sh` imports `builder_ii.governance.authority`.
- Artifact kind `builder_ii.command_authority` restored (not `builder_ii.authority`).
- False path `builder_ii.authority` correctly fails.

### Additional defects fixed during reapply
1. Restored missing `@dataclass(frozen=True)` on `CommandAuthorityRecord`.
2. `BUILDER_II_IMPORT_ROOT = Path(__file__).resolve().parents[3]` (was wrong after nest).
3. Demoted inflated artifact kind strings back to short `builder_ii.<leaf>` forms.
4. Rebuilt `MODULE_ALIASES` after corruption (self-aliases like `gate_battery_receipt → builder_ii.gate_battery_receipt`).
5. mypy file list: explicit modules only (no package directory + file duplicate).
6. `_live_registry()` so monkeypatches on the public package rebind validation.
7. SourceLoader-based alias so `python -m builder_ii.gate_battery_receipt` works.
8. `target_profile_defaults` project root depth `parents[3]`.

## Phase 2 — Hygiene
- Removed `commit_msg.txt`, `replace_script.py`, `patch_conflicts.sh`.
- Moved `run_all_tests.py`, `verify_local_models.py` → `scripts/ops/`.
- `.gitignore` ops pollution patterns.
- `artifacts/` / `docs/audits/` already real (no fabrication).

## Phase 3 — Docs
- `QUICKSTART.md` — ollama-first, HITL closed loop via `clean-clone-smoke` + scenario pins.
- `LEXICON.md` — full translation table.
- `README.md` — CI badge, scenario trust call-outs, and commercial-plugin boundary note.

## Phase 4–5 — CI + portability
- Did **not** replace `scripts/ci.sh` battery.
- `.github/workflows/ci.yml` job env: `BUILDER_MODEL_BACKEND=ollama`.
- Code default backend: `ollama` (`config.py`, `config_schema.py`, `.env.example`).
- Optional extras: `mlx` + `apple` alias in `pyproject.toml`.

## Phase 6 — CodeVault
- Open core retains only an opaque fail-closed commercial-plugin seam and upgrade URL.
- `repo_map` `upgrade_hint` only when `truncated=True`.
- `tests/test_codevault_upsell.py`.

## Verification
- `bash scripts/ci.sh` (run after this log update for final proof).
- Authority import smoke: `check_command_authority` + 467 records.
- Paths: governance.authority ✅ / command_authority alias ✅ / authority ❌.
