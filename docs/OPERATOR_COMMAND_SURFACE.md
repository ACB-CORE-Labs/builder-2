# Operator Command Surface Index

This canonical index defines the bounded command surface available to a human operator when interacting with builder-II.

## Identity Boundary

builder-II is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench, not CORE UI/UX, and not a second CORE runtime. CORE is only a target profile.

## Target Profiles

builder-II supports three distinct target profiles:

- `generic`: Default profile for standard local governed developer workflows.
- `builder`: Specialized profile for self-developing the builder-II platform.
- `core`: Target profile for governed sessions operating against CORE repositories (CORE is only a target profile, not an identity or runtime).

## Related Documentation

This index links together the core governed operator lane documentation:

- [Operator Quickstart](OPERATOR_QUICKSTART.md)
- [CORE Demo Walkthrough](CORE_DEMO_WALKTHROUGH.md)
- [Governed Prepare Package](GOVERNED_PREPARE_PACKAGE.md)
- [Validate Prepare Package](VALIDATE_PREPARE_PACKAGE.md)
- [Prepare Package Summary](PREPARE_PACKAGE_SUMMARY.md)
- [Profile Packs](PROFILE_PACKS.md)

## Exact First-Class Operator Lane

The primary governed sequence for preparing, validating, and summarizing a local development session package consists of the exact first-class operator lane:

1. `builder-session prepare-package`
2. `builder-session validate-prepare-package`
3. `builder-session summarize-prepare-package`

The event-sourced guided workflow lane composes existing passive artifacts into a replayable operator chain:

1. `builder workflow plan`
2. `builder workflow promote`
3. `builder workflow candidate`
4. `builder workflow verify-chain`
5. `builder workflow handoff`
6. `builder ledger replay <session-id>`
7. `builder ledger audit <artifact-sha>`

## Canonical Governed E2E Proof

The canonical governed session lane binds together the platform preparation tools into a single, cohesive, fail-closed sequence. This end-to-end relationship connects prepare-package creation, convention kernel platform spine coordination, index recognition, and passive verification:

1. **Governed Prepare Package**: Emits deterministic component artifacts (`prepare-package.json`, `session-workflow.json`, `goose-readonly-session.json`, `verification-profile-report.json`, `repo-map.json`, `context-pack.json`, `handoff-note.json`) into an isolated output directory while keeping package state at `PREPARED_ONLY`.
2. **ConventionKernel Platform Spine**: Composes the governed platform spine bundle, verifying target profile constraints and auditing that all proposed commands belong to Tier 0 or Tier 1 (or remain uninvoked operator-managed helpers).
3. **Artifact Index Recognition**: Inspects emitted package output files to verify that generated records conform to known schemas without unknown or invalid entries.
4. **Passive Chain Verification**: Cryptographically resolves and audits cross-record references across the emitted bundle using canonical JSON digests.
5. **Agent Assignment / Orchestration v2**: Binds target, task, agent, model recommendation, context, verification, tool policy, HITL policy, outputs, and handoff refs into deterministic assignment artifacts without execution authority.
6. **Fail-Closed Governance**: Throughout the entire sequence, runtime execution, model calls, shell invocations, and target repository modifications remain disabled, and planned verification checks remain strictly unexecuted (`NOT_RUN`).

## Bounded Approved Verification Lane

`builder-verify run-approved` is the current approved verification execution lane. It is not arbitrary shell. The operator must first create a passive plan with `builder-verify plan`, bind human approval with `builder-verify approve-plan`, then run one fixed profile with `builder-verify run-approved --profile platform_status` or `--profile docs_audit`. The runner validates command authority, uses `shell=False`, forwards only an environment allowlist, captures bounded output, compares git preflight/postflight state, writes an honest receipt for success, failure, timeout, or pre-execution denial, and emits a generated postflight sidecar.

Still gated: arbitrary argv, broad shell execution, patch authority, model/MCP/Goose/deepagents runtime, commit/push automation, and model-driven file mutation.

## CORE Demo Loop

The real-world CORE recording lane is separate from the passive session lane:

1. `builder-platform demo-loop --phase prepare`
2. `builder-platform demo-loop --phase approve --approve`
3. `builder-platform demo-loop --phase apply`
4. `builder-platform demo-loop --phase verify`
5. `builder-platform demo-loop --phase rollback`
6. `builder-platform demo-loop --phase finalize`
7. `builder-platform validate-demo-loop`

