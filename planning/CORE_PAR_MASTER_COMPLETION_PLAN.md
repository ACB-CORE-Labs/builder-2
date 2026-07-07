# builder-II → CORE Par: Master Completion Plan

**Version:** 1.0 (adversarially reviewed)
**Date:** 2026-07-07
**Status:** AWAITING OPERATOR REVIEW — not adopted, no execution authorized
**Location note:** This file lives in `scratch/` (gitignored) deliberately. It contains capability names
combined with promotion-state language that would trip `builder-platform audit-docs` /
`scan_docs_for_false_completion` if placed under `docs/`. When adopted, a safe-phrasing summary can be
derived for `docs/plan/` — do not move this file there verbatim.

---

## Decision log

| # | Decision | Ruling | Date |
| --- | --- | --- | --- |
| D1 | Plan adoption | **ON HOLD** — operator reviewing; may delegate parts to cheaper agents | 2026-07-07 |
| D2 | License | **DEFERRED** until operator takes the repo public. Repo is private and STAYS private. | 2026-07-07 |
| D3 | Git history strategy | **DEFERRED** until open-sourcing. | 2026-07-07 |
| D4 | CodeVault Tier-1 in beta | **CUT to post-beta** (v0.2 flagship). Doctrine-amendment RFC may be authored during beta as design-only. | 2026-07-07 |
| D5 | STRATUM TUI for beta | **Gate behind `--experimental`** (committed by plan; wiring post-beta) | 2026-07-07 |
| D6 | Non-Mac support | **Extras-gate mlx deps now; Mac-first beta with honest boundary; full Linux CI post-beta** (committed by plan) | 2026-07-07 |
| D7 | Sandbox model for pytest verification lane | **RECOMMENDED, not yet ratified:** env-allowlist subprocess + explicit HITL execution-risk acknowledgment field in the approval artifact; container isolation post-beta | pending |
| D8 | Public hosting destination | **DEFERRED** (with D2/D3) | pending |

### ⚠ Standing authority boundary

**The repository visibility is PRIVATE and must remain PRIVATE.** No agent has authority to change
repo visibility, publish, mirror, or push this repository anywhere public. Only the operator may do
this, personally, when they decide to open-source. All Phase 3 "publication" items are
*preparation-only* until that moment.

---

## Goal and exit criteria

"CORE par" = mastery-grade completion, fit for gifting to a select community of senior engineers.

- **(a)** A stranger clones the repo, onboards in ≤30 minutes, and runs one complete governed patch
  loop — propose → approve → apply → verify → rollback — **on their own repo**, with receipts at every step.
- **(b)** Onboarding is a single validated path, not ~40 README commands.
- **(c)** The repo is legally and hygienically giftable (license, community files, PII-clean, secret-scanned).
- **(d)** The demo is credible to skeptical senior engineers — governance *felt*, nothing fake on screen.

**Numbering note:** the B4.x / Phase-N taxonomy below is plan-internal. It does not exist in repo
docs. `docs/audits/B4_CLOSURE_AUDIT.md` is a *deliverable* of this plan, not an existing reference.

---

## Verified current state (evidence: `evidence/*.json`, 7-domain audit, 2026-07-07)

- Truth matrix: 15/51 capabilities OPERATIONALLY_VERIFIED; 25 PASSIVE_FOUNDATION; 5 MERGED_BUT_NOT_OPERATIONAL; 5 NOT_STARTED; 1 ARTIFACT_ONLY.
- Test suite: 1,533 tests green in ~39 s.
- The B4 patch/rollback **executors are real and merged** (`hitl_patch_apply.py`), already exercised
  end-to-end by the CORE demo loop on a detached worktree. What's missing is the *generic governance
  envelope*, not the mechanics.
- **Known security gap:** any JSON file with a matching `patch_digest` authorizes mutation
  (`hitl_patch_apply.py` ~line 237); command authority accepts any non-empty `approval_ref`
  (`command_authority.py` 334-336). Closed by work item 1.1.
