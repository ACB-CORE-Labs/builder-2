# B8/B9 governed execution plan

Status: passive plan artifact. Execution is disabled until a HITL approval artifact or receipt explicitly authorizes this plan.

Objective source: `<user_home>/.codex/attachments/23d714f6-450f-4cd5-af30-a5f616d947af/goal-objective.md`

Repository state observed before this plan:

- Worktree: `<user_home>/.codex/worktrees/ba03/builder-II`
- Local `origin/main`: `dae925c` (`Merge pull request #186 from AssetOverflow/feat/b7-tool-mcp-gateway`)
- Current worktree state before this file: detached `HEAD` with no short-status modifications reported.
- Required sequence: B8 first on `feat/b8-artifact-memory`; open B8 PR. B9 only after B8 is merged or after rebasing from the merged B8 base, on `feat/b9-operator-product-polish`; open B9 PR separately.

## Governance boundary

This artifact is a plan, not execution, verification, promotion, or approval.

Disabled in this phase:

- branch creation
- implementation edits beyond this plan artifact
- tests or verification commands
- model/provider execution
- external tool or MCP invocation
- Goose runtime
- deepagents runtime
- shell/subprocess behavior added to product code
- target repository mutation
- autonomous memory writes
- hidden memory
- vector store behavior
- commit, push, or PR automation

Before implementation, a HITL approval artifact must identify this plan and authorize the B8 execution scope. Planned is not executed. Executed is not verified. Verified is not promoted.

## Context read

The plan is based on direct read-through of:

- `docs/BUILDER_II_COMPLETION_TRUTH_REPORT.md`
- `docs/PLATFORM_COMPLETION_AUDIT.md`
- `docs/plan/ARTIFACT_MEMORY_RFC.md`
- `docs/OPERATOR_QUICKSTART.md`
- `docs/COMMAND_AUTHORITY.md`
- `builder_ii/platform_completion_audit.py`
- `builder_ii/platform_status_cli.py`
- `builder_ii/command_authority.py`
- `builder_ii/event_ledger.py`
- `builder_ii/artifact_chain_verification.py`
- `builder_ii/handoff_notes.py`
- `builder_ii/handoff_artifacts.py`
- `builder_ii/handoff_bundle_records.py`
- `builder_ii/notes_cli.py`
- `builder_ii/workflow_records.py`
- `builder_ii/workflow_orchestrator.py`
- `builder_ii/ledger_cli.py`
- `builder_ii/model_cli.py`
- `builder_ii/tools_cli.py`
- `builder_ii/mcp_cli.py`
- `builder_ii/tool_invocation_gateway.py`
- recent tests around platform truth, command authority, ledger, model/tool/MCP receipts, and workflow golden path.

## Map

Direction 1: hidden or semantic memory store.

- Shape: add a persistent memory service or vector index behind operator commands.
- Invariant failure: hidden storage would make memory mutation invisible to artifacts, source refs, and command authority. Opaque embeddings would make search non-explainable.
- Disposition: rejected.

Direction 2: append memory behavior to handoff artifacts.

- Shape: make existing handoff notes or bundle records act as memory directly.
- Invariant failure: handoff summaries are evidence inputs, not source truth. Promoting them directly would inflate their authority and blur summary versus source.
- Disposition: rejected except as source-bound inputs for memory atoms.

Direction 3: content-addressed artifact memory graph.

- Shape: create explicit `builder_ii.memory_atom`, `builder_ii.memory_index`, `builder_ii.memory_reconstruction`, and `builder_ii.memory_search_result` artifacts. Every atom binds to exact source refs by digest. Index and reconstruction artifacts bind back to atom/source refs and carry stale/superseded state.
- Invariants preserved: no hidden memory, no vector DB, deterministic sorting/search, no source truth inflation, no target repo mutation, no authority granted by artifacts.
- Disposition: chosen for B8.

Direction 4: operator UX as a projection over truth matrix, ledger, and artifacts.

- Shape: add operator status, next-action, and golden-path reports generated from `platform_completion_audit.py`, command authority, ledger/artifact evidence, and B8 memory artifacts.
- Invariants preserved: status is reconstructed from source artifacts, not status prose or environment vibes. Golden path declares exercised and skipped capabilities according to state labels.
- Disposition: chosen for B9 after B8.

## B8 build plan

Branch and base after approval:

1. Refresh remote state and confirm `origin/main` is still at or after PR #186.
2. Create/switch to `feat/b8-artifact-memory` from updated `origin/main`.
3. Keep B8 scope limited to artifact memory and required truth/docs/authority updates.