The alias `builder-platform wow --approve` runs the full sequence for a continuous recording. This lane uses a detached temporary AssetOverflow/core worktree, applies one digest-approved documentation marker patch, rolls it back, and emits `DEMO_EVIDENCE.md`. It does not mutate the source CORE checkout, commit, push, call models, activate Goose, invoke MCP, write hidden memory, or couple to CORE Workbench/UI.


## Command Taxonomy by Phase

The operator command surface is organized by phase. Every command operates strictly within bounded runtime authority and write permissions.

### Discovery / Inspection

#### Root governed inspector groups
- **Command name**: `builder tui`
- **Purpose**: Render the read-only status, roster, gates, HITL, handoff, and golden-path inspection panels.
- **Output artifact, if any**: None; terminal UI only.
- **Execution authority**: read-only observer; no runtime, model, shell, Goose, deepagents, MCP, tool, source-write, git, or memory authority.
- **Human responsibility**: Use the inspector to understand current governed state before invoking separate artifact or HITL command surfaces.
- **Writes**: Read-only; writes only stdout.

#### STRATUM launcher
- **Command name**: `builder stratum`
- **Purpose**: Launch the full Textual STRATUM operator interface.
- **Output artifact, if any**: None; terminal UI only.
- **Execution authority**: operator-managed presentation layer; runtime-changing operations still require their own governed subcommand boundaries.
- **Human responsibility**: Launch intentionally from an operator terminal when the full Textual app is desired.
- **Writes**: No direct source, git, model, Goose, deepagents, or MCP authority at the launcher boundary.

#### Root read-only TUI inspector
- **Command names**: `builder hitl *`, `builder profile *`, `builder model routing *`, `builder model registry *`, `builder promote *`, `builder postflight *`, `builder goose *`
- **Purpose**: Inspect existing governed artifacts from `$BUILDER_DIR` through first-class root `builder` command groups without creating, executing, promoting, or mutating anything.
- **Output artifact, if any**: None; stdout inspection only.
- **Execution authority**: read-only observer; invalid JSON, explicit lookup misses, schema failures, failed present gates, and governance violations exit non-zero.
- **Human responsibility**: Use the inspector to understand current state and then invoke separate governed artifact CLIs only when artifact creation or HITL execution is explicitly intended.
- **Writes**: Read-only; writes only stdout.

#### `builder-targets list`
- **Command name**: `builder-targets list`
- **Purpose**: Enumerate available target profiles (`generic`, `builder`, `core`) and their default configuration settings.
- **Output artifact, if any**: None (stdout inspection).
- **Execution authority**: disabled
- **Human responsibility**: Review available target profiles and select the appropriate profile before initiating session preparation.
- **Writes**: Read-only; writes only stdout (no artifact writes).

#### `builder-tools list`
- **Command name**: `builder-tools list`
- **Purpose**: Enumerate governed local tool definitions and check boundary definitions.
- **Output artifact, if any**: None (stdout inspection).
- **Execution authority**: disabled
- **Human responsibility**: Inspect available tool capabilities and verify read-only constraints.
- **Writes**: Read-only; writes only stdout.

#### `builder-readonly inspect`
- **Command name**: `builder-readonly inspect`
- **Purpose**: Inspect candidate repositories or sessions to generate a read-only candidate inspection report.
- **Output artifact, if any**: Optional inspection report artifact when `--output` is specified.
- **Execution authority**: disabled
- **Human responsibility**: Confirm repository state and verify read-only inspection reports before candidate promotion.
- **Writes**: Can write only explicit artifact output paths when requested; otherwise read-only stdout.

#### `builder-git-state inspect`
- **Command name**: `builder-git-state inspect`
- **Purpose**: Inspect repository git status, clean state, and current HEAD metadata.
- **Output artifact, if any**: None (stdout inspection).
- **Execution authority**: disabled
- **Human responsibility**: Ensure the target repository working tree is clean or understood before session initiation.
- **Writes**: Read-only; writes only stdout.

#### `builder-index list`
- **Command name**: `builder-index list`
- **Purpose**: List indexed governed artifacts across local ledgers.
- **Output artifact, if any**: None (stdout inspection).
- **Execution authority**: disabled
- **Human responsibility**: Audit existing artifacts in local storage.
- **Writes**: Read-only; writes only stdout.

