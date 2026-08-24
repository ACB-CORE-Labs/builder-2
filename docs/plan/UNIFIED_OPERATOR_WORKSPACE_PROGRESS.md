# Unified operator workspace progress ledger

This is the living execution companion to
`UNIFIED_OPERATOR_WORKSPACE_COMPLETION_PLAN.md`.

It records observed and executed work. It is not approval, a receipt, capability
promotion, merge authority, release authority, or self-hosting admission.

Last updated: 2026-08-24

## Custody and current implementation context

| Field | Current value |
| --- | --- |
| Canonical repository | `https://github.com/ACB-CORE-Labs/builder-2` |
| Predecessor review | PR #21 remains open and mergeable; no merge was performed by this program |
| Stacked base | `53f968e357f4efaf2aeba7df5a04c48e65551a7c` (exact reviewed PR #22 head; PR #22 is itself stacked on PR #21) |
| Implementation branch | `feat/unified-operator-ps1` |
| Worktree | `.builder/dev-worktrees/unified-operator-ps1` |
| Delivery state | Plan Set 0 is under review in stacked PR #22; Plan Set 1 lifecycle convergence is active on this exact PR-head child branch; no merge, tag, release, promotion, or self-hosting admission |

The branch is intentionally stacked on PR #22, which remains stacked on PR #21,
so the successor work includes both reviewed foundations without altering or
merging either review. Before delivery, hosted state and the eventual base
strategy must be read back and reconciled.

## Program dashboard

| Plan set | State | Current result | Next required proof |
| --- | --- | --- | --- |
| 0 - authority/adoption baseline | `LOCAL_CI_VERIFIED` | successor plan, interaction contract, Goose adoption matrix, and this ledger added | independent review and stacked-base delivery decision |
| 1 - run registry and RunView | `IN_PROGRESS` | core registry, deterministic selection, RunView, and run-oriented status are focused-verified; cross-runtime lifecycle convergence remains | lifecycle state contract and complete/fail/interrupt/resume/cancel/orphan/close fixtures |
| 2 - Lens/Inspect/visual validation | `NOT_STARTED` | no implementation claim | Plan Set 1 stable core contract |
| 3 - governed actions | `NOT_STARTED` | existing five-command seam remains the starting point | Plan Set 1 RunView plus current authority registry |
| 4 - Goose lifecycle/context | `NOT_STARTED` | existing governed launch remains current | Goose compatibility qualification and run binding |
| 5 - Deep Agents delegation | `NOT_STARTED` | existing bounded native lane remains current | `delegation_start` contract and read-only role qualification |
| 6 - model quality/routing | `NOT_STARTED` | existing runtime benchmark remains current | preregistered quality corpus and methodology |
| 7 - terminal workspace | `NOT_STARTED` | no Zellij/plain backend exists | Lens and Goose lifecycle stable |
| 8 - patch/recovery/delivery loop | `NOT_STARTED` | specialist canonical services remain current | contextual action and workspace integration |
| 9 - cutover/closure | `NOT_STARTED` | current `builder start` remains unchanged | Plan Sets 0-8 golden-path evidence |

`IMPLEMENTED_ON_BRANCH` above does not mean focused or local-CI verification. The
dashboard advances only when the verification log below contains the exact gate.

## Work-item ledger

| ID | Plan set | State | Intended result | Current evidence or gap |
| --- | --- | --- | --- | --- |
| UOW-000 | 0 | `FOCUSED_VERIFIED` | canonical successor plan distinct from v1 history | plan document exists; docs truth audit and docs tests pass |
| UOW-001 | 0 | `FOCUSED_VERIFIED` | fixed five-command normal-user grammar | interaction contract exists and docs gates pass; no CLI cutover |
| UOW-002 | 0 | `FOCUSED_VERIFIED` | explicit Goose adopt/project/qualify/defer/forbid matrix | matrix exists and docs gates pass; runtime `1.47.0` remains unqualified |
| UOW-003 | 0 | `FOCUSED_VERIFIED` | living progress/discovery/decision ledger | this document records the first focused gate set |
| UOW-100 | 1 | `FOCUSED_VERIFIED` | core owns validator-backed `RunView` | `builder_ii/core/run_view.py` exists; lifecycle verdict logic moved intact; focused tests pass |
| UOW-101 | 1 | `FOCUSED_VERIFIED` | one-release TUI import compatibility | compatibility facade exports old names without projection logic; focused tests pass |
| UOW-102 | 1 | `FOCUSED_VERIFIED` | calm read-only aliases for goal/stage/activity/attention/recovery | core properties and focused tests added |
| UOW-103 | 1 | `IN_PROGRESS` | durable run registry and deterministic selection | core registry now projects canonical session ledgers, exposes corrupt-only sessions, and selects exact/latest without fallback; subsystem lifecycle artifacts remain distributed |
| UOW-104 | 1 | `FOCUSED_VERIFIED` | run-oriented `builder status`; environment health moves to doctor | human and JSON status plus change-only watch are implemented; doctor retains environment probes; authority/docs tests pass |
| UOW-105 | 1 | `IN_PROGRESS` | shared lifecycle truth for complete/fail/interrupt/resume/cancel/corrupt/orphan/close | first bounded unit migrates governed Goose start/close custody into `sessions/<run>/{goose,events}` with validator-backed, digest-bound events; remaining terminal states and runtime families stay open |
| UOW-106 | 1 | `FOCUSED_VERIFIED` | canonical governed Goose start/close evidence and events | five rejected exact tips and their lesions are retained below; cumulative correctness review passed at `813aced3c3f665d066fed3e022773ce0c374381e`; full exact-tip local CI remains required and UOW-105 lifecycle convergence remains open |

## Verification log

| Date | Scope | Command | Result | Meaning |
| --- | --- | --- | --- | --- |
| 2026-08-24 | RunView ownership and STRATUM compatibility | `uv run pytest -q tests/test_run_view.py tests/test_plan_set4_correction.py tests/test_stratum_tui.py` | PASS | focused implementation selection passed; not full CI or promotion |
| 2026-08-24 | RunView, STRATUM, and docs truth | `uv run pytest -q tests/test_run_view.py tests/test_plan_set4_correction.py tests/test_stratum_tui.py tests/test_docs_truth_enforcement.py` | PASS | 57 focused tests passed; not full CI or promotion |
| 2026-08-24 | documentation truth | `uv run builder-platform audit-docs` | PASS | report was valid with zero violations; no capability state changed |
| 2026-08-24 | platform truth matrix render | `uv run builder-platform matrix` | PASS | matrix rendered successfully and still reports the platform operationally incomplete |
| 2026-08-24 | patch whitespace and conflict markers | `git diff --check` | PASS | tracked diff is mechanically clean; not a semantic review or full CI |
| 2026-08-24 | run registry/status plus authority and source-owned docs mirrors | `uv run pytest -q tests/test_run_view.py tests/test_run_status.py tests/scenarios/test_run_cockpit.py tests/test_stratum_tui.py tests/test_command_authority.py tests/test_known_limitations.py tests/test_platform_completion_truth.py tests/test_docs_truth_enforcement.py` | PASS | 127 focused and load-bearing tests passed; not full CI or promotion |
| 2026-08-24 | changed Python static checks | `uv run ruff check builder_ii/core/run_view.py builder_ii/core/run_registry.py builder_ii/core/run_status.py builder_ii/cli/main.py builder_ii/tui/projections/run_projection.py builder_ii/tui/projections/runs.py builder_ii/tui/widgets/stratum.py tests/test_run_view.py tests/test_run_status.py` | PASS | changed Python selection is lint-clean; not full CI |
| 2026-08-24 | root status smoke | `uv run builder status --json` | PASS | default config resolved the admitted artifact root and honestly reported no run; no artifact was created |
| 2026-08-24 | first committed-tip local CI attempt | `bash scripts/ci.sh --receipt .builder/dev-evidence/unified-operator-ps0/gate-battery-a9e8530.json` | FAIL | gates through Bandit passed; Deep Agents readiness failed because the fresh isolated environment lacked the declared extra; failed receipt retained |
| 2026-08-24 | CI environment remediation | `uv sync --all-groups --extra deepagents` | PASS | installed the lockfile-declared `deepagents==0.6.12` environment only; no source or lockfile change |
| 2026-08-24 | committed-tip local CI rerun | `bash scripts/ci.sh --receipt .builder/dev-evidence/unified-operator-ps0/gate-battery-a9e8530-rerun.json` | PASS | all blocking gates passed with no skips; full suite reported 3016 passed, 1 skipped, 4 warnings; receipt binds `a9e85303eef108ea9024b765c8c6b6185ea246b9` |
| 2026-08-24 | committed-tip receipt validation | `uv run python -m builder_ii.governance.ledger.gate_battery_receipt --validate .builder/dev-evidence/unified-operator-ps0/gate-battery-a9e8530-rerun.json` | PASS | receipt schema/digest/cross-field validation passed; receipt remains recorded-only and non-independent |
| 2026-08-24 | closure-review repairs | `uv run pytest -q tests/test_run_status.py tests/test_run_view.py tests/scenarios/test_run_cockpit.py tests/test_stratum_tui.py` | PASS | 42 tests passed, including deterministic watch suppression/interruption and corrupt-WAL-with-valid-mirror lesions; supersedes the focused UOW-104 gap |
| 2026-08-24 | canonical Goose lifecycle custody | `uv run pytest -q tests/test_goose_session_custody.py tests/test_goose_runtime_harness.py tests/test_goose_primary_cli.py tests/test_goose_plan_set_3b1_identity.py tests/test_governed_recipe.py tests/test_run_view.py tests/test_run_status.py tests/test_artifact_chain_verification.py tests/test_runtime_event_ledger_spine.py` | PASS | 67 focused tests passed; new launch/close chain, transcript-drift refusal, orphan-close detection, and existing Goose/RunView paths are green; not full CI or lifecycle convergence |
| 2026-08-24 | canonical Goose lifecycle static checks | `uv run ruff check builder_ii/adapters/goose/goose_receipts.py builder_ii/adapters/goose/goose_session_custody.py builder_ii/adapters/goose/goose_runtime_harness.py builder_ii/governance/ledger/event_ledger.py builder_ii/core/artifact_chain_verification.py builder_ii/core/run_view.py tests/test_goose_session_custody.py` | PASS | changed Python selection is lint-clean; not full CI |
| 2026-08-24 | Plan Set 1 lifecycle documentation truth | `uv run builder-platform audit-docs`; `uv run builder-platform matrix`; `uv run pytest -q tests/test_docs_truth_enforcement.py tests/test_platform_completion_truth.py tests/test_known_limitations.py tests/test_command_authority.py` | PASS | docs audit reported zero violations, the matrix remained operationally incomplete, and 87 truth/authority tests passed; no capability state changed |
| 2026-08-24 | first independent lifecycle custody audit | read-only adversarial review of exact commit `ae35e46fe29cf34914ec50e9bdc8dda531fcd66a` | BLOCK | reproduced namespace symlink escape, incomplete RunView cross-binding reconstruction, unaccounted-mutation acceptance, concurrent event loss, and incomplete export-failure recovery; exact tip rejected before full CI |
| 2026-08-24 | independent-audit repair battery | `uv run pytest -q tests/test_goose_session_custody.py tests/test_runtime_event_ledger_spine.py tests/test_model_ledger_chain.py tests/test_tool_ledger_chain.py tests/test_goose_runtime_harness.py tests/test_governed_recipe.py tests/test_goose_primary_cli.py tests/test_goose_plan_set_3b1_identity.py tests/test_run_view.py tests/test_run_status.py tests/test_artifact_chain_verification.py tests/test_mcp_plan_set_3b1_hardening.py` | PASS | 101 tests passed, including symlink escape, full reconstruction, mutation partition, same/different-type concurrent append, protected export cleanup/retry, and affected existing lanes; independent re-audit remains required |
| 2026-08-24 | second independent lifecycle custody audit | read-only adversarial review of exact commit `2bf68f971636ce9501f400f9fc1be3fe76ff68a2` | BLOCK | reproduced dangling-WAL symlink traversal, divergent WAL/JSON truth, transcript pathname replacement exposure, and opaque approved-mutation evidence; exact tip rejected before full CI |
| 2026-08-24 | second-audit targeted repair smoke | `uv run pytest -q tests/test_goose_session_custody.py tests/test_governed_recipe.py tests/test_run_view.py tests/test_runtime_event_ledger_spine.py tests/test_goose_session.py` | PASS | 35 tests passed after making JSON events sole authority, retaining WAL only as a reconciled legacy mirror, carrying transcript file/directory descriptors through export, and requiring typed approved evidence; broader focused verification and independent re-audit remain required |
| 2026-08-24 | second-audit broader repair battery | `uv run pytest -q tests/test_goose_session_custody.py tests/test_runtime_event_ledger_spine.py tests/test_model_ledger_chain.py tests/test_tool_ledger_chain.py tests/test_goose_runtime_harness.py tests/test_governed_recipe.py tests/test_goose_primary_cli.py tests/test_goose_plan_set_3b1_identity.py tests/test_run_view.py tests/test_run_status.py tests/test_artifact_chain_verification.py tests/test_mcp_plan_set_3b1_hardening.py` | PASS | 105 tests passed across canonical custody, model/tool event chains, Goose launch/close, RunView/status, artifact-chain verification, and MCP hardening; changed-code lint plus docs truth/matrix and 87 truth/authority tests also passed; new committed-tip audit remains required |
| 2026-08-24 | third independent lifecycle custody audit | read-only correctness review of exact commit `13dbb44e1a9176c8d9c69e1201ac5642a70d3742` | BLOCK | reproduced replacement of the transcript temporary directory entry after fd admission and acceptance of digest-correct foreign files as approved mutation evidence; exact tip rejected before full CI |
| 2026-08-24 | third-audit targeted repair smoke | `uv run pytest -q tests/test_goose_session_custody.py tests/test_governed_recipe.py tests/test_goose_runtime_harness.py` | PASS | 43 tests passed after binding the transcript name to the retained inode and repeating the runtime's full approved patch/rollback reconstruction at close persistence and later custody validation; independent exact-tip review remains required |
| 2026-08-24 | fourth independent lifecycle custody audit | read-only correctness review of exact commit `3b0194c9518dd6ec5c1be1b80398846d506528c3` | BLOCK | confirmed foreign approved evidence is refused but reproduced a swap at the link boundary, malformed JSON escaping reconstruction as `AttributeError`, and a legacy rollback-close fixture missing new custody attributes; exact tip rejected before full CI |
| 2026-08-24 | fourth-audit targeted repair smoke | `uv run pytest -q tests/test_goose_session_custody.py tests/test_governed_recipe.py tests/test_goose_runtime_harness.py tests/test_mcp_plan_set_3c3_rollback.py` | PASS | 54 tests passed after post-link destination inode verification/removal, total fail-closed reconstruction, and compatibility-safe access to optional canonical-close attributes; exact-tip review remains required |
| 2026-08-24 | fifth independent lifecycle custody audit | read-only correctness review of exact commit `fe17f065628b30d945707697987735d7ee6dbcf8` | BLOCK | confirmed the prior three blockers closed, then reproduced replacement of the canonical transcript name after its fd was opened but before acceptance; exact tip rejected before full CI |
| 2026-08-24 | sixth independent lifecycle custody audit | read-only cumulative review of exact commit `813aced3c3f665d066fed3e022773ce0c374381e` from base `53f968e357f4efaf2aeba7df5a04c48e65551a7c` | PASS | no remaining correctness blocker found; prior transcript, WAL, reconstruction, mutation, concurrency, malformed-evidence, and rollback lesions were rerun; changed-code lint, docs truth, matrix rendering, and the cumulative focused selection passed; full exact-tip local CI remains separate |

The two `a9e8530` receipt rows above describe the pre-ledger-update commit. Updating
this ledger creates a new tip, so those receipts are not final delivery evidence.
The new exact tip must receive its own full local CI receipt before push or PR.

`bash scripts/ci.sh --receipt <project-local-path>` remains required on the
settled committed tip before push or PR creation.

## Decision log

| ID | Decision | Reason | Revisit condition |
| --- | --- | --- | --- |
| D-001 | Preserve the v1 plan as historical and create a successor plan | avoids rewriting completed evidence and authority history | never rewrite history; supersede this plan only explicitly |
| D-002 | Use exactly five normal-user commands | users learn interaction grammar, not the command graph | usability evidence shows a required normal action cannot be contextual |
| D-003 | Cut over `builder start` only after the integrated golden path | prevents a partial daily path becoming the default | all Plan Sets 0-8 exit gates pass |
| D-004 | Use optional Zellij plus plain fallback | seamless enhanced workspace without mandatory infrastructure | Lens dogfood disproves the need or Zellij qualification fails |
| D-005 | Keep self-hosting as a separate admission | builder-II currently does not govern its own development | independent end-to-end evidence and explicit ratification exist |
| D-006 | Local models are default; cloud is approved fallback | preserves M1/local-first policy without hiding useful escalation | empirical role qualification supports a revised policy proposal |
| D-007 | Move existing projection logic; do not invent another RunView interpreter | validators and lifecycle semantics already exist | never, unless the owning artifact contracts themselves change |
| D-008 | Canonical lifecycle evidence is persisted before its event is appended | an event cannot truthfully bind an in-memory receipt or a not-yet-exported transcript | revisit only if the event store gains an atomic multi-artifact transaction with equivalent custody |
| D-009 | Keep receipt mirrors for one compatibility interval, but derive run truth only from the admitted session namespace | avoids a flag-day CLI break without allowing target-local mirrors to compete with canonical evidence | remove mirrors after every supported consumer reads canonical refs |

## Implementation discoveries

These are observations, not automatically authorized scope changes.

| ID | Observation | Consequence for the plan | Disposition |
| --- | --- | --- | --- |
| F-001 | STRATUM already has a closed typed five-command invocation seam | generalized governed actions should extend it, not introduce the first executor | incorporated into Plan Set 3 |
| F-002 | The existing run projection already validates canonical evidence and derives next state | extraction is higher leverage and lower risk than greenfield RunView design | implemented on branch |
| F-003 | `builder start` already launches governed Goose but requires five prebuilt WRP route artifacts | the product launcher should generate/validate those artifacts internally, not discard them | incorporated into Plan Set 7 |
| F-004 | `builder status` currently reports backend/Goose/model environment health | run status needs the name; environment status belongs in `builder doctor` | incorporated into Plan Set 1 |
| F-005 | Resume is explicitly refused by the current primary launcher | seamless resume requires real run/session custody, not a UI alias | incorporated into Plan Set 4/7 |
| F-006 | Installed Goose is `1.47.0`, outside the admitted `<1.47.0` range | no local governed launch may cite 1.47 compatibility until recollected evidence passes | Plan Set 0 compatibility work remains open |
| F-007 | Native Deep Agents currently admits only task/echo/HITL tool classes | mechanism proof is real, but engineering-role mastery requires read-only governed tools | incorporated into Plan Set 5 |
| F-008 | Current Textual tests include Pilot coverage and a PTY boot lane, but no visual verdict | add semantic fixed-size captures and supervised image review without making pixels governance evidence | incorporated into Plan Set 2 |
| F-009 | The canonical event loader intentionally skips malformed/foreign event files | the core registry must inventory the event directory separately or corrupt-only sessions disappear | implemented: registry entries carry inventory errors and fail closed |
| F-010 | Goose close wrote a sequence-zero `goose_session_closed` event outside `sessions/<run>/events`, using an event type/ref shape the canonical ledger validator did not admit | migrate new close custody into the shared run namespace without reinterpreting old bytes | implemented in UOW-106; legacy files remain non-canonical rather than being wrapped into false validity |
| F-011 | The canonical event loader falls back from an unreadable WAL to JSON mirrors | a corrupt WAL could disappear from status even when the mirror remained readable | implemented: registry performs an independent strict WAL inventory and fails closed |
| F-012 | Goose close emitted before its caller persisted close/postflight artifacts | the harness could not bind the exact evidence it claimed to close; lifecycle custody must own persistence and append ordering | implemented in UOW-106 |
| F-013 | Goose close/postflight artifacts had constructors but no owning validators | RunView could not distinguish intact close evidence from plausible JSON by kind alone | implemented in UOW-106 with paired validators and lesions |
| F-014 | Path concatenation plus ordinary `mkdir`/`write_text` allowed symlinked session components to redirect custody | custody must validate its own session id and use component-wise no-follow directory admission plus exclusive file creation | repair implemented locally; independent re-audit pending |
| F-015 | Per-artifact event checks did not reconstruct close-to-launch/postflight/transcript bindings | one reusable reconstruction validator must serve persistence and RunView | repair implemented locally; independent re-audit pending |
| F-016 | Postflight `valid` only tracked the caller-supplied unexplained list | validators must prove an exact disjoint partition of detected mutations and mode/evidence consistency | repair implemented locally; independent re-audit pending |
| F-017 | Runtime events allocated sequence and filename outside a lock | lock allocation, prior-chain validation, and exclusive canonical JSON creation as one serialized operation | repair implemented locally with deterministic same/different-type concurrency lesions; independent re-audit pending |
| F-018 | A dangling `events.wal` symlink bypassed an `exists()` guard, while valid-but-divergent WAL and JSON inventories could project different histories | designate canonical JSON as the sole event authority; treat any retained WAL as a reconciliation-only legacy mirror and fail closed on symlink or byte-semantic divergence | repair implemented locally; runtime append refuses retained WAL until it is reconciled and retired; independent re-audit pending |
| F-019 | Transcript export validated a temporary pathname and later gave that mutable pathname to Goose | preserve both directory and file descriptor custody across child export, then install by descriptor-bound inode only if the canonical directory identity is unchanged | repair implemented locally with export-failure and directory-inode-swap lesions; independent re-audit pending |
| F-020 | Approved mutation mode accepted a non-empty opaque object as authority evidence | require the mode-specific exact reference set, session/target identity, SHA-256 syntax, and reconstruction of every referenced byte before close can validate | repair implemented locally; independent re-audit pending |
| F-021 | Retaining a transcript file descriptor did not prove that the temporary filename still named that inode at installation | open the name relative to the retained directory descriptor with no-follow semantics and require exact device/inode equality before linking | repair implemented locally with a temporary-name replacement lesion; independent re-audit pending |
| F-022 | Canonical close reconstruction checked approved-reference names and digests but did not repeat the runtime's namespace, owning-validator, cross-binding, scope, and final-state checks | use the same approved patch/rollback reconstruction functions before persistence and during later RunView custody validation | repair implemented locally with digest-correct foreign-file refusal; independent re-audit pending |
| F-023 | A temporary-name swap inside the hard-link boundary could occur after the pre-link inode comparison | reopen the canonical destination after linking, compare it to the retained export inode, and remove/refuse any mismatch | repair implemented locally with a link-boundary swap lesion; independent re-audit pending |
| F-024 | Shared runtime reconstruction helpers assumed already-screened JSON object shapes and could raise through persistence or RunView | make the canonical reconstruction seam total: unexpected evidence types or validator exceptions become explicit fail-closed custody errors | repair implemented locally; malformed evidence and rollback integration are in the focused battery; independent re-audit pending |
| F-025 | Post-link validation compared only an already-open destination fd, not the canonical directory entry at acceptance | add a final no-follow, dirfd-relative stat of the canonical name and remove/refuse any inode mismatch | repair implemented locally with a post-open canonical-name replacement lesion; independent re-audit pending |

## Deferred and optional opportunities

Items stay here until evidence moves them into a future ratified plan set.

| ID | Opportunity | Potential value | Why deferred |
| --- | --- | --- | --- |
| O-001 | Native Goose skills extension | upstream progressive disclosure may reduce prompt weight | must prove no ambient executable/filesystem authority beyond generated instruction assets |
| O-002 | Goose adversary review as an advisory signal | possible prompt-injection/risk annotation | fail-open behavior cannot be governance and current builder boundary is stronger |
| O-003 | Observation-only Goose hooks | refresh hints and diagnostics correlation | shell/best-effort hooks cannot own ledger or receipt custody |
| O-004 | Deep Agents as a Goose ACP provider | tighter protocol-level UI integration | duplicates session/runtime ownership before direct delegation is mastered |
| O-005 | Ephemeral Goose-native micro-subagents | possibly lower latency for trivial read-only work | creates a second orchestrator and ambiguous budget/evidence ownership |
| O-006 | Web or desktop workspace | richer visualization | terminal-first Lens/Inspect must first prove the interaction contract |
| O-007 | Builder-II self-hosting | end-to-end dogfood and eventual operational leverage | requires separate independent qualification and explicit admission |

## Blockers and risks

| ID | Risk/blocker | Required response |
| --- | --- | --- |
| R-001 | PR #21 remains open, so this branch is stacked | do not merge PR #21 implicitly; reconcile base before successor delivery |
| R-002 | Goose 1.47 is installed but unadmitted | qualify exact binary or retain policy and provide downgrade/select remediation |
| R-003 | A compatibility alias could silently become permanent | attach removal to one release and pin deprecation tests/docs |
| R-004 | UI convenience could duplicate authority interpretation | derive RunView and actions from owning validators/registry only |
| R-005 | Large program scope could blur implemented versus complete | maintain this ledger per work item and close one plan set at a time |
| R-006 | Existing runtime families use partially distinct lifecycle event vocabularies and locations | define a shared lifecycle contract and adapters; preserve legacy evidence without wrapping it into false validity |

## Update protocol

After every implementation unit:

1. Update the work-item state and exact evidence.
2. Record new discoveries separately from approved scope.
3. Add architectural choices to the decision log with a revisit condition.
4. Add attractive but unproven ideas to deferred opportunities.
5. Record exact verification commands and distinguish focused, full CI, PR, merge,
   and promotion states.
6. Reconcile the dashboard before commit and again after hosted readback.

Never edit an earlier verification entry to claim a stronger result. Add a new row.
