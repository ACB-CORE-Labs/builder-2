# PR 203 deepagents Forge execution plan

Status: passive plan artifact. Execution is disabled until a HITL approval artifact explicitly authorizes this plan.

Objective source: `/Users/you/.codex/attachments/93eaccdb-2f04-4b60-a554-f1dbf50d15a8/goal-objective.md`

Repository state observed before this plan:

- Worktree: `/Users/you/Projects/builder-II`
- Branch: `pr-203-deepagents-forge`
- PR branch: `feat/deepagents-forge`
- PR: AssetOverflow/builder-II #203
- Short status before this file: clean branch line only, no modified files reported.

## Governance boundary

This artifact is a plan, not execution, verification, promotion, or approval.

Disabled in this phase:

- dependency synchronization
- test execution
- shell/subprocess verification beyond passive repository inspection
- implementation edits beyond this plan artifact
- source writes outside this plan artifact
- Forge profile emission
- Goose runtime activation
- deepagents runtime activation
- MCP/tool invocation
- model/provider execution
- autonomous source writes
- git mutation, commit, push, or PR update
- runtime promotion or command-authority promotion

Before implementation, a HITL approval artifact must identify this plan and authorize the bounded PR #203 execution scope. Planned is not executed. Executed is not verified. Verified is not promoted.

## Map

Direction 1: patch the red test only.

- Shape: reproduce the failing test, repair the immediate cause, rerun the narrow Forge lane.
- Invariant preserved: minimal blast radius and truthful failure-first sequencing.
- Risk: may leave command authority, docs, TUI state, and emission semantics below the PR objective.
- Disposition: required as the first correction operator, not sufficient as the final structure.

Direction 2: widen Forge into an active runtime or agent launcher.

- Shape: let Forge create profiles and then run, promote, or dispatch them through Goose/deepagents.
- Invariant failure: collapses proposal, execution, and authority into one surface. It would violate builder-II governance.
- Disposition: rejected.

Direction 3: harden Forge as a governed artifact kernel.

- Shape: centralize spec validation, make preview and emission truthful, constrain writes, expose optional hooks as evidence, preserve dry-run purity, and bind command surfaces to command authority only where they actually exist.
- Invariants preserved: Forge emits bounded artifacts, not authority. Runtime and promotion remain pending external gates.
- Disposition: chosen.

Direction 4: add orchestration proposal artifacts only if the existing seams support a clean slice.

- Shape: Forge may reference target profiles, handoff notes, Goose recipe/tool refs, and verification expectations as planned orchestration metadata.
- Invariant preserved: proposed orchestration remains passive and reviewable.
- Risk: sprawl if it requires broad new runtime contracts.
- Disposition: conditional; prefer a precise design doc and boundary tests unless the first slice is small and native to current patterns.

## Build plan after approval

1. Establish truth.
   - Run dependency sync if needed for the local environment.
   - Run the full test suite requested by the objective.
   - Capture the exact first failure and fix that root cause before broadening scope.

2. Audit current Forge surfaces.
   - Read Forge schema, wizard, preview, emission, TUI, CLI, deepagents bridge/CLI, profile handling, command authority, Goose bridge/CLI, Forge docs, deepagents policy/readiness docs, command docs, README, and related tests.
   - Record false claims, unsafe paths, weak validation, overbroad exception handling, dry-run leaks, TUI state bugs, bridge overclaims, and unregistered command surfaces.

3. Harden spec validation.
   - Make slug, target profile, capability/HITL gate, output path, rollback path, and emission preconditions centralized and test-backed.
   - Preserve builder-II as a generic governed platform; CORE can be a target profile only.

4. Harden emission and preview.
   - Return a truthful result structure with dry-run state, profile/handoff writes, hook attempts/failures, paths, blockers, and warnings.
   - Keep dry-run strictly side-effect free.
   - Keep real writes bounded to governed profile/handoff paths unless a separately governed output surface is introduced and tested.
   - State clearly that generated handoff artifacts do not grant runtime promotion.

5. Harden CLI and TUI behavior.
   - Ensure deterministic headless behavior, non-zero invalid-spec exits, testable preview/emit paths, and no runtime-authority claims.
   - Fix Done, abort/cancel, and `app.run()` result handling so UI state cannot masquerade as emission evidence.

6. Decide command integration honestly.
   - Either register a real `builder-deepagents forge` subcommand with command authority, docs, pyproject/registry sync tests, and no over-authorization, or keep Forge module-invoked and document that truth.
   - Do not leave command claims without implemented command surfaces.

7. Add first clean orchestration/template slice only if it stays bounded.
   - Prefer passive templates, examples, or design docs over runtime behavior.
   - Add tests that prove non-authority boundaries remain intact.

8. Verify.
   - Run the specific failing test after the root fix.
   - Run Forge schema, preview, and emission tests.
   - Run compileall for `builder_ii` and `tests`.
   - Run command-doc and command-matrix audits.
   - Run the full test suite again before commit.

9. Commit preparation.
   - Inspect the diff for unrelated changes.
   - Commit only the bounded PR #203 hardening work after verification evidence is collected.
   - Do not push or merge unless separately authorized.

## Proposed verification profiles

The objective requests these verification lanes after approval:

- dependency synchronization for all configured groups;
- full Python test suite;
- first failing test reproduced and rerun specifically;
- Forge schema, preview, and emission test lane;
- Python compile check over `builder_ii` and `tests`;
- documentation command audit;
- platform command matrix.

This plan records those lanes as proposed work only. It does not execute them.

## Justify

The intrinsic space of PR #203 is not a wizard UI. It is a governed artifact-production field with three conjugate operators:

- spec creation and validation;
- preview and emission;
- command/docs/tests as corrective evidence.

The masterstroke is to keep Forge powerful by refusing hidden authority. A valid Forge spec may reconstruct a profile, preview bounded writes, emit governed artifacts, and hand off intent, but it cannot become runtime permission. Every forward operator receives a correction: validation blocks malformed specs, preview exposes exact effects, dry-run proves non-mutation, emission reports hook failures instead of swallowing them, command authority constrains CLI claims, and tests bind the contract.

## HITL stop

Stop here until a human approval artifact authorizes execution of this PR #203 plan. After approval, execution must stay within this scope and begin with the exact failing test, not broad speculative refactoring.