#### `builder-session repo-map`
- **Command name**: `builder-session repo-map`
- **Purpose**: Create a bounded read-only repository map foundation artifact.
- **Output artifact, if any**: `repo-map.json` when `--output` is specified.
- **Execution authority**: artifact-only
- **Human responsibility**: Inspect repository structure and role classification before planning work.
- **Writes**: Writes only explicit artifact output paths specified via `--output`.

#### `builder-session context-pack`
- **Command name**: `builder-session context-pack`
- **Purpose**: Create a bounded read-only context pack foundation artifact from a repo map.
- **Output artifact, if any**: `context-pack.json` when `--output` is specified.
- **Execution authority**: artifact-only
- **Human responsibility**: Inspect selected files to understand relevant repository context. Do not treat as proof of correctness.
- **Writes**: Writes only explicit artifact output paths specified via `--output`.

### Session Preparation

#### `builder workflow plan`
- **Command name**: `builder workflow plan`
- **Purpose**: Create a governed workflow session graph from intent through profile pack, model-routing recommendation, orchestration assignment, and passive deepagents work plan artifacts.
- **Output artifact, if any**: `workflow-session.json`, `workflow-transition-plan.json`, `event-ledger.json`, `ledger-replay-report.json`, `workflow-status.json`, and composed passive planning artifacts under the workflow output directory.
- **Execution authority**: artifact-only
- **Human responsibility**: Inspect the generated session graph and confirm that all planned surfaces remain passive.
- **Writes**: Writes only explicit workflow artifact output paths.

#### `builder workflow promote`
- **Command name**: `builder workflow promote`
- **Purpose**: Record passive HITL promotion request, review, decision, and approval-boundary artifacts for candidate design.
- **Output artifact, if any**: HITL promotion artifacts, workflow transition, event record, replay report, ledger, and status.
- **Execution authority**: artifact-only; no runtime approval is granted.
- **Human responsibility**: Review that promotion remains limited to candidate-manifest design.
- **Writes**: Writes only workflow artifact output paths.

#### `builder workflow candidate`
- **Command name**: `builder workflow candidate`
- **Purpose**: Record a passive execution candidate manifest and structural validation report from the approved candidate-design boundary.
- **Output artifact, if any**: `execution-candidate-manifest.json`, validation report, workflow transition, event record, replay report, ledger, and status.
- **Execution authority**: artifact-only; no command execution.
- **Human responsibility**: Confirm that any later execution requires a separate exact HITL approval.
- **Writes**: Writes only workflow artifact output paths.

#### `builder workflow verify-chain`
- **Command name**: `builder workflow verify-chain`
- **Purpose**: Create artifact index and chain verification evidence for the passive workflow graph.
- **Output artifact, if any**: `artifact-index.json`, `chain-verification-report.json`, workflow transition, event record, replay report, ledger, and status.
- **Execution authority**: validation-only
- **Human responsibility**: Treat chain verification as evidence-link validation, not executed verification.
- **Writes**: Writes only workflow artifact output paths.

#### `builder workflow handoff`
- **Command name**: `builder workflow handoff`
- **Purpose**: Produce passive handoff and golden-path summary artifacts after successful chain verification.
- **Output artifact, if any**: `handoff-note.json`, `GOLDEN_PATH_CHAIN_v1.json`, `GOLDEN_PATH_DEMO_README.md`, workflow transition, event record, replay report, ledger, and status.
- **Execution authority**: artifact-only
- **Human responsibility**: Review the handoff before deciding whether any later runtime promotion is warranted.
- **Writes**: Writes only workflow artifact output paths.

#### `builder workflow status`
- **Command name**: `builder workflow status`
- **Purpose**: Reconstruct workflow status from event records rather than trusting mutable state.
- **Output artifact, if any**: Refreshed `ledger-replay-report.json`, `event-ledger.json`, and `workflow-status.json`.
- **Execution authority**: validation-only
- **Human responsibility**: Use replayed status as the current operational view.
- **Writes**: Writes only workflow artifact output paths.

#### `builder-session prepare-package`
- **Command name**: `builder-session prepare-package`
- **Purpose**: Create a bounded set of local preparation artifacts for a developer session without executing target-repo work.
- **Output artifact, if any**: `prepare-package.json`, `session-workflow.json`, `goose-readonly-session.json`, `verification-profile-report.json`, `repo-map.json`, `context-pack.json`, `handoff-note.json`, `deepagents-bridge-readiness.json`.
- **Execution authority**: planned-only (for workflow and verification plans) and artifact-only (for manifest generation).
- **Human responsibility**: Inspect generated session package artifacts and verify proposed workflow tasks.
- **Writes**: Writes only explicit artifact output paths specified via `--output-dir`.