- pytest verification profile is declared but **unrunnable** (naming-invariant violation vs
  `_validate_fixed_profile`); receipts carry no commit identity; timeout is fixed 30 s.
- CodeVault is a deterministic layout-geometry artifact system; no content-derived encoding exists (cut to post-beta per D4).
- No LICENSE/CONTRIBUTING/SECURITY/CHANGELOG/tags. PII in 22 tracked files; `assetoverflow@icloud.com`
  on all 614 commits; 63 local + 172 remote branches + 1 stash never content-scanned.
- STRATUM TUI shows fake tier evaluation, fabricated chain digest, notify-only approvals; splash
  compile-runs Swift via subprocess at launch.
- `builder-goose start-readonly`: docs pin it Tier 4 forbidden citing a test file that **does not
  exist** (`tests/test_goose_cli.py`); registry says Tier 3; code actually launches Goose.

---

## Delegation guide

Every work item is tagged for the operator's stated intent of using cheaper agents where safe:

- **[A]** Mechanical — cheap/fast agent OK with a clear spec; operator spot-check.
- **[B]** Standard engineering — mid-tier agent; operator reviews the diff.
- **[C]** Doctrine-critical — senior agent (high effort) + mandatory operator HITL review.
  These touch authority boundaries, promotion state, or execution envelopes.

Rule of thumb: anything editing `command_authority.py`, `platform_completion_audit.py`, the pinned
truth tests, promotion docs, or execution paths is [C]. Anything that could be reverted with
`git checkout` and no governance consequence is [A].

---

## Phase 0 — Truth & Safety Hardening

*Low risk, mostly parallel. Owns docs-truth pins only; NO matrix flips in this phase.*

| # | Item | Tier | Notes |
| --- | --- | --- | --- |
| 0.1 | Fix apply failure path: dangling `rollback_plan_ref` in failure receipt (references a file only written on success); add rollback failure receipt; **stop executors self-stamping `OPERATIONALLY_VERIFIED` / `MUTATION_WITH_ROLLBACK_VERIFIED` in their own governance fields** while the matrix says BLOCKED_BY_EVIDENCE | B | `hitl_patch_apply.py` lines ~174-189, 271-286, 314, 383-387, 484-486 |
| 0.2 | Fix phantom command **in code**: `session_cli.py:582` advertises nonexistent `builder-hitl plan-patch` | A | Real commands: propose-patch / apply-patch / rollback |
| 0.3 | Docs drift reconciliation — **candidate/not-enabled phrasing ONLY**: fix outright falsehoods (`docs/HITL_PATCH_PROPOSAL.md` "no patches are applied by any current code path"). Enabled-state language is reserved for the 1.7 flip. `CAPABILITY_PROMOTION.md` §6/7 + `RUNTIME_PROMOTION.md` non-promotion statement move to 1.7, NOT here | C | Else `builder-platform audit-docs` fails or we commit promotion-by-documentation |
| 0.4 | Typing gate: add `[tool.mypy]` to pyproject **reproducing the existing 5-module CI scope first**, then add the 5 already-passing authority modules (hitl_command_execution, hitl_patch_proposal, verification_execution_plan, tool_invocation_gateway, readonly_inspection_promotion); add `types-PyYAML`; fix `goose_command_proposal.py` 7 union-attr NoneType crashes | A | Unblocks 3 more HITL modules for typing |
| 0.5 | Tests for `hitl_command_runner.execute_hitl_command` — the human-approved subprocess path has **zero** coverage | B | |
| 0.6 | Presentation truth: remove README "rock-solid/flawlessly supports" cloud claims; fix splash tagline ("CORE-native" contradicts generic-first doctrine); **remove Swift compile-run subprocess from TUI splash** (portability bug on the 30-min path — fails on machines without Xcode toolchain) | A | `builder_ii/tui/widgets/splash.py:60-120` |
| 0.7 | Delete `agent_tui.py` (1,173 dead lines, no importer) after confirming palette-contract intent (comments in `hitl_tui.py:7`, `profile_tui.py:15`) | A | |