Core implementation:

- Add `builder_ii/artifact_memory.py`.
- Add `builder_ii/memory_cli.py`.
- Add `builder-memory` console script.
- Register `builder-memory` and subcommands in `builder_ii/command_authority.py`.
- Register memory artifact validators in `builder_ii/artifact_chain_verification.py`.
- Update `builder_ii/platform_completion_audit.py` so `artifact memory` moves from `DESIGN_ONLY` to `PASSIVE_FOUNDATION`.
- Update `docs/COMMAND_AUTHORITY.md` from the registry table.
- Update `docs/PLATFORM_COMPLETION_AUDIT.md` and add or update memory docs, preferably `docs/ARTIFACT_MEMORY.md` while preserving the RFC as design history.

B8 command surface:

- `builder-memory atom`
- `builder-memory index`
- `builder-memory reconstruct`
- `builder-memory search`
- `builder-memory validate-atom`
- `builder-memory validate-index`
- `builder-memory validate-reconstruction`
- optional `builder-memory validate-search-result` if useful for test symmetry.

B8 artifact schemas:

- `builder_ii.memory_atom`
- `builder_ii.memory_index`
- `builder_ii.memory_reconstruction`
- `builder_ii.memory_search_result`

Memory atom required shape:

- `kind`
- `schema_version`
- `atom_id`
- `atom_state`: `ACTIVE`, `SUPERSEDED`, `STALE`, or `REJECTED`
- `source_refs`
- `claim_text` or `normalized_summary`
- `tags`
- `created_at`
- `supersedes_refs`
- `stale_reason`
- `review_state`
- `source_truth_state`: for example `SOURCE_BOUND`, `DERIVED_SUMMARY`, or `OPERATOR_NOTE`
- `artifact_is_authority=false`
- `grants_authority=false`
- `model_summary_is_authority=false`
- `target_repo_mutation=false`
- `governance`

Memory index required shape:

- `kind`
- `schema_version`
- `index_state`
- `atom_refs`
- `source_artifact_refs`
- `deterministic_sort_key`
- `index_digest`
- `stale_atom_ids`
- `superseded_atom_ids`
- `search_keys`
- `artifact_is_authority=false`
- `grants_authority=false`
- `governance`

Reconstruction required shape:

- `kind`
- `schema_version`
- `reconstruction_state`
- `query` or `requested_scope`
- `included_atom_refs`
- `excluded_atom_refs` with reasons
- `source_refs`
- `stale_warnings`
- `supersession_warnings`
- deterministic ordering declaration
- `reconstructed_context`
- `artifact_is_authority=false`
- `grants_authority=false`
- `no_source_truth_inflation=true`
- `governance`

B8 mechanics:

- Use canonical compact JSON SHA-256 via the existing `workflow_records.canonical_digest` grammar for JSON artifacts.
- Source refs must include `role`, `kind`, `path`, `sha256`, `required`, and `name`.
- Atom creation from files should derive refs from actual source artifacts, not operator-supplied unchecked digests.
- Atom and index validation should fail closed on malformed refs, broken digests, authority claims, model-summary authority, hidden-memory language, and target mutation claims.
- Index ordering should be deterministic across input ordering by canonical atom ref digest plus atom id.
- Search should be deterministic lexical/tag matching with explicit matched keys and refs. No embeddings.
- Reconstruction should include active atoms deterministically and either exclude or warn on stale/superseded/rejected atoms according to explicit policy.
- Handoff artifacts may become memory atoms only through source refs; handoff prose is not source truth.

B8 tests:

- `tests/test_artifact_memory.py`
- `tests/test_memory_cli.py`
- updates to `tests/test_command_authority.py`
- updates to `tests/test_platform_completion_truth.py`
- updates to `tests/test_platform_completion_audit.py`
- chain validator coverage for all B8 artifact kinds.

B8 validation commands:

- `CORE_REPO_PATH=. uv run pytest -q`
- `uv run pytest -q`
- `git diff --check`
- `uv run builder-platform matrix`
- `uv run builder-platform status`
- `uv run builder-platform audit-docs`

B8 acceptance:

- `builder-memory atom` emits or writes valid source-bound memory atoms.
- `builder-memory index` builds deterministic indexes from explicit atoms.
- `builder-memory reconstruct` emits replay-stable reconstructions with source refs and stale/superseded warnings.
- `builder-memory search` returns deterministic refs and explainable matches.
- `artifact memory` is truthfully promoted to `PASSIVE_FOUNDATION`.
- No B8 command calls models, tools, MCP, Goose, deepagents, shell, or subprocess.
- No B8 command mutates a target repo.
- Durable memory exists only as explicit output artifacts.
- B8 PR body maps implementation to checklist, state changes, and test results.

## B9 build plan

Precondition:

- B8 PR is open and complete, then B8 is merged or the B9 branch is created from a base that includes the B8 implementation.

Branch and base:

1. Refresh `origin/main` after B8 merge or use the merged B8 base.
2. Create/switch to `feat/b9-operator-product-polish`.
3. Keep B9 separate from B8 unless explicitly re-approved.

Core implementation:

- Add `builder_ii/operator_status.py`.
- Add `builder_ii/operator_next.py`.
- Add `builder_ii/operator_golden_path.py` or equivalent if the golden path is not best housed in an existing module.
- Extend `builder_ii/platform_status_cli.py` with unified platform commands.
- Register new subcommands in `builder_ii/command_authority.py`.
- Update `docs/COMMAND_AUTHORITY.md`, `docs/PLATFORM_COMPLETION_AUDIT.md`, and `docs/OPERATOR_QUICKSTART.md`.

B9 command surface:

- `builder-platform operator-status`
- `builder-platform next`
- `builder-platform golden-path`
- `builder-platform validate-golden-path`

Root `builder status`, `builder doctor`, `builder next`, or `builder demo` wrappers are not planned unless the existing codebase strongly requires compatibility.

B9 artifact schemas:

- `builder_ii.operator_status_report`
- `builder_ii.operator_next_action_report`
- `builder_ii.operator_golden_path_report`
- `builder_ii.release_proof_from_truth_matrix`
- `builder_ii.golden_path_transcript`

B9 mechanics:

- Operator status derives from `platform_completion_audit.py`, command authority validation, optional ledger/session paths, setup/onboarding state if supplied, and B8 memory/index/reconstruction artifacts when supplied.
- Next action derives from matrix state and evidence gaps, not prose.
- Golden path runs in an output directory with a temp/safe target fixture and existing in-process artifact builders where possible.
- Golden path report must declare promoted capabilities exercised and unpromoted or skipped capabilities by exact state label.
- If a capability is not `OPERATIONALLY_VERIFIED`, the report must mark it unavailable/deferred instead of faking coverage.
- Status and next commands remain read-only/validation-only. Golden path may write explicit report/transcript/artifact outputs only.
- No CORE Workbench/UI, no landing page, no autonomous commit/push, no Deephaven.

B9 tests:

- `tests/test_operator_status.py`
- `tests/test_operator_next.py`
- `tests/test_operator_golden_path.py`
- updates to platform truth and command authority tests.
- CLI snapshot-style assertions for key output messages.
- failure recovery tests for missing ledger, missing memory index, missing config, and unknown capability states.

B9 validation commands:

- `CORE_REPO_PATH=. uv run pytest -q`
- `uv run pytest -q`
- `git diff --check`
- `uv run builder-platform matrix`
- `uv run builder-platform status`
- `uv run builder-platform audit-docs`

B9 acceptance:

- A new operator can run one governed command path and see target/context state, approval/authority state, verification/patch/rollback state if enabled, model/tool state if enabled, B8 memory/handoff state, ledger/replay/audit state, and one next action.
- Operator report is sourced from truth matrix, ledger, and artifacts.
- `operator quickstart/golden path` is promoted only if tests and reports prove the workflow from B1-B8 without misleading claims.
- B9 PR body maps implementation to checklist, states no CORE Workbench/UI, no autonomous commit/push, no landing page, and includes exact test results.

## Justification

The intrinsic space is an artifact graph with digest-bound provenance, not a mutable memory heap. B8 treats memory as reconstruction over source-bound atoms, with stale and superseded state as first-class structure. The corrective operator for every memory write is validation plus staleness/supersession reporting; the corrective operator for reconstruction is source-ref disclosure plus no-source-truth-inflation.

B9 then projects that graph into an operator surface. It does not create a parallel status reality. It harmonizes the truth matrix, command authority, ledger, and B8 memory artifacts into reports that remain reviewable and replay-stable.

## HITL stop

Stop here until a human approval artifact authorizes execution of B8 from this plan. After approval, execution must stay within the B8 scope above. B9 requires a separate post-B8 base and should not begin until B8 is implemented, validated, and opened as its own PR.