#### `builder-session plan`
- **Command name**: `builder-session plan`
- **Purpose**: Generate a governed local read-only session workflow plan.
- **Output artifact, if any**: Optional workflow plan JSON artifact when `--output` is specified.
- **Execution authority**: planned-only
- **Human responsibility**: Review planned workflow steps and profile bindings before human evaluation.
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

#### `builder-session goose-readonly-plan`
- **Command name**: `builder-session goose-readonly-plan`
- **Purpose**: Create a read-only projection plan for bounded Goose inspection sessions.
- **Output artifact, if any**: Optional projection plan JSON artifact when `--output` is specified.
- **Execution authority**: planned-only
- **Human responsibility**: Confirm projection plan enforces strict read-only tool boundaries.
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

### Package Validation

#### `builder ledger list`
- **Command name**: `builder ledger list`
- **Purpose**: List known workflow ledgers and replayed stages without activating any workflow runtime.
- **Output artifact, if any**: None; JSON stdout only.
- **Execution authority**: validation-only
- **Human responsibility**: Locate the relevant session before replay or audit.
- **Writes**: Read-only; writes only stdout.

#### `builder ledger replay`
- **Command name**: `builder ledger replay`
- **Purpose**: Rebuild workflow status deterministically from event records.
- **Output artifact, if any**: Optional or default `ledger-replay-report.json`.
- **Execution authority**: validation-only
- **Human responsibility**: Confirm event order and status before making operational claims.
- **Writes**: Writes only explicit replay artifact output paths.

#### `builder ledger audit`
- **Command name**: `builder ledger audit`
- **Purpose**: Answer audit-by-SHA questions with event, actor, policy, decision, evidence, and next-transition context.
- **Output artifact, if any**: None; JSON stdout only.
- **Execution authority**: validation-only
- **Human responsibility**: Use SHA-linked events as evidence, not authority.
- **Writes**: Read-only; writes only stdout.

#### `builder ledger export`
- **Command name**: `builder ledger export`
- **Purpose**: Export the current passive event ledger artifact for a workflow session.
- **Output artifact, if any**: `event-ledger.json` or explicit export path.
- **Execution authority**: artifact-only
- **Human responsibility**: Preserve exported ledgers as review evidence only.
- **Writes**: Writes only explicit ledger artifact output paths.

#### `builder-session validate-prepare-package`
- **Command name**: `builder-session validate-prepare-package`
- **Purpose**: Validate a governed prepare package manifest and verify structural integrity, relative containment, existence, hash matches, and JSON schemas of referenced artifacts.
- **Output artifact, if any**: None (stdout confirmation message).
- **Execution authority**: artifact-only (verifies structural validity; does not prove that planned verification commands have been run).
- **Human responsibility**: Execute package validation prior to sharing or utilizing session packages.
- **Writes**: Read-only; writes only stdout.

#### `builder-session validate`
- **Command name**: `builder-session validate`
- **Purpose**: Validate an individual session workflow plan artifact against schema invariants.
- **Output artifact, if any**: None (stdout confirmation message).
- **Execution authority**: artifact-only
- **Human responsibility**: Ensure workflow plans adhere to required structural properties.
- **Writes**: Read-only; writes only stdout.

### Package Summarization

#### `builder-session summarize-prepare-package`
- **Command name**: `builder-session summarize-prepare-package`
- **Purpose**: Generate a human-readable summary of a validated prepare package for inspection and review.
- **Output artifact, if any**: Optional `prepare-package-summary.json` when `--output` is specified.
- **Execution authority**: artifact-only (summarization proves package integrity only; it does not convert planned verification into completed evidence and does not imply summary artifacts are authoritative).
- **Human responsibility**: Review summary metrics and perform manual verification checks before making claims.
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

### Handoff / Notes

#### `builder-notes create`
- **Command name**: `builder-notes create`
- **Purpose**: Create a structured developer note or observation record for session tracking.
- **Output artifact, if any**: Note JSON artifact.
- **Execution authority**: artifact-only
- **Human responsibility**: Accurately document context, blockers, or observations for downstream reviewers.
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