*The former "harden approval boundary NOW" item is merged into 1.1 (sequencing critic: an interim fix
B4.1 rewrites weeks later is duplicated work for one operator).*

## Phase 1 — The Loop (B4 generic promotion) — critical path

Execution order within phase is load-bearing.

| # | Item | Tier | Notes |
| --- | --- | --- | --- |
| 1.1 | **B4.1 (first):** generic `builder_ii.hitl_patch_approval` artifact kind + `builder-hitl approve-patch` CLI with **interactive TTY prompt at the decision point** (diff + digest shown at the moment of approval). Includes: `expires_at` **enforced inside `apply_hitl_patch`** (no decorative fields); `CommandAuthorityRecord` registration; artifact-index + chain-verification registration; documented threat model (operator-only invocation; *artifacts are evidence, not authority*). Closes the weak-approval security gap — honestly: *narrows* it; the TTY moment is what makes it real | C | New CLI surfaces MUST be registered or `validate_command_surfaces` fails matrix validation |
| 1.2 | **Ladder slice** (true B4.2 prerequisite set — ladder items 1, 2, 3, 8): (a) pytest profile naming-invariant fix; (b) commit identity (HEAD SHA/branch) in git state + **receipt schema bump sequenced BEFORE any B4 fixtures/evidence are authored**, with explicit dual-version-tolerance decision; (c) bounded `pytest_full` promotion with three BLOCKING prerequisites: sandbox/trust decision (D7), timeout policy (fixed 30 s is a hard blocker), pytest-byproduct ignore-globs **pinned inside the fixed profile with observed byproducts recorded in postflight** (an ignore channel is where a malicious patch hides writes); (d) `builder_full` extension in **both** the plan validator AND the runner's hardcoded `expected_ref` (line ~141) | C | Executing a stranger repo's tests = executing their code with user authority. D7 must be ratified first |
| 1.3 | **B4.2:** generic pre/post-apply verification receipt lane for arbitrary target repos | C | Depends on 1.2 complete |
| 1.4 | **B4.3:** distinct rollback human approval + rollback failure receipt | B | Today the machine-generated rollback plan path doubles as the "approval" |
| 1.5 | **Route apply/rollback through the command-authority gate at execution time** — `apply_hitl_patch` never consults the gate; flipping the matrix without this promotes a write lane that bypasses the gate the matrix cites as promoted | C | Critic-found omission |
| 1.6 | **B4.5 + B4.6:** unmocked E2E tests (real schema-valid approval + verification artifacts — current tests monkeypatch `VALIDATORS` and mock receipt validation) + CLI-level denial tests + ledger event emission for apply/rollback (zero ledger integration today) | B | |
| 1.7 | **B4.7 → B4.8:** receipts-backed live closure audit (`docs/audits/B4_CLOSURE_AUDIT.md`) → then ONE atomic flip commit: matrix rows, `operationally_verified_count` 15→17, both BLOCKED_BY_EVIDENCE asserts, `operationally_incomplete` flag, `render_human_summary` strings, `CAPABILITY_PROMOTION.md` §6/7, `RUNTIME_PROMOTION.md` non-promotion statement. Evidence first, flip second — never the reverse | C | Owns the pinned truth tests for this phase |
| 1.8 | **B4.9:** generalize demo loop to generic targets (parameterize marker patch + CORE sensitive-path checks; generalize worktree prep beyond `_ensure_core_repo`; replace `core_demo_approval` with the 1.1 generic kind) + **second pin edit** (CORE demo loop matrix row; decide whether the `core_demo_verification_receipt` fallback in `_verification_receipt_errors` survives) | B/C | Feeds Phase 3 demo |

## Phase 2 — The Door (R1 minimum onboarding)

