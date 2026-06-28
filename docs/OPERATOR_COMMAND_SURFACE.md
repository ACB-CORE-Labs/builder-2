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
- [Governed Prepare Package](GOVERNED_PREPARE_PACKAGE.md)
- [Validate Prepare Package](VALIDATE_PREPARE_PACKAGE.md)
- [Prepare Package Summary](PREPARE_PACKAGE_SUMMARY.md)

## Exact First-Class Operator Lane

The primary governed sequence for preparing, validating, and summarizing a local development session package consists of the exact first-class operator lane:

1. `builder-session prepare-package`
2. `builder-session validate-prepare-package`
3. `builder-session summarize-prepare-package`

## Canonical Governed E2E Proof

The canonical governed session lane binds together the platform preparation tools into a single, cohesive, fail-closed sequence. This end-to-end relationship connects prepare-package creation, convention kernel platform spine coordination, index recognition, and passive verification:

1. **Governed Prepare Package**: Emits deterministic component artifacts (`prepare-package.json`, `session-workflow.json`, `goose-readonly-session.json`, `verification-profile-report.json`, `repo-map.json`, `context-pack.json`, `handoff-note.json`) into an isolated output directory while keeping package state at `PREPARED_ONLY`.
2. **ConventionKernel Platform Spine**: Composes the governed platform spine bundle, verifying target profile constraints and auditing that all proposed commands belong to Tier 0 or Tier 1 (or remain uninvoked operator-managed helpers).
3. **Artifact Index Recognition**: Inspects emitted package output files to verify that generated records conform to known schemas without unknown or invalid entries.
4. **Passive Chain Verification**: Cryptographically resolves and audits cross-record references across the emitted bundle using canonical JSON digests.
5. **Fail-Closed Governance**: Throughout the entire sequence, runtime execution, model calls, shell invocations, and target repository modifications remain disabled, and planned verification checks remain strictly unexecuted (`NOT_RUN`).


## Command Taxonomy by Phase

The operator command surface is organized by phase. Every command operates strictly within bounded runtime authority and write permissions.

### Discovery / Inspection

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

### HITL Request / Receipt / Evidence

#### HITL verification execution candidate artifact
- **Artifact kind**: `builder_ii.hitl_verification_execution_candidate`
- **Purpose**: Represent a candidate-only path for a future operator-approved verification command, including approval, preflight, request, receipt, postflight, rollback/no-mutation, verification record, and chain-binding requirements.
- **Output artifact, if any**: `hitl-verification-candidate.json` when created by library or future governed artifact tooling.
- **Execution authority**: candidate-only / planned-only; no execution authority.
- **Human responsibility**: Review the bounded command intent and all future evidence requirements before any manual/operator-approved verification run.
- **Writes**: The artifact itself may be written only to an explicit artifact output path by external tooling; it does not execute commands, run shell, call models, start Goose/deepagents, mutate source, write target repositories, or mutate git.

#### `builder-hitl plan-patch`
- **Command name**: `builder-hitl plan-patch`
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

#### `builder-deepagents check-readiness`
- **Command name**: `builder-deepagents check-readiness`
- **Purpose**: Inspect optional bridge readiness and configuration for deepagents integration.
- **Output artifact, if any**: Optional readiness report JSON artifact.
- **Execution authority**: disabled / artifact-only (readiness evaluation only; no runtime activation).
- **Human responsibility**: Confirm readiness status without relying on autonomous delegation.
- **Writes**: Writes only explicit artifact output paths when `--output` is specified.

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