#### `builder-handoff create`
- **Command name**: `builder-handoff create`
- **Purpose**: Generate a passive handoff note bundle summarizing session context and status.
- **Output artifact, if any**: Handoff bundle JSON artifact.
- **Execution authority**: artifact-only (summary records do not trigger execution or become authoritative).
- **Human responsibility**: Verify handoff notes reflect actual state and pending manual steps before transfer.
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

### Verification Planning

#### `builder-verification plan`
- **Command name**: `builder-verification plan`
- **Purpose**: Emit a planned verification profile report outlining test commands and quality gates.
- **Output artifact, if any**: Verification profile report JSON artifact.
- **Execution authority**: planned-only
- **Human responsibility**: Execute planned verification commands manually and collect receipt evidence.
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

#### `builder-quality check`
- **Command name**: `builder-quality check`
- **Purpose**: Evaluate planned quality gate definitions against session manifests.
- **Output artifact, if any**: Optional quality inspection report when requested.
- **Execution authority**: artifact-only
- **Human responsibility**: Ensure quality gate definitions match required project standards.
- **Writes**: Can write only explicit artifact output paths when requested; otherwise stdout.

### Assignment / Orchestration

#### `builder-orchestration render-assignment`
- **Command name**: `builder-orchestration render-assignment`
- **Purpose**: Render passive Goal 2 assignment and orchestration assignment plan artifacts from existing source artifacts and SHA-256 refs.
- **Output artifact, if any**: `agent-assignment-plan.json` when `--assignment-output` is specified and `orchestration-assignment-plan.json` when `--output` is specified.
- **Execution authority**: artifact-only; no runtime activation.
- **Human responsibility**: Review the target/task/agent/model/context/verification/tool/HITL/output/handoff bindings, source digests, denied capabilities, and required promotions.
- **Writes**: Writes only explicit artifact output paths when requested.

#### `builder-orchestration validate`
- **Command name**: `builder-orchestration validate`
- **Purpose**: Validate v1 orchestration artifacts and Goal 2 assignment/orchestration artifacts; for Goal 2 artifacts it can emit a passive validation report.
- **Output artifact, if any**: Optional orchestration assignment validation report when `--output` is specified.
- **Execution authority**: validation-only; validation is structural and does not authorize execution.
- **Human responsibility**: Treat validation as source-ref and governance evidence only, not runtime approval.
- **Writes**: Writes only explicit validation-report output paths when requested.

#### `builder-orchestration dry-run`
- **Command name**: `builder-orchestration dry-run`
- **Purpose**: Explain what a Goal 2 orchestration assignment plan would bind and why, including planned bindings, denied capabilities, required promotions, expected evidence, and handoff expectations.
- **Output artifact, if any**: `orchestration-assignment-dry-run.json` when `--output` is specified.
- **Execution authority**: dry-run only; no execution, authorization, promotion, or verification evidence.
- **Human responsibility**: Inspect the dry-run before any separate HITL execution proposal or manual verification path.
- **Writes**: Writes only explicit artifact output paths when requested.

### Profile Pack Lifecycle

#### `builder-profile-pack scaffold`
- **Command name**: `builder-profile-pack scaffold`
- **Purpose**: Scaffold a passive profile-pack manifest with required pack areas, source refs, content hashes, and denied-by-default authority classifications.
- **Output artifact, if any**: Profile pack manifest JSON when `--output` is specified.
- **Execution authority**: artifact-only; no runtime activation.
- **Human responsibility**: Review the source refs, hashes, and authority classifications before using the pack as planning input.
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

#### `builder-profile-pack render`
- **Command name**: `builder-profile-pack render`
- **Purpose**: Render a passive profile-pack render plan from a manifest.
- **Output artifact, if any**: Profile pack render plan JSON when `--output` is specified.
- **Execution authority**: artifact-only; render means deterministic planning, not execution.
- **Human responsibility**: Confirm planned outputs remain passive and deny runtime authority.
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

#### `builder-profile-pack dry-run`
- **Command name**: `builder-profile-pack dry-run`
- **Purpose**: Emit a passive dry-run artifact proving planned pack entries would render without executing commands, starting Goose, constructing deepagents, calling models, or calling MCP tools.
- **Output artifact, if any**: Profile pack dry-run JSON when `--output` is specified.
- **Execution authority**: dry-run only; no execution, authorization, promotion, or verification evidence.
- **Human responsibility**: Inspect dry-run checks before any future capability promotion proposal.
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

