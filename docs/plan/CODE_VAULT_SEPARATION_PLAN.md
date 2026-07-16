# CodeVault Separation & Decoupling — Execution Plan

**Status:** PLANNED_ONLY (planning artifact; no capability promoted by this doc)
**Branch:** `feat/code-vault-separation-20260715`
**Worktree:** `~/Projects/builder-II-codevault-split` (isolated; `main` never touched directly)
**Author:** authored brief for operator-dispatched agents — this doc dispatches nothing.

---

## 0. Locked decisions

1. **Severance strategy — Optional-dependency + thin explicit registry.**
   Reuse the idiom already present in `builder_ii/semantic_readonly.py:121`
   (`try: import builder_ii.code_vault…; except ImportError: fallback`). Core's
   `command_authority.py` authority manifest stays **static and fail-closed**; the
   proprietary package ships its **own** frozen authority manifest, audited in its own
   repo. A thin explicit plugin registry handles only *light-up* re-attach of
   validators / CLI / enrichment — it never mutates the governance authority manifest.
   **Rejected:** `entry_points` auto-mutation of core registries (would make the
   authority manifest dynamically mutable — a governance regression needing the 8 gates).

2. **Proprietary package home — new Forgejo repo `core-labs/builder-ii-code-vault`.**
   Physically proves zero `core → proprietary` import coupling and keeps CodeVault
   severable/private. Repo creation is **operator-gated** (see `repo-stays-private` /
   D2·D3·D8). Until it exists, assemble the package in a sibling worktree.

## Governance framing

Strengthens **artifact ≠ authority** and **model output ≠ approval** by making CodeVault a
cleanly optional capability whose *absence is fail-closed*, never a silent surface the core
audit cannot see. Crosses a promotion boundary in `command_authority.py` (removing rows from
the core manifest) → requires the eight gates + evidence-backed matrix update, not docs alone.

---

## 1. Verified premise (traced against code @ `main` 16c1e4d)

**Every CodeVault coupling is additive-optional — core loses zero capability.**

- Context packs, governed prepare package, convention kernel, workflow orchestration,
  artifact index/chain validation (core kinds), semantic readonly, full TUI, and the
  `audit-docs`/`matrix`/docs-truth gates **all function with `code_vault/` absent.**
- What goes dark with CodeVault absent = exactly the paid upgrade: hierarchical frames,
  recall, geometric lint, CGA lift, and the context-pack enrichment overlay.

### Corrections to the source plan (do not repeat these)
- ❌ `platform_completion_audit.py` / `compliance.py` do **not** reference code_vault. The
  audit is coupled **transitively** (imports `artifact_index_records` → eager
  `builder_ii.code_vault.*`), not directly. Fix the transitive chain, not those files.
- ⚠️ The prepare/context imports are **eager top-of-file**, not lazy — deleting `code_vault/`
  breaks `import` of those modules today despite their runtime `include_code_vault` flag.
- ➕ Missed sites now included below: `artifact_index_records.py`, `convention_kernel.py`,
  `workflow_orchestrator.py`, `tui/projections/codevault.py`, `code_vault_receipt_bridge.py`,
  `cli/session_cli.py`, `cli/tui_inspection_cli.py`, and the count pin at
  `tests/test_command_authority.py:874` (asserts 102, traces CodeVault G1/G2 additions).

### Severance map

| Site | Coupling | Treatment | Core behavior when absent |
|---|---|---|---|
| `semantic_readonly.py:121` | already `try/except ImportError` | **no change** (reference idiom) | symbol samples empty |
| `code_vault_provenance.py` | pure `.git`, no code_vault import | stays in core (optional rename) | n/a |
| `artifact_chain_verification.py` (`VALIDATORS` @452) | eager import → literal entries @519,582 | guard import; conditional `.update()` | core kinds validate |
| `artifact_index_records.py` (`_VALIDATORS` @475) | eager imports @27-82 → entries @539,609 | guard import; conditional `.update()` | core kinds validate |
| `context_packs.py:7-9` | eager import; validator already optional (`.get`) | lazy/guard merge import | packs built; no enrichment |
| `governed_prepare_package.py:8,14` · `convention_kernel.py:12,18` · `workflow_orchestrator.py:12,17` | eager import + runtime `include_code_vault` flag | move imports inside the flag block (pattern at `governed_prepare_package.py:453`) | artifacts built; no frame ref |
| `tui/projections/codevault.py` | **pure JSON reader** | **stays** as viewer | CodeVault tab shows "upgrade" |
| `tui/projections/__init__.py` · `tui/app.py` (`b` bind) · `tui/widgets/stratum.py` (mode) | reference the reader | keep | all tabs work |
| `command_authority.py` (group row @1169; `_EXTRA_COMMAND_NAMES`) | code-vault rows in core manifest | remove from core; proprietary ships own manifest | core manifest static & complete-for-core |
| `cli/main.py:38` · `cli/tui_inspection_cli.py` · `cli/session_cli.py:473` | lazy reg / string dispatch / flag | fail-closed "not installed / upgrade" | `builder` CLI works |
| `code_vault_receipt_bridge.py`, `code_vault_demo_loop.py`, `code_vault_tui.py`, `utility_baseline_runner.py`, `cli/code_vault_cli.py` | import code_vault package | **move to proprietary** | n/a (CodeVault features) |
| `docs/ARTIFACT_INDEX.md` (14), `docs/CAPABILITY_PROMOTION.md` (8), all `CODE_VAULT*.md` + ADR-0005/0006 | `audit-docs` cross-check | relocate code-vault rows to proprietary docs | gates green |
| 38 `test_code_vault_*` + `scenarios/test_code_vault_receipt_bridge_lane.py` | — | **move** to proprietary | — |
| `test_context_packs`, `test_convention_kernel_platform_spine`, `test_governed_prepare_package`, `test_session_prepare_package_kernel_spine_e2e`, `test_stratum_projections`, `test_workflow_ledger`, `test_command_authority` | assert code_vault behavior | **edit**: drop code-vault assertions; update count pin | — |

