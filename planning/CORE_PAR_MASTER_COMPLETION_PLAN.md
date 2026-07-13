# builder-II → CORE Par: Master Completion Plan

**Version:** 1.2 (adversarially reviewed; external review folded; D7 ratified)
**Date:** 2026-07-07 (v1.1: folded Gemini 3.1 Pro external review + operator craft doctrine; v1.2 same day: operator authorized implementation via `/goal` and ratified D7)
**Status:** IMPLEMENTATION IN PROGRESS — Phase 1 critical path. Items **1.1 + 1.5 shipped** (Forgejo PR #1; weak-approval gap closed + mutation lane gated at every entrance). **D7 ratified** (pytest verification envelope). Next Tier-C: **1.2** (now unblocked), **2.1**. No matrix flips yet (that's 1.7).
**Location note:** This file lives in `planning/` (tracked, deliberately **outside** `docs/`). It
contains capability names combined with promotion-state language that would trip
`builder-platform audit-docs` / `scan_docs_for_false_completion` if placed under `docs/` — the scanner
only walks `README.md` + `docs/**` (`platform_completion_audit.py:_docs_to_scan`). When adopted, a
safe-phrasing summary can be derived for `docs/plan/` — do not move this file there verbatim.

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
| D7 | Sandbox model for pytest verification lane | **RATIFIED (operator, 2026-07-07).** Envelope: (1) env-allowlist subprocess, `shell=False`, fixed argv — bounds *invocation*, never *code behavior*; **never described as a sandbox** anywhere in code/docs/UI. (2) **Schema-enforced execution-risk acknowledgment:** target-code-executing profiles (`pytest_full`/`builder_full`) require the approval artifact to carry `execution_risk_acknowledged: true` + an `acknowledged_risk` string naming target-code execution (incl. transitive `conftest`/plugin code) on the host with operator privileges; the runner verifies it **before spawning** and refuses (fail closed) if absent. Non-target-code profiles (`platform_status`/`docs_audit`, builder-II's own fixed argv — verified `verification_execution_runner.py:69-84`) do **not** require the ack (no consent noise on safe profiles). (3) **Timeout policy:** the hardcoded 30 s is replaced by a required per-profile timeout in the approved plan, range-checked `[1, 1800]` s (no silent default masking a hang); on expiry the runner kills the subprocess and emits a FAILED/timeout receipt. (4) **Byproduct rule:** ignore-globs are pinned *inside* the fixed profile (never caller-supplied); paths matching them that changed during the run are recorded in postflight as observed byproducts (an ignore channel must not silently hide a write). (5) **Scope:** trusted local repositories only (FIRST_SESSION + beta charter + 4.2). Container/VM isolation is post-beta (ladder item 9). Tunable knobs the operator may still adjust: the timeout range/default and the exact `acknowledged_risk` wording. | 2026-07-07 |
| D8 | Public hosting destination | **DEFERRED** (with D2/D3) — but decide at **Phase 3 kickoff**, not cut-over: D8 shapes 3.4/3.5 content (host-specific contributor tooling, issue templates) and D3 shapes 3.8–3.10 | pending |
| D9 | Pre-`v0.1.0` schema bumps | **HARD CUT ("Ledger Genesis"):** no dual-version parsers. Validators are already strict single-version (`verification_execution_receipt.py:312-336` rejects any other `schema_version`); tolerance would be net-new machinery for zero external users. Bump constants, wipe local ledger/artifacts, regenerate fixtures + demo assets, note in CHANGELOG. After the `v0.1.0` tag, schema changes require an explicit versioning policy. | 2026-07-07 |
| D10 | Craft doctrine (operator's "Apple philosophy") | **ADOPTED** as a design standard for every operator-facing surface — see "Craft doctrine" section. Complex ≠ complicated; friction only at authority boundaries; native adapter power without lane collisions; minimal agent briefings. | 2026-07-07 |

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

## Craft doctrine (D10 — the operator's bar: "an extension of the engineer")

Governance correctness is necessary but not sufficient for CORE par. Every operator-facing surface is
also held to this standard. These are review criteria, not aspirations — 2.7 (clean-clone smoke) and
3.11 (demo script) are explicitly checked against them.

1. **Complex ≠ complicated.** One mental model everywhere: *artifact → validate → approve → execute →
   receipt*. Five verbs an operator can hold in their head; the depth (chains, ledgers, digests,
   promotion states) stays behind them until asked for. New surfaces reuse the existing verb-noun
   grammar — never invent a second vocabulary for the same concept.
2. **The tool points to the next move.** Every command ends by naming the obvious next command; every
   error names its cause *and the exact command that fixes it*. Zero dead ends on the golden path
   (acceptance: the 2.7 smoke transcript contains no "now what?" moment).
3. **Friction budget.** Interaction cost is spent *only* at authority boundaries — digest re-entry at
   approval, execution-risk acknowledgment for target-code execution — and aggressively removed
   everywhere else (sane defaults, auto-discovery, one-command `builder init`). A prompt that guards
   nothing is clutter; a boundary without a prompt is a hole. Corollary: confirmations must force
   attention (type the digest prefix), never train reflexes (`[y/N]` mashing).
4. **Progressive disclosure.** A stranger reaches a governed session in minutes; ledgers, chains, and
   profiles reveal on demand. Human-first rendering by default; `--json` everywhere for machines.
5. **Honest surfaces.** Nothing on screen is ever fake — no fabricated digests, no mock tier
   evaluations (D5). Demos show real failure beats (tamper detection) because governance *felt* is
   the product. Language stays precise: receipts are digest-chained evidence, not "cryptographic
   proof" — no signature claims we don't back.
6. **Native power through governed adapters — no lane collisions.** deepagents' native strengths
   (subagent delegation, planning graphs, work artifacts, forge) and Goose's native strengths
   (interactive sessions, recipes, extensions) are each exercised *fully*, each through its own
   adapter. builder-II never reimplements one runtime's features on the other. Lane ownership is
   policy recorded as artifacts — deepagents = planning/delegation lane, Goose = operator-interactive
   runtime lane, gateways = model/tool invocation — so a capability collision is resolved by policy,
   never by whichever adapter got invoked first. (Full orchestration promotion is post-beta ladder
   work; the doctrine binds all design *now*.)
7. **Agent dispatch economy.** Any dispatched agent — subagent, deepagent, workflow stage — is briefed
   with the *minimum necessary*: the task, its boundary, the expected artifact contract, and file
   *references* rather than file dumps. Context is a budget; an oversized briefing is both waste and
   an enlarged prompt-injection surface. (Operator standing instruction, 2026-07-07.)

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

**Dispatch economy (craft doctrine #7):** every delegated agent gets a *minimal* briefing — task,
boundary, expected output contract, and file paths to read, never pasted file contents. Spec sheets
for [A]/[B] items should fit in a page.

**Registry wiring protocol (external review B, adapted):** parallel agents deliver *isolated logic +
tests* plus a **registry wiring spec** (the exact rows/entries to add to `command_authority.py`,
artifact index, chain verification, operator-status coverage) — they do NOT edit the shared
registries themselves. Wiring specs land serially, one short-lived single-owner branch per merge
window, applied by the operator or one dedicated serial agent with operator diff review ([C]). This
kills registry merge conflicts *and* the subtler risk: a capability wired in a mega-conflict
resolution nobody actually reviewed.

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
| 1.1 | **B4.1 (first):** generic `builder_ii.hitl_patch_approval` artifact kind + `builder-hitl approve-patch` CLI with **interactive TTY prompt at the decision point** (diff + digest shown at the moment of approval). **Confirmation idiom (external review D): the operator types the first 4 characters of the patch digest — never `[y/N]`.** This is an *attention* control (forces eyes onto the identifier), not a security control — document it as such. No non-interactive approval mode exists by design (scripting the prompt would collapse `planned ≠ approved`); the demo gets its TTY moment, not a `--approve` flag. Includes: `expires_at` **enforced inside `apply_hitl_patch`** (no decorative fields); `CommandAuthorityRecord` registration; artifact-index + chain-verification registration; documented threat model (operator-only invocation; *artifacts are evidence, not authority*). Closes the weak-approval security gap — honestly: *narrows* it; the TTY moment is what makes it real | C | New CLI surfaces MUST be registered or `validate_command_surfaces` fails matrix validation |
| 1.2 | **Ladder slice** (true B4.2 prerequisite set — ladder items 1, 2, 3, 8): (a) pytest profile naming-invariant fix; (b) commit identity (HEAD SHA/branch) in git state + **receipt schema bump sequenced BEFORE any B4 fixtures/evidence are authored** — **hard cut per D9** (bump the strict-equality constants, wipe local ledger/artifacts, regenerate fixtures; no dual-version parsers); (c) bounded `pytest_full` promotion — **D7 RATIFIED 2026-07-07, so this is now unblocked**; implement the ratified envelope exactly: the schema-enforced execution-risk acknowledgment (required `execution_risk_acknowledged`/`acknowledged_risk` on the approval for target-code-executing profiles, runner verifies before spawning and refuses if absent; approve-time prompt states plainly "this executes the target repository's code (pytest imports `conftest.py` and test modules) on your host with your user privileges"), the timeout policy (required per-profile timeout range-checked `[1, 1800]` s replacing the hardcoded 30 s; kill + FAILED/timeout receipt on expiry), and pytest-byproduct ignore-globs **pinned inside the fixed profile with observed byproducts recorded in postflight** (an ignore channel is where a malicious patch hides writes); (d) `builder_full` extension in **both** the plan validator AND the runner's hardcoded `expected_ref` (line ~141) | C | The bounded runner bounds *what gets invoked*, never *what invoked code can do* — pytest over a repo executes that repo's code (and its dependencies' plugins/conftest) with user authority. Not a sandbox; never describe it as one. D7 ratified 2026-07-07 (see decision log) — envelope is fixed, implement faithfully |
| 1.3 | **B4.2:** generic pre/post-apply verification receipt lane for arbitrary target repos | C | Depends on 1.2 complete |
| 1.4 | **B4.3:** distinct rollback human approval + rollback failure receipt. **Drift hardening (external review 3): `git apply -R` is brittle if the tree was touched between apply and rollback** — rollback preflight re-fingerprints the tree against the post-apply receipt; on mismatch it refuses, emits a rollback-failure receipt carrying a **recovery block** (the `pre_apply` HEAD SHA captured at apply time via 1.2b, the exact operator commands — e.g. `git reset --hard <pre_apply_sha>` with its data-loss warning — and a chain-invalidation event). Failure must instruct, never strand | B | Today the machine-generated rollback plan path doubles as the "approval" |
| 1.5 | **Route apply/rollback through the command-authority gate at execution time** — `apply_hitl_patch` never consults the gate; flipping the matrix without this promotes a write lane that bypasses the gate the matrix cites as promoted | C | Critic-found omission |
| 1.6 | **B4.5 + B4.6:** unmocked E2E tests (real schema-valid approval + verification artifacts — current tests monkeypatch `VALIDATORS` and mock receipt validation) + CLI-level denial tests + ledger event emission for apply/rollback (zero ledger integration today) | B | |
| 1.7 | **B4.7 → B4.8:** receipts-backed live closure audit (`docs/audits/B4_CLOSURE_AUDIT.md`) → then ONE atomic flip commit: matrix rows, `operationally_verified_count` 15→17, both BLOCKED_BY_EVIDENCE asserts, `operationally_incomplete` flag, `render_human_summary` strings, `CAPABILITY_PROMOTION.md` §6/7, `RUNTIME_PROMOTION.md` non-promotion statement. Evidence first, flip second — never the reverse. **Flip assistant (external review C, adapted): a small `scripts/` helper that reads the closure audit, computes the FULL edit set across every pinned site, and emits it as a reviewable diff + consistency check. It never auto-applies — an auto-writer for truth pins would itself be a truth-inflation vector. The operator reviews and applies; the flip stays [C]. Kills the miss-one-string CI-failure loop while keeping evidence-before-flip human** | C | Owns the pinned truth tests for this phase; assistant is reused at 1.8 and 2.6 |
| 1.8 | **B4.9:** generalize demo loop to generic targets (parameterize marker patch + CORE sensitive-path checks; generalize worktree prep beyond `_ensure_core_repo`; replace `core_demo_approval` with the 1.1 generic kind) + **second pin edit** (CORE demo loop matrix row; decide whether the `core_demo_verification_receipt` fallback in `_verification_receipt_errors` survives) | B/C | Feeds Phase 3 demo |

## Phase 2 — The Door (R1 minimum onboarding)

| # | Item | Tier | Notes |
| --- | --- | --- | --- |
| 2.1 | **Doctrinal prerequisite:** reconcile `builder-goose start-readonly` promotion state BEFORE touching it. `CAPABILITY_PROMOTION.md` §7 pins Tier 4 forbidden citing `tests/test_goose_cli.py` **which does not exist**; registry says Tier 3; code launches Goose. Run the `RUNTIME_PROMOTION.md` read-only checklist (denied-action tests, no-mutation postflight, interruption recovery) and write real launch/close tests | C | Critique panel's one fatal doctrine flaw |
| 2.2 | **`builder init` unified orchestrator** over the **existing** 4-decision wizard + registry-validated answers + documented defaults for the remaining ~5 decisions. Init emits plan artifact + digest and requires **digest re-entry or a separately invoked apply step** — the process that renders a digest must not also harvest the confirmation. **Uses the SAME digest-prefix-typing idiom as 1.1** — one confirmation grammar across the whole platform (craft doctrine #1/#3; external review D: `[y/N]` trains reflex-mashing and collapses `planned ≠ executed`). `CommandAuthorityRecord` + operator-status coverage included | C | Wizard-framework extraction + 9-decision wizard v2 = post-beta (infrastructure-before-need) |
| 2.3 | MockPlan removal (`cli/goose_cli.py:264-271`) + implement `close-readonly` stub | B | Only after 2.1 |
| 2.4 | Goose config via **documented manual step** for beta (secrets-bearing `merge` op is its own 8-gate promotion → post-beta; `copy` for skills = stretch) | A | |
| 2.5 | `FIRST_SESSION.md` + README First-run rewrite — **sequenced AFTER 1.7** (a quickstart describing the patch loop cannot pass `scan_docs_for_false_completion` until the rows flip) | A | Sequencing-critic fatal trap |
| 2.6 | **R1 closure audit + matrix flip**, incl. audited amendment of `validate_r1_config_onboarding_mapping` (currently hard-fails if any R1 row goes OPERATIONALLY_VERIFIED) + pinned-test updates (`interactive setup wizard == NOT_STARTED` at truth-test line 65, etc.) | C | Owns R1 pins |
| 2.7 | **Scripted clean-clone smoke run** — repeatable 30-minute-claim validation gate (includes no-Swift-toolchain case) | B | Only defense against onboarding regressions |

## Phase 3 — The Gift (preparation-only; NOTHING published — see authority boundary)

**Start any time (independent):**

| # | Item | Tier |
| --- | --- | --- |
| 3.1 | PII scrub of the 22 tracked files (<developer_name> paths, "<developer_name>", hardcoded `/Users` paths in docs/fixtures) | A |
| 3.2 | Move `mlx-lm`/`rapid-mlx` to `[project.optional-dependencies]` (unblocks non-Mac `uv sync`); document Mac-first boundary in README | B |
| 3.3 | Remove `gh` from `install-tools.sh` required tier (contradicts repo's own Forgejo rule); pin goose installer by checksum | A |
| 3.4 | Docs funnel: `docs/README.md` index, 3-tier entry path (README → FIRST_SESSION → reference); fix OPERATOR_QUICKSTART founder paths | A |
| 3.5 | CONTRIBUTING/SECURITY/CODE_OF_CONDUCT/CHANGELOG **drafts** — **host-neutral** (license header slots blank per D2; hosting/tooling sections templated per D8: a public-GitHub home means contributor docs speak `gh`/GitHub-PR grammar while internal agent files stay `tea`-only — those two audiences must not share one document). Host-specific finalization happens at cut-over with 3.7 | A |

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
| 4.2 | Known-limitations doc generated from truth matrix — **explicitly stating verification-lane target scope: trusted local Python-with-pytest repos only** (D7 language: the runner bounds invocation, not code behavior; container isolation is post-beta) | A |
| 4.3 | Issue intake + templates at the (eventual) public host; weekly triage cadence | A |

## Post-beta ladder (explicitly cut from beta; in order)

1. **CodeVault Tier-1 encoder + bench lane** (D4 — v0.2 flagship; doctrine-amendment RFC may be authored during beta as design-only; must re-scope what the determinism demo proves: center stability AND declared versor instability)
2. B2.0 machine-checkable promotion-gate evaluator (manual closure audits suffice for a twice-run process)
3. Ladder tail: structured test outcomes (pass/fail/skip + junit-xml + exact argv), ledger index chain (`ledger_index`/`previous_ledger_record_digest`)
4. **Governed orchestration promotion (the builder vision, craft doctrine #6/#7):** promote the deepagents delegation lane — native deepagents subagent/planning capability exercised through the bridge under an explicit **lane-policy artifact** (deepagents = planning/delegation, Goose = interactive runtime, gateways = model/tool calls; collisions resolved by policy, validated like any artifact) + **minimal-briefing dispatch contracts** (a dispatched subagent receives task/boundary/output-contract/file-refs — a schema, so dispatch economy is checkable, not aspirational). Rides on B2.0 evidence machinery; same 8-gate promotion as everything else
5. Wizard framework extraction + wizard v2 (9 decisions) + profile/recipe/deepagents wizards
6. STRATUM TUI real wiring
7. Secrets-preserving `merge` apply operation (Goose config)
8. CodeVault receipt-consumption bridge (epistemic promotion via verification receipts)
9. Full Linux CI parity; container isolation for the verification lane

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

## Risk register (top 6)

1. **Target-repo test execution is real code execution** — **D7 RATIFIED 2026-07-07** (envelope in
   the decision log); it gated 1.2/1.3, now unblocked. The bounded runner constrains *invocation*,
   never *code behavior*; beta scope = trusted local repos only, and the realistic beta-window threat
   is transitive (a dependency's `conftest`/plugin), which the schema-enforced risk-ack names
   explicitly. Residual risk is accepted for the trusted-local-repo beta; container isolation
   (ladder item 9) is the post-beta mitigation.
2. **Receipt schema bump mid-stream** invalidates approvals/fixtures if mis-sequenced — bump before
   fixtures, hard cut per D9 (no dual-version parsers; wipe local ledger, regenerate fixtures).
3. **Pinned-truth-test lockstep** — any stream flipping matrix state without owning the pins breaks
   every other stream's green build. Mitigated by the 1.7 flip assistant (generate + review, never
   auto-apply) and the registry wiring protocol (specs land serially).
4. **Working-tree drift between apply and rollback** — `git apply -R` fails if the operator, an IDE,
   or a background agent touched the tree. Mitigated by 1.4 preflight fingerprint check + recovery
   block in the rollback-failure receipt.
5. **Onboarding regression** between now and beta — mitigated only by the 2.7 clean-clone gate.
6. **Publication hygiene is irreversible** — PII/secrets re-scan at cut-over (3.8), never trust a
   stale scan.

## Sizing (one operator + AI agents; HITL review is the serial bottleneck)

- Phase 0: ~1 week
- Phase 1: ~2–3 weeks (sandbox decision + unmocked test suite dominate)
- Phase 2: ~1–2 weeks
- Phase 3: ~1 week spread + cut-over items deferred with D2/D3
- **Minimum cut if the window compresses:** 0.1–0.3 + Phase 1 complete + 2.1–2.3, 2.5–2.7 +
  3.1/3.11/3.12. Still delivers all four exit criteria (with (c) pending the deferred
  license/publication decisions).

## External review disposition (Gemini 3.1 Pro Deep Think, 2026-07-07 — v1.1 fold)

Full review text: `evidence/external-review-gemini-3-1-pro.md`. Every finding dispositioned; two were
adapted rather than adopted because following them literally would violate our own governance.

| Finding | Verdict | Action |
| --- | --- | --- |
| A. ACE elephant (`pytest_full` = arbitrary code execution; "not a sandbox") | **Adopted** — aligns with and sharpens D7 | D7 strengthened: schema-enforced risk-ack field, scoped to target-code-executing profiles only (the two live profiles run builder-II's own argv — verified); runner refuses un-acked approvals; "trusted local repos only" pinned in FIRST_SESSION/charter/4.2; 1.2 notes column now states the bound honestly |
| B. Registry merge-conflict trap (parallel agents on `command_authority.py`) | **Adopted, adapted** — full human-manual wiring wastes the delegation model | Registry wiring protocol added to delegation guide: agents deliver logic + a *wiring spec*; specs land serially in single-owner merge windows with operator diff review ([C]). Pin-ownership rule kept |
| C. `bump_matrix.py` auto-updater for flips | **Adapted (doctrine guard)** — an auto-*writer* for truth pins is a truth-inflation vector | 1.7 flip assistant: *generates* the full edit set from the closure audit + consistency-checks it; never auto-applies; operator reviews/applies. Reused at 1.8/2.6 |
| D. Consent fatigue; digest-prefix typing instead of `[y/N]` | **Adopted** — also serves craft doctrine #3 | 1.1 + 2.2 share one confirmation idiom: type the first 4 digest chars; documented as attention control, not security control; no non-interactive approval mode by design |
| S1. Force D3 (fresh-start) now | **Rejected as timed; content endorsed** — D3 is operator-only, explicitly DEFERRED (2026-07-07 ruling) | Fresh-start remains the standing recommendation-on-file. D8 row amended: decide D3/D8 at *Phase 3 kickoff* rather than cut-over, since they shape 3.4–3.10 |
| S2. Drop dual-version tolerance; "Ledger Genesis" hard cut | **Adopted → D9** — validators are already strict single-version (verified `verification_execution_receipt.py:312-336`); tolerance would be net-new machinery for zero external users | 1.2b rewritten; risk #2 rewritten; post-`v0.1.0` schema changes require explicit policy |
| S3. Rollback brittleness (`git apply -R` vs tree drift) | **Adopted** | 1.4 amended: preflight fingerprint check, recovery block (pre-apply HEAD SHA + exact commands) in the rollback-failure receipt, chain-invalidation event; risk #4 added |
| S4. Decide D8 before authoring community files | **Adopted, adapted** — decision stays deferred, authoring de-risked instead | 3.5 drafts are host-neutral with templated hosting sections; host-specific finalization at cut-over with 3.7; contributor docs vs internal agent rules explicitly split (public host may be `gh`-grammar while internal stays `tea`-only) |

Also noted: the review says "cryptographic evidence" — our receipts are digest-chained integrity
artifacts, not signatures. Craft doctrine #5 pins the honest phrasing so our own language never
over-claims.

## Evidence appendix

Raw audit + critique outputs preserved at `planning/evidence/` (tracked; originals also at
`scratch/core-par-planning/evidence/`):
`b4.json`, `r1.json`, `codevault.json`, `ladder.json`, `oss.json`, `quality.json`, `demo.json`
(7-domain audit, ~866k tokens of investigation), `critique-{doctrine,sequencing,scope}.json`
(adversarial panel verdicts: 3× sound_with_corrections — all corrections folded into this document),
`draft-plan-as-reviewed.md` (pre-critique draft for diffing),
`external-review-gemini-3-1-pro.md` (external review folded into v1.1).