#### `builder-profile-pack validate`
- **Command name**: `builder-profile-pack validate`
- **Purpose**: Validate profile-pack lifecycle artifacts and optionally emit a validation report.
- **Output artifact, if any**: Profile pack validation report JSON when `--output` is specified.
- **Execution authority**: validation-only; validation does not imply execution, authorization, verification, or promotion.
- **Human responsibility**: Treat validation as structural evidence only.
- **Writes**: Writes only explicit artifact output paths when `--output` is specified; otherwise stdout/errors only.

### HITL Request / Receipt / Evidence

#### HITL verification execution candidate artifact
- **Artifact kind**: `builder_ii.hitl_verification_execution_candidate`
- **Purpose**: Represent a candidate-only path for a future operator-approved verification command, including approval, preflight, request, receipt, postflight, rollback/no-mutation, verification record, and chain-binding requirements.
- **Output artifact, if any**: `hitl-verification-candidate.json` when created by library or future governed artifact tooling.
- **Execution authority**: candidate-only / planned-only; no execution authority.
- **Human responsibility**: Review the bounded command intent and all future evidence requirements before any manual/operator-approved verification run.
- **Writes**: The artifact itself may be written only to an explicit artifact output path by external tooling; it does not execute commands, run shell, call models, start Goose/deepagents, mutate source, write target repositories, or mutate git.

#### `builder-hitl promotion-request` / `promotion-review` / `promotion-decision` / `approval-boundary` / `rejection-record` / `validate-promotion`
- **Command name**: `builder-hitl promotion-request` (and related review, decision, boundary, rejection, validate subcommands)
- **Purpose**: Connect Goal 2/Goal 3 passive proposals to typed human request, review, decision, boundary, and rejection records, and validate structural compliance.
- **Output artifact, if any**: `hitl_promotion_request`, `hitl_promotion_review`, `hitl_promotion_decision`, `hitl_approval_boundary`, `hitl_rejection_record`, or `hitl_promotion_validation_report` JSON artifact.
- **Execution authority**: artifact-only / validation-only; executes nothing and grants no authority.
- **Human responsibility**: Review promotion request proposals, review findings, decisions, and approval boundaries passively before any future execution-candidate design.
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

#### `builder-hitl candidate-manifest` / `validate-candidate-manifest`
- **Command name**: `builder-hitl candidate-manifest` (and related validation subcommand)
- **Purpose**: Render a passive execution candidate manifest from human approval boundaries, or validate its invariants and structure.
- **Output artifact, if any**: `execution_candidate_manifest` or `execution_candidate_manifest_validation_report` JSON artifact.
- **Execution authority**: artifact-only / validation-only; executes nothing and grants no authority.
- **Human responsibility**: Passively record candidate execution parameters and verify them before any future activation.
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

#### `builder-hitl propose-patch`
- **Command name**: `builder-hitl propose-patch`
- **Purpose**: Generate a Human-In-The-Loop patch specification proposal for review.
- **Output artifact, if any**: Patch specification JSON artifact.
- **Execution authority**: planned-only
- **Human responsibility**: Review proposed diffs and patch specifications before any execution or application.
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

#### `builder-records generate`
- **Command name**: `builder-records generate`
- **Purpose**: Generate an approval record documenting explicit human review and sign-off decisions.
- **Output artifact, if any**: Approval record JSON artifact.
- **Execution authority**: artifact-only
- **Human responsibility**: Sign off only when verification expectations have been met manually.
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

#### `builder-receipt generate`
- **Command name**: `builder-receipt generate`
- **Purpose**: Create an execution receipt linking manual verification outputs to session plans.
- **Output artifact, if any**: Receipt JSON artifact.
- **Execution authority**: artifact-only
- **Human responsibility**: Ensure receipt evidence accurately captures real manual execution results.
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

### Optional Deepagents Readiness

#### `builder-deepagents policy`
- **Command name**: `builder-deepagents policy`
- **Purpose**: Create governed deepagents policy metadata without constructing deepagents.
- **Output artifact, if any**: Deepagents policy JSON.
- **Execution authority**: artifact-only
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