---

## 2. Phased plan (each phase = pinned assertion + smallest verifying command)

> Roles are labels for operator dispatch, not autonomous agents. Every phase ends by
> running the named command; a phase is not "done" until its assertion is proven.

### Phase 0 — Isolation (DONE for setup; no code changes)
- Branch + worktree created off clean `main`; this doc is the planning artifact.
- **Proof:** `bash scripts/ci.sh` green as a **baseline** before any edit.
- Task: `cd ~/Projects/builder-II-codevault-split && uv sync --all-groups`.

### Phase 1 — Absence test first (RED)  · role: TDD
- Add `tests/test_code_vault_absence.py`: with `builder_ii.code_vault` import-blocked
  (e.g. `sys.modules` sentinel / `builtins.__import__` shim), assert imports of
  `platform_completion_audit`, `artifact_index_records`, `artifact_chain_verification`,
  `context_packs`, `convention_kernel`, `workflow_orchestrator`, `governed_prepare_package`
  **all succeed**, and a context pack + governed prepare package still build.
- **Pinned assertion:** the new test. **Proof (must fail now):**
  `uv run pytest tests/test_code_vault_absence.py -q` → RED.

### Phase 2 — De-eager registries & producers (highest leverage) · role: ENGINEER
- Guard imports + conditional `.update()` in the two registries; move producer imports
  inside `include_code_vault` blocks; guard `context_packs` merge import.
- **Proof:** `tests/test_code_vault_absence.py` GREEN; plus
  `uv run pytest tests/test_artifact_index_records.py tests/test_artifact_chain_verification.py tests/test_context_packs.py tests/test_convention_kernel_platform_spine.py tests/test_governed_prepare_package.py tests/test_workflow_ledger.py -q`.

### Phase 3 — Authority manifest + CLI/TUI fail-closed · role: ENGINEER + governance review
- Remove code-vault group row + `_EXTRA_COMMAND_NAMES` prefix-clones from core
  `command_authority.py`; update the count pin at `tests/test_command_authority.py:874`
  (with a comment tracing the removal); make `cli/main.py:38`, `cli/tui_inspection_cli.py`,
  `cli/session_cli.py` fail-closed; keep the TUI viewer tab in an "upgrade" state; scrub
  `stratum_guide.py` help strings.
- **Proof:** `uv run pytest tests/test_command_authority.py tests/test_stratum_projections.py -q`
  + `uv run mypy builder_ii/command_authority.py`.

### Phase 4 — Extract proprietary package · role: FORGE (operator-gated repo)
- Move to `builder-ii-code-vault`: `code_vault/`, seam roots
  (`code_vault_receipt_bridge`, `code_vault_demo_loop`, `code_vault_tui`,
  `utility_baseline_runner`), `cli/code_vault_cli.py`, the 39 code-vault tests, all
  `CODE_VAULT*` docs + ADR-0005/0006. Package declares `builder-II>=<pin>` and registers
  its validators/CLI/enrichment + its **own** authority manifest via the thin registry on import.
- **Proof:** proprietary CI installs core + package; the **same** 39 tests pass there.

### Phase 5 — Core-only gate battery + docs truth · role: HERALD + AUDITOR
- Relocate code-vault kind rows out of `docs/ARTIFACT_INDEX.md` / `CAPABILITY_PROMOTION.md`.
- **Proof:** `uv run builder-platform audit-docs` + `uv run builder-platform matrix` green;
  then full `bash scripts/ci.sh --receipt scratch/receipt.json` on the core worktree.

### Phase 6 — Light-up integration + promotion · role: operator
- Install proprietary into a venv with core; prove `builder-code-vault`, enrichment, and the
  CodeVault tab reappear identically. `tea` PR → `main`; eight-gate review; **no autonomous merge.**

---

## 3. Guardrails (cannot screw up `main`)
- All edits in the worktree; `main`'s working tree stays clean. PR via `tea` only (never `gh`).
- **Decoupling ≠ publication.** `git-filter-repo` history-excision and any public repo are a
  **separate, later, operator-only** phase — never on this branch or `main`.
- **Rollback:** `git worktree remove ~/Projects/builder-II-codevault-split` +
  `git branch -D feat/code-vault-separation-20260715` if any gate fails irrecoverably.
- Concurrent Codex/Gemini/Grok worktrees exist — re-check `git worktree list` before any op.