| # | Item | Tier | Notes |
| --- | --- | --- | --- |
| 2.1 | **Doctrinal prerequisite:** reconcile `builder-goose start-readonly` promotion state BEFORE touching it. `CAPABILITY_PROMOTION.md` §7 pins Tier 4 forbidden citing `tests/test_goose_cli.py` **which does not exist**; registry says Tier 3; code launches Goose. Run the `RUNTIME_PROMOTION.md` read-only checklist (denied-action tests, no-mutation postflight, interruption recovery) and write real launch/close tests | C | Critique panel's one fatal doctrine flaw |
| 2.2 | **`builder init` unified orchestrator** over the **existing** 4-decision wizard + registry-validated answers + documented defaults for the remaining ~5 decisions. Init emits plan artifact + digest and requires **digest re-entry or a separately invoked apply step** — the process that renders a digest must not also harvest the confirmation. `CommandAuthorityRecord` + operator-status coverage included | C | Wizard-framework extraction + 9-decision wizard v2 = post-beta (infrastructure-before-need) |
| 2.3 | MockPlan removal (`cli/goose_cli.py:264-271`) + implement `close-readonly` stub | B | Only after 2.1 |
| 2.4 | Goose config via **documented manual step** for beta (secrets-bearing `merge` op is its own 8-gate promotion → post-beta; `copy` for skills = stretch) | A | |
| 2.5 | `FIRST_SESSION.md` + README First-run rewrite — **sequenced AFTER 1.7** (a quickstart describing the patch loop cannot pass `scan_docs_for_false_completion` until the rows flip) | A | Sequencing-critic fatal trap |
| 2.6 | **R1 closure audit + matrix flip**, incl. audited amendment of `validate_r1_config_onboarding_mapping` (currently hard-fails if any R1 row goes OPERATIONALLY_VERIFIED) + pinned-test updates (`interactive setup wizard == NOT_STARTED` at truth-test line 65, etc.) | C | Owns R1 pins |
| 2.7 | **Scripted clean-clone smoke run** — repeatable 30-minute-claim validation gate (includes no-Swift-toolchain case) | B | Only defense against onboarding regressions |

## Phase 3 — The Gift (preparation-only; NOTHING published — see authority boundary)

**Start any time (independent):**