#### `builder-deepagents validate`
- **Command name**: `builder-deepagents validate`
- **Purpose**: Validate governed deepagents policy metadata.
- **Output artifact, if any**: None.
- **Execution authority**: validation-only
- **Writes**: Read-only; writes diagnostic stdout/stderr only.

#### `builder-deepagents readiness`
- **Command name**: `builder-deepagents readiness`
- **Purpose**: Create optional dependency-readiness metadata for deepagents integration.
- **Output artifact, if any**: Deepagents readiness JSON.
- **Execution authority**: artifact-only; no runtime activation.
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

#### `builder-deepagents validate-readiness`
- **Command name**: `builder-deepagents validate-readiness`
- **Purpose**: Validate deepagents dependency-readiness metadata.
- **Output artifact, if any**: None.
- **Execution authority**: validation-only
- **Writes**: Read-only; writes diagnostic stdout/stderr only.

#### `builder-deepagents forge`
- **Command name**: `builder-deepagents forge`
- **Purpose**: Preview or emit governed deepagent profile and handoff artifacts.
- **Output artifact, if any**: `profiles/deepagents/{slug}.yaml` and optional `profiles/deepagents/forge_{slug}.handoff.json`.
- **Execution authority**: artifact-only; no native deepagents construction, runtime promotion, model execution, shell execution, Goose activation, MCP/tool invocation, source mutation, or git mutation.
- **Writes**: Dry-run writes nothing. Real emission writes only the bounded Forge artifacts under `profiles/deepagents/`.

#### `builder-deepagents delegate`
- **Command name**: `builder-deepagents delegate`
- **Purpose**: Fail closed for forbidden active deepagents delegation.
- **Output artifact, if any**: None.
- **Execution authority**: forbidden / unpromoted
- **Writes**: None.

### Deepagents Work Artifacts

#### `builder-deepagents work-plan`
- **Command name**: `builder-deepagents work-plan`
- **Purpose**: Create a passive deepagents work plan artifact.
- **Output artifact, if any**: Deepagents work plan JSON.
- **Execution authority**: artifact-only
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

#### `builder-deepagents assign-subagent`
- **Command name**: `builder-deepagents assign-subagent`
- **Purpose**: Create a passive deepagents subagent assignment artifact.
- **Output artifact, if any**: Subagent assignment JSON.
- **Execution authority**: artifact-only
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

#### `builder-deepagents record-result`
- **Command name**: `builder-deepagents record-result`
- **Purpose**: Create a passive deepagents subagent result artifact.
- **Output artifact, if any**: Subagent result JSON.
- **Execution authority**: artifact-only
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

#### `builder-deepagents review-result`
- **Command name**: `builder-deepagents review-result`
- **Purpose**: Create a passive deepagents subagent review artifact.
- **Output artifact, if any**: Subagent review JSON.
- **Execution authority**: artifact-only
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

#### `builder-deepagents request-human-gate`
- **Command name**: `builder-deepagents request-human-gate`
- **Purpose**: Create a passive deepagents human gate request artifact.
- **Output artifact, if any**: Human gate request JSON.
- **Execution authority**: artifact-only
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

#### `builder-deepagents record-blocked-action`
- **Command name**: `builder-deepagents record-blocked-action`
- **Purpose**: Create a passive deepagents blocked action record artifact.
- **Output artifact, if any**: Blocked action record JSON.
- **Execution authority**: artifact-only
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

#### `builder-deepagents proposal-result`
- **Command name**: `builder-deepagents proposal-result`
- **Purpose**: Create a passive deepagents proposal result artifact.
- **Output artifact, if any**: Proposal result JSON.
- **Execution authority**: artifact-only
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

#### `builder-deepagents validate-work-artifact`
- **Command name**: `builder-deepagents validate-work-artifact`
- **Purpose**: Validate any passive deepagents work-output artifact file.
- **Output artifact, if any**: None.
- **Execution authority**: validation-only
- **Writes**: Read-only; writes diagnostic stdout/stderr only.

#### `builder-deepagents execution-candidate`
- **Command name**: `builder-deepagents execution-candidate`
- **Purpose**: Create the bounded protocol execution candidate from a passive deepagents work plan.
- **Output artifact, if any**: `builder_ii.deepagents_execution_candidate`.
- **Execution authority**: artifact-only; no backend run. `--backend-mode optional_deepagents` requires a passing `builder_ii.deepagents_backend_readiness_gate`.
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

#### `builder-deepagents backend-readiness`
- **Command name**: `builder-deepagents backend-readiness`
- **Purpose**: Inspect the optional deepagents protocol adapter exports and produce the promotion-readiness gate required before `optional_deepagents` candidate creation.
- **Output artifact, if any**: `builder_ii.deepagents_backend_readiness_gate`.
- **Execution authority**: artifact-only readiness probe; no native deepagents agent construction.
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

#### `builder-deepagents approve-candidate`
- **Command name**: `builder-deepagents approve-candidate`
- **Purpose**: Bind HITL approval to the exact deepagents execution candidate digest.
- **Output artifact, if any**: `builder_ii.deepagents_execution_approval`.
- **Execution authority**: approval artifact only; the approval does not execute anything by itself.
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

#### `builder-deepagents run-approved`
- **Command name**: `builder-deepagents run-approved`
- **Purpose**: Run the approved protocol backend lane after validating candidate digest, approval digest, backend mode, budgets, and output-root containment.
- **Output artifact, if any**: Run envelope, hash-chained event records, replay report, event ledger, execution receipt, and optional checkpoint.
- **Execution authority**: HITL-gated protocol backend candidate only.
- **Writes**: Writes only deepagents evidence artifacts under the approved output root; no target-repo mutation, shell, model, Goose, MCP, git, source write, hidden memory, or native deepagents construction authority.

#### `builder-deepagents replay-run`
- **Command name**: `builder-deepagents replay-run`
- **Purpose**: Reconstruct deepagents run state from hash-chained event records.
- **Output artifact, if any**: `builder_ii.deepagents_replay_report`.
- **Execution authority**: validation-only; replay never reruns backend/model/tool work.
- **Writes**: Writes only explicit replay report output path.

#### `builder-deepagents evidence-bundle`
- **Command name**: `builder-deepagents evidence-bundle`
- **Purpose**: Bundle candidate, approval, run, receipt, ledger, replay, and optional checkpoint evidence for operator review.
- **Output artifact, if any**: `builder_ii.deepagents_evidence_bundle`.
- **Execution authority**: evidence-only.
- **Writes**: Writes only explicit artifact output paths.

#### `builder-deepagents resume-approved`
- **Command name**: `builder-deepagents resume-approved`
- **Purpose**: Resume a checkpointed approved protocol run only when the same candidate and approval still bind exactly.
- **Output artifact, if any**: Appended event records plus updated run envelope, replay report, ledger, and execution receipt.
- **Execution authority**: HITL-gated protocol backend candidate only, bounded by the original approval.
- **Writes**: Writes only deepagents evidence artifacts under the approved output root.

#### `builder-bridge status`
- **Command name**: `builder-bridge status`
- **Purpose**: Check optional integration bridge status report passively.
- **Output artifact, if any**: None (stdout inspection).
- **Execution authority**: disabled
- **Human responsibility**: Inspect bridge status passively.
- **Writes**: Read-only; writes only stdout.

### Release Proof Harness

#### `python scripts/verify_v0_release.py`
- **Command name**: `python scripts/verify_v0_release.py`
- **Purpose**: Execute the repeatable anti-handwave v0 release proof harness for builder-II, producing the 8 canonical governed preparation artifacts, platform spine bundle, chain verification reports, artifact index, and release manifest without runtime authority or source modifications.
- **Output artifact, if any**: `release-manifest.json`, `chain-verification-report.json`, `artifact-index.json`, `platform-spine.json`, and the canonical preparation artifacts written to the isolated output directory.
- **Execution authority**: artifact-only / proof-only
- **Human responsibility**: Execute proof harness to evaluate v0 release readiness and inspect emitted reports confirming no runtime execution occurred.
- **Writes**: Writes strictly to isolated output directory specified via `--output-dir` (defaulting to `dist/v0-release-proof`); target repository working tree remains 100% untouched.

## Explicit Forbidden Boundary

The operator command surface strictly adheres to builder-II governance and runtime boundaries. None of the commands listed above permit or execute:

- no target-repo execution
- no shell execution
- no subprocess-backed authority
- no Goose activation
- no deepagents activation/delegation
- no model/runtime execution
- no target-repo writes
- no Deephaven changes
- no CORE Workbench/UI coupling
- no conversion of planned verification into completed evidence

Furthermore, summary artifacts are not authoritative, and planned verification commands do not imply or constitute executed verification.