| # | Item | Tier |
| --- | --- | --- |
| 3.1 | PII scrub of the 22 tracked files (kaizenpro paths, "Joshua Shay", hardcoded `/Users` paths in docs/fixtures) | A |
| 3.2 | Move `mlx-lm`/`rapid-mlx` to `[project.optional-dependencies]` (unblocks non-Mac `uv sync`); document Mac-first boundary in README | B |
| 3.3 | Remove `gh` from `install-tools.sh` required tier (contradicts repo's own Forgejo rule); pin goose installer by checksum | A |
| 3.4 | Docs funnel: `docs/README.md` index, 3-tier entry path (README → FIRST_SESSION → reference); fix OPERATOR_QUICKSTART founder paths | A |
| 3.5 | CONTRIBUTING/SECURITY/CODE_OF_CONDUCT/CHANGELOG **drafts** (license header slots left blank per D2) | A |

**At cut-over (only when operator initiates open-sourcing — D2/D3/D8):**

| # | Item | Tier |
| --- | --- | --- |
| 3.6 | License decision + pyproject field (operator's call) | — |
| 3.7 | Agent-instruction-file public edits (CLAUDE.md/AGENTS.md/.cursorrules reference the private host) | A |
| 3.8 | **Full-refs secret scan re-run at publication time** (a scan now goes stale as Phases 0–2 commit; 614 commits, 235 branches, 1 stash) | B |
| 3.9 | History strategy execution (fresh-start vs rewrite — operator's call, D3) | C |
| 3.10 | v0.1.0 tag bound to release-proof harness + CHANGELOG (after both flips 1.7 + 2.6) | B |

**Demo (after 1.8):**

| # | Item | Tier |
| --- | --- | --- |
| 3.11 | Canonical 15-minute flagship script with **live tamper-detection beat** (edit a receipt on camera → chain verification fails) | B |
| 3.12 | asciinema/VHS recordings (zero recorded assets exist); timestamp-pinning option for reproducible takes | A |
| 3.13 | STRATUM TUI: gate behind `--experimental` (D5 — committed; wiring post-beta) | B |

## Phase 4 — The Beta

| # | Item | Tier |
| --- | --- | --- |
| 4.1 | Beta charter (what feedback is wanted) | A |
| 4.2 | Known-limitations doc generated from truth matrix — **explicitly stating verification-lane target scope: Python-with-pytest repos only** | A |
| 4.3 | Issue intake + templates at the (eventual) public host; weekly triage cadence | A |

## Post-beta ladder (explicitly cut from beta; in order)

1. **CodeVault Tier-1 encoder + bench lane** (D4 — v0.2 flagship; doctrine-amendment RFC may be authored during beta as design-only; must re-scope what the determinism demo proves: center stability AND declared versor instability)
2. B2.0 machine-checkable promotion-gate evaluator (manual closure audits suffice for a twice-run process)
3. Ladder tail: structured test outcomes (pass/fail/skip + junit-xml + exact argv), ledger index chain (`ledger_index`/`previous_ledger_record_digest`)
4. Wizard framework extraction + wizard v2 (9 decisions) + profile/recipe/deepagents wizards
5. STRATUM TUI real wiring
6. Secrets-preserving `merge` apply operation (Goose config)
7. CodeVault receipt-consumption bridge (epistemic promotion via verification receipts)
8. Full Linux CI parity; container isolation for the verification lane

## Cross-cutting: shared-registry integration order

Five files are appended to by nearly every stream: `command_authority.py` (~3,800 lines),
`artifact_index_records.py`, `artifact_chain_verification.py`, `platform_completion_audit.py`, and
the pinned truth tests (`test_platform_completion_truth.py`, `test_docs_truth_enforcement.py`).

**Rule: one phase owns each pinned file at a time.**
- Phase 0 owns docs-truth pins only (no matrix flips).
- Phase 1 owns the count/assurance pins — twice (1.7, then 1.8).
- Phase 2 owns the R1 pins (2.6).
- Registry appends from concurrent streams land through short-lived serialized merges.
- Every stream adding a CLI must also extend operator-status coverage (`test_operator_status.py`
  asserts command-count parity with the registry).

## Risk register (top 5)

1. **Stranger-repo test execution is real code execution** — D7 is the most safety-significant open
   decision; it gates 1.2/1.3.
2. **Receipt schema bump mid-stream** invalidates approvals/fixtures if mis-sequenced — bump before
   fixtures, decide dual-version tolerance, plan for pre-bump ledger records.
3. **Pinned-truth-test lockstep** — any stream flipping matrix state without owning the pins breaks
   every other stream's green build.
4. **Onboarding regression** between now and beta — mitigated only by the 2.7 clean-clone gate.
5. **Publication hygiene is irreversible** — PII/secrets re-scan at cut-over (3.8), never trust a
   stale scan.

## Sizing (one operator + AI agents; HITL review is the serial bottleneck)

- Phase 0: ~1 week
- Phase 1: ~2–3 weeks (sandbox decision + unmocked test suite dominate)
- Phase 2: ~1–2 weeks
- Phase 3: ~1 week spread + cut-over items deferred with D2/D3
- **Minimum cut if the window compresses:** 0.1–0.3 + Phase 1 complete + 2.1–2.3, 2.5–2.7 +
  3.1/3.11/3.12. Still delivers all four exit criteria (with (c) pending the deferred
  license/publication decisions).

## Evidence appendix

Raw audit + critique outputs preserved at `scratch/core-par-planning/evidence/`:
`b4.json`, `r1.json`, `codevault.json`, `ladder.json`, `oss.json`, `quality.json`, `demo.json`
(7-domain audit, ~866k tokens of investigation), `critique-{doctrine,sequencing,scope}.json`
(adversarial panel verdicts: 3× sound_with_corrections — all corrections folded into this document),
`draft-plan-as-reviewed.md` (pre-critique draft for diffing).
