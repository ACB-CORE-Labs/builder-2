# builder-II documentation index

This is the reference-tier entry point into `docs/`. It exists so a reader can find any of
builder-II's ~136 tracked documents by topic instead of scrolling an alphabetical file listing.

## Entry path

builder-II documentation is organized as three tiers, each narrower and deeper than the last:

1. **[`README.md`](../README.md)** (repo root) — what builder-II is, the governing distinctions,
   install, and a curated "Documentation map" of the ~40 documents most readers need first.
2. **New-operator path**
   - **[`docs/GETTING_STARTED.md`](GETTING_STARTED.md)** — **start here as a new builder**: mental
     model (determinism / audit / governance), optimal setup order, and how to leverage **STRATUM**
     against every major subsystem (artifacts, HITL, Goose, deepagents, models, the CodeVault commercial seam, promotion).
   - **[`FIRST_SESSION.md`](../FIRST_SESSION.md)** (repo root) — the single validated onboarding
     path: clone to one complete governed patch loop in one sitting (CI-smoked).
   - **[`docs/OPERATOR_QUICKSTART.md`](OPERATOR_QUICKSTART.md)** — operator golden path
     (`builder-platform status` / `operator-status` / `next` / `golden-path`) plus the
     governed demo-loop entrypoint. Only what is currently true is documented; see
     [`docs/CAPABILITY_PROMOTION.md`](CAPABILITY_PROMOTION.md) and
     [`docs/PLATFORM_COMPLETION_AUDIT.md`](PLATFORM_COMPLETION_AUDIT.md) for promotion state.
   - **[`docs/STRATUM.md`](STRATUM.md)** — STRATUM console reference (keys, flags, walkthrough opt-out).
   - **[`docs/GETTING_STARTED.md`](MAXIMIZING_PROFICIENCY.md)** — walkthroughs for advanced setup, STRATUM console navigation, local model setup, and deepagents orchestration.
   - **[`docs/GLOSSARY.md`](GLOSSARY.md)** — centralized definitions for core terminology.
3. **This file** — the reference tier: every document in `docs/`, grouped by subsystem, for anyone
   going deeper than the curated map.

Also see **[`docs/demos/CORE_READONLY_FOUNDER_DEMO.md`](demos/CORE_READONLY_FOUNDER_DEMO.md)** — a
real, currently-runnable read-only governed demo (`builder-targets readonly-founder-demo`) worth
knowing about alongside the quickstart's golden path, since it isn't otherwise linked from
`OPERATOR_QUICKSTART.md`.

## Full index, by subsystem

### Start here

| Document | Purpose |
| --- | --- |
| [`docs/GLOSSARY.md`](GLOSSARY.md) | builder-II Centralized Glossary |
| [`docs/MANIFESTO.md`](MANIFESTO.md) | builder-II Manifesto |
| [`docs/PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md) | builder-II project overview |
| [`docs/PLATFORM_COMPLETION_AUDIT.md`](ROADMAP.md) | builder-II roadmap |
| [`docs/adrs/README.md`](adrs/README.md) | builder-II Architecture Decision Records |
| [`docs/adrs/ADR-0001-core-builder-ii-governed-engineering-extension.md`](adrs/ADR-0001-core-builder-ii-governed-engineering-extension.md) | ADR-0001: builder-II as a Governed Engineering Extension |
| [`docs/adrs/ADR-0002-builder-convention-layer-over-codename-goose.md`](adrs/ADR-0002-builder-convention-layer-over-codename-goose.md) | ADR-0002: Builder Convention Layer over Codename Goose |
| [`docs/adrs/ADR-0003-builder-ii-generic-platform-identity-and-capability-factory.md`](adrs/ADR-0003-builder-ii-generic-platform-identity-and-capability-factory.md) | ADR-0003: builder-II Generic Platform Identity and Capability Factory |
| [`docs/adrs/ADR-0004-core-born-builders-signet-doctrine.md`](adrs/ADR-0004-core-born-builders-signet-doctrine.md) | ADR-0004: CORE-Born Builder's Signet Doctrine |
| [`docs/adrs/ADR-0008-governed-deepagents-model-invocation-lane.md`](adrs/ADR-0008-governed-deepagents-model-invocation-lane.md) | ADR-0008: Governed deepagents Model-Invocation Lane (Proposed, DESIGN_ONLY) |

### Operator onboarding and guides

| Document | Purpose |
| --- | --- |
| [`docs/GETTING_STARTED.md`](GETTING_STARTED.md) | **New builder start here** — setup order, governance mental model, STRATUM × full platform |
| [`docs/GETTING_STARTED.md`](MAXIMIZING_PROFICIENCY.md) | Walks through advanced setup, STRATUM console navigation, local model setups, and deepagent execution |
| [`docs/OPERATOR_QUICKSTART.md`](OPERATOR_QUICKSTART.md) | Operator Quickstart |
| [`docs/OPERATOR_GUIDE.md`](OPERATOR_GUIDE.md) | builder-II operator guide |
| [`docs/OPERATOR_PLAYBOOK.md`](OPERATOR_PLAYBOOK.md) | builder-II Operator Playbook |
| [`docs/manual.md`](manual.md) | Builder Platform Manual |
| [`docs/CONFIG_ONBOARDING.md`](CONFIG_ONBOARDING.md) | Config + Onboarding Kernel |
| [`docs/RATIFICATION_GRANTS.md`](RATIFICATION_GRANTS.md) | Which confirmations you may delegate to a standing grant, which ones can never be delegated, and the audit trail either way |
| [`docs/CORE_DEMO_WALKTHROUGH.md`](CORE_DEMO_WALKTHROUGH.md) | CORE Demo Walkthrough |
| [`docs/demos/FLAGSHIP_DEMO_SCRIPT.md`](demos/FLAGSHIP_DEMO_SCRIPT.md) | Flagship 15-minute demo script with live tamper-detection beat |
| [`docs/recordings/README.md`](recordings/README.md) | Recorded asciinema casts of the governed loop, tamper beat, and builder init |
| [`docs/TARGET_PROFILE_DEMOS.md`](TARGET_PROFILE_DEMOS.md) | Target profile demos |
| [`docs/demos/CORE_READONLY_FOUNDER_DEMO.md`](demos/CORE_READONLY_FOUNDER_DEMO.md) | CORE Read-Only Founder Demo |
| [`docs/demos/CODE_VAULT_DETERMINISM_DEMO.md`](demos/CODE_VAULT_DETERMINISM_DEMO.md) | CodeVault Determinism Demo — Recording Walkthrough (Requires Commercial Upgrade) |

### Command and capability governance

| Document | Purpose |
| --- | --- |
| [`docs/OPERATOR_COMMAND_SURFACE.md`](OPERATOR_COMMAND_SURFACE.md) | Operator Command Surface Index |
| [`docs/COMMAND_AUTHORITY.md`](COMMAND_AUTHORITY.md) | COMMAND_AUTHORITY |
| [`docs/COMMAND_SURFACE_AUDIT.md`](COMMAND_SURFACE_AUDIT.md) | Command Surface Audit |
| [`docs/CAPABILITY_PROMOTION.md`](CAPABILITY_PROMOTION.md) | Capability promotion registry |
| [`docs/KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) | Known limitations, generated from the completion truth matrix |
| [`docs/RUNTIME_PROMOTION.md`](RUNTIME_PROMOTION.md) | Runtime promotion contract |
| [`docs/capability_gates.md`](capability_gates.md) | Local capability gates |
| [`docs/PROMOTION_READINESS.md`](PROMOTION_READINESS.md) | Promotion readiness |
| [`docs/PROMOTION_DECISIONS.md`](PROMOTION_DECISIONS.md) | Promotion decisions |
| [`docs/GOVERNANCE_INVARIANTS.md`](GOVERNANCE_INVARIANTS.md) | Cross-artifact governance invariants |

### Session and artifact pipeline

| Document | Purpose |
| --- | --- |
| [`docs/AGENTS.md`](AGENTS.md) | Agent profiles |
| [`docs/TARGETS.md`](TARGETS.md) | Target profiles |
| [`docs/PROFILE_RESOLUTION.md`](PROFILE_RESOLUTION.md) | Profile Resolution |
| [`docs/PROFILE_PACKS.md`](PROFILE_PACKS.md) | Profile packs |
| [`docs/REPO_MAPS.md`](REPO_MAPS.md) | Bounded Repository Maps |
| [`docs/CONTEXT_PACKS.md`](CONTEXT_PACKS.md) | Bounded Context Packs |
| [`docs/TARGET_BUNDLES.md`](TARGET_BUNDLES.md) | Target bundle artifacts |
| [`docs/GOVERNED_PREPARE_PACKAGE.md`](GOVERNED_PREPARE_PACKAGE.md) | Governed Prepare Package |
| [`docs/GOVERNED_SESSION_BOOTSTRAP.md`](GOVERNED_SESSION_BOOTSTRAP.md) | Governed Session Bootstrap |
| [`docs/PREPARE_PACKAGE_SUMMARY.md`](PREPARE_PACKAGE_SUMMARY.md) | Prepare Package Summary |
| [`docs/VALIDATE_PREPARE_PACKAGE.md`](VALIDATE_PREPARE_PACKAGE.md) | Validate Prepare Package |
| [`docs/CONVENTION_LAYER_KERNEL.md`](CONVENTION_LAYER_KERNEL.md) | Convention Layer Kernel |
| [`docs/SESSION_WORKFLOW.md`](SESSION_WORKFLOW.md) | Governed Local Session Workflow |
| [`docs/ORCHESTRATION_ASSIGNMENT.md`](ORCHESTRATION_ASSIGNMENT.md) | Orchestration Assignment |
| [`docs/ORCHESTRATION_OBLIGATIONS.md`](ORCHESTRATION_OBLIGATIONS.md) | Orchestration Obligations (Law 1 Tickets) |
| [`docs/STATE_LEDGER.md`](STATE_LEDGER.md) | State ledger |
| [`docs/ARTIFACT_INDEX.md`](ARTIFACT_INDEX.md) | Artifact index |
| [`docs/ARTIFACT_CHAIN_VERIFICATION.md`](ARTIFACT_CHAIN_VERIFICATION.md) | Artifact Chain Verification |
| [`docs/ARTIFACT_MEMORY.md`](ARTIFACT_MEMORY.md) | Artifact Memory |
| [`docs/HANDOFF_ARTIFACTS.md`](HANDOFF_ARTIFACTS.md) | Handoff artifacts |
| [`docs/HANDOFF_BUNDLES.md`](HANDOFF_BUNDLES.md) | Handoff bundles |
| [`docs/HANDOFF_NOTES.md`](HANDOFF_NOTES.md) | Governed Handoff Notes |
| [`docs/HANDOFF_SUMMARIES.md`](HANDOFF_SUMMARIES.md) | Handoff summaries |
| [`docs/READONLY_INSPECTION_PROMOTION.md`](READONLY_INSPECTION_PROMOTION.md) | Read-Only Inspection Promotion |
| [`docs/READONLY_INSPECTION_REPORTS.md`](READONLY_INSPECTION_REPORTS.md) | Read-only inspection reports |
| [`docs/STACKED_NOTES_READONLY_INSPECTION.md`](STACKED_NOTES_READONLY_INSPECTION.md) | Stacked PR note: read-only inspection boundary |
| [`docs/TUI_INSPECTION_SURFACE.md`](TUI_INSPECTION_SURFACE.md) | TUI Inspection Surface |
| [`docs/STRATUM.md`](STRATUM.md) | STRATUM operator console — first-session walkthrough, keymap, boundaries |

### HITL governance chain

| Document | Purpose |
| --- | --- |
| [`docs/HITL_CHAIN_BINDING.md`](HITL_CHAIN_BINDING.md) | HITL Chain Binding |
| [`docs/HITL_COMMAND_EXECUTION.md`](HITL_COMMAND_EXECUTION.md) | HITL Command Execution Specification |
| [`docs/HITL_EVIDENCE_BUNDLE.md`](HITL_EVIDENCE_BUNDLE.md) | Human-in-the-Loop (HITL) Execution Evidence Bundle |
| [`docs/HITL_EXECUTION_CLI.md`](HITL_EXECUTION_CLI.md) | HITL Execution Artifact CLI (`builder-hitl`) |
| [`docs/HITL_EXECUTION_RECORDS.md`](HITL_EXECUTION_RECORDS.md) | HITL Execution Request & Receipt Records |
| [`docs/HITL_PATCH_APPLY.md`](HITL_PATCH_APPLY.md) | HITL Patch Apply |
| [`docs/HITL_PATCH_PROPOSAL.md`](HITL_PATCH_PROPOSAL.md) | HITL Patch Application Specification |
| [`docs/HITL_PROMOTION_ARTIFACTS.md`](HITL_PROMOTION_ARTIFACTS.md) | HITL Promotion Bridge Artifacts |
| [`docs/HITL_VERIFICATION_CANDIDATE.md`](HITL_VERIFICATION_CANDIDATE.md) | HITL Verification Execution Candidate |
| [`docs/EXECUTION_POSTFLIGHT_RECORDS.md`](EXECUTION_POSTFLIGHT_RECORDS.md) | Execution Postflight and Verification Records |
| [`docs/EXECUTION_PROTOCOL.md`](EXECUTION_PROTOCOL.md) | ⚔️ The Execution Protocol |
| [`docs/APPROVAL_RECORDS.md`](APPROVAL_RECORDS.md) | Approval records |
| [`docs/PREFLIGHT_RECORDS.md`](PREFLIGHT_RECORDS.md) | Preflight records |
| [`docs/RECEIPT_RECORDS.md`](RECEIPT_RECORDS.md) | Receipt records |
| [`docs/INTAKE_RECORDS.md`](INTAKE_RECORDS.md) | Intake records |
| [`docs/ROLLBACK_ARTIFACTS.md`](ROLLBACK_ARTIFACTS.md) | Rollback Artifacts |

### Verification and quality

| Document | Purpose |
| --- | --- |
| [`docs/VERIFICATION_PROFILES.md`](VERIFICATION_PROFILES.md) | Verification profiles |
| [`docs/VERIFICATION_PROFILE_REPORTS.md`](VERIFICATION_PROFILE_REPORTS.md) | Verification Profile Reports |
| [`docs/QUALITY_GATES.md`](QUALITY_GATES.md) | Quality gate artifacts |
| [`docs/RESEARCH_PLANS.md`](RESEARCH_PLANS.md) | Research planning artifacts |
| [`docs/RESEARCH_ADAPTERS.md`](RESEARCH_ADAPTERS.md) | Research adapter artifacts |

### Goose adapter

| Document | Purpose |
| --- | --- |
| [`docs/GOOSE_CONVENTION_LAYER.md`](GOOSE_CONVENTION_LAYER.md) | Codename Goose Convention Layer |
| [`docs/GOOSE_RUNTIME.md`](GOOSE_RUNTIME.md) | Goose runtime design spec |
| [`docs/GOOSE_SESSION.md`](GOOSE_SESSION.md) | Goose session manifests |
| [`docs/GOOSE_READONLY.md`](GOOSE_READONLY.md) | Goose read-only runtime candidate |
| [`docs/GOOSE_READONLY_SESSION.md`](GOOSE_READONLY_SESSION.md) | Goose Governed Read-Only Session Plan |
| [`docs/GOOSE_INSPECTION.md`](GOOSE_INSPECTION.md) | Goose bounded read-only inspection |
| [`docs/GOOSE_COMMAND_PROPOSALS.md`](GOOSE_COMMAND_PROPOSALS.md) | Goose command proposal artifacts |

### deepagents adapter

| Document | Purpose |
| --- | --- |
| [`docs/DEEPAGENTS_POLICY.md`](DEEPAGENTS_POLICY.md) | Governed deepagents policy artifacts |
| [`docs/DEEPAGENTS_READINESS.md`](DEEPAGENTS_READINESS.md) | Deepagents dependency-readiness artifacts |
| [`docs/DEEPAGENTS_BRIDGE_READINESS.md`](DEEPAGENTS_BRIDGE_READINESS.md) | DeepAgents Bridge Readiness |
| [`docs/DEEPAGENTS_RUNTIME.md`](DEEPAGENTS_RUNTIME.md) | Deepagents Runtime Harness |
| [`docs/DEEPAGENTS_FORGE.md`](DEEPAGENTS_FORGE.md) | deepagents Forge |
| [`docs/DEEPAGENTS_WORK_ARTIFACTS.md`](DEEPAGENTS_WORK_ARTIFACTS.md) | Deepagents Work Artifacts |
| [`docs/ORCHESTRATION_OBLIGATIONS.md`](ORCHESTRATION_OBLIGATIONS.md) | Governed obligation delegation (Ladder 4) |
| [`docs/BRIDGE.md`](BRIDGE.md) | deepagents bridge |

### CodeVault (Commercial Extension)

The CodeVault engine has been cleanly separated from open core to a commercial paid plugin (`builder-ii-code-vault`) to provide advanced hierarchical frames, exact geometric/structural recall, polyglot extractor substrates, and exact-recall analysis. The open-source CLI command (`builder-code-vault`) functions as a fail-closed seam that informs the operator of the separation and guides them on how to upgrade. 

To inquire about acquiring the CodeVault commercial plugin, please reach out to the maintainers to ask about it.

The following architectural and design documents reside in the commercial plugin repository:

* `docs/CODE_VAULT.md` — CodeVault operator overview & vision-set index
* `docs/CODE_VAULT_BACKENDS.md` — CodeVault recall backends
* `docs/CODE_VAULT_CGA_ENTITIES.md` — CodeVault CGA entities
* `docs/CODE_VAULT_CONTEXT_PACKS.md` — CodeVault context projection
* `docs/CODE_VAULT_FINDINGS.md` — CodeVault hypothesis findings
* `docs/CODE_VAULT_GEOMETRIC_ONTOLOGY.md` — CodeVault geometric ontology
* `docs/CODE_VAULT_HIERARCHY.md` — CodeVault hierarchical frame
* `docs/CODE_VAULT_STAGED_ACCEPTANCE.md` — CodeVault staged acceptance ledger
* `docs/CODE_VAULT_VISION_AND_CAPABILITY_LADDER.md` — Vision, axioms, capability ladder, fruition bar
* `docs/CODE_VAULT_GLOSSARY.md` — Vocabulary lock
* `docs/CODE_VAULT_PROOF_PROGRAM.md` — Proof classes R / D / U and Axiom Zero
* `docs/CODE_VAULT_LANGUAGE_SUBSTRATE.md` — Polyglot substrate: Artifact IR + grade doctrine + extractors
* `docs/CODE_VAULT_FIELD_BLUEPRINTS.md` — Dual-correction blueprints for fields F0–F6
* `docs/CODE_VAULT_ROADMAP.md` — Gate-ordered roadmap (no chronos)
* `docs/CODE_VAULT_GATE_STATE.md` — Gate-state ledger: which roadmap bullets hold, and which gates are therefore closed
* `docs/CODE_VAULT_CURRENT_STATE_AND_GAP_MAP.md` — Three-clock truth delta
* `docs/architecture/CODE_VAULT_TIER1_ENCODER.md` — F1 encoder RFC and measurement history
* `docs/adrs/ADR-0005-codevault-boundary-and-authority.md` — CodeVault boundary and authority ADR


### Models, lanes, and personas

| Document | Purpose |
| --- | --- |
| [`docs/model_role_matrix.md`](model_role_matrix.md) | Model role matrix |
| [`docs/model_operating_policy.md`](model_operating_policy.md) | Model operating policy |
| [`docs/lane_guides.md`](lane_guides.md) | Lane guides |
| [`docs/lane_checks.md`](lane_checks.md) | Offline lane checks |
| [`docs/personas.md`](personas.md) | Personas |
| [`docs/role_gates.md`](role_gates.md) | Role capability gates |
| [`docs/direct_ask.md`](direct_ask.md) | Direct local ask lane |
| [`docs/VOICE_IO_POLICY.md`](VOICE_IO_POLICY.md) | Voice I/O Policy |

### Truth, status, and audits

| Document | Purpose |
| --- | --- |
| [`docs/PLATFORM_COMPLETION_AUDIT.md`](PLATFORM_COMPLETION_AUDIT.md) | Platform Completion Audit |
| [`docs/PLATFORM_SNAPSHOT.md`](PLATFORM_SNAPSHOT.md) | Platform snapshot |
| [`docs/BUILDER_II_COMPLETION_TRUTH_REPORT.md`](BUILDER_II_COMPLETION_TRUTH_REPORT.md) | builder-II Completion Truth Report + Master Completion Plan |
| [`docs/BUILDER_PLATFORM_RELEASE_AUDIT.md`](BUILDER_PLATFORM_RELEASE_AUDIT.md) | builder-II Platform Release Audit |
| [`docs/RUNTIME_GOVERNANCE_RELEASE_AUDIT.md`](RUNTIME_GOVERNANCE_RELEASE_AUDIT.md) | Runtime Governance Release Audit |
| [`docs/FOUNDATION_STATUS.md`](FOUNDATION_STATUS.md) | Foundation Status |
| [`docs/RELEASE_PROOF.md`](RELEASE_PROOF.md) | Builder-II V0 Release Proof Harness |
| [`docs/PERFORMANCE_MEASUREMENTS.md`](PERFORMANCE_MEASUREMENTS.md) | Performance measurement records |
| [`docs/audits/B1_3C_RUNNER_HARDENING_AUDIT.md`](audits/B1_3C_RUNNER_HARDENING_AUDIT.md) | B1.3C Runner Hardening Audit |
| [`docs/audits/B1_4A_PASSIVE_EXECUTION_LEDGER.md`](audits/B1_4A_PASSIVE_EXECUTION_LEDGER.md) | B1.4A Passive Execution Ledger Scope |
| [`docs/audits/B1_4B_READONLY_LEDGER_QUERIES.md`](audits/B1_4B_READONLY_LEDGER_QUERIES.md) | B1.4B Read-Only Verification Ledger Queries |
| [`docs/audits/B1_4C_PASSIVE_LEDGER_INTEGRITY.md`](audits/B1_4C_PASSIVE_LEDGER_INTEGRITY.md) | B1.4C Passive Verification Ledger Integrity |
| [`docs/audits/B1_4D_LEDGER_RECONSTRUCTION.md`](audits/B1_4D_LEDGER_RECONSTRUCTION.md) | B1.4D Passive Ledger Reconstruction |
| [`docs/audits/B1_B2_RUNTIME_GOVERNANCE_COMPLETION_MAP.md`](audits/B1_B2_RUNTIME_GOVERNANCE_COMPLETION_MAP.md) | B1/B2 Runtime Governance Completion Map |
| [`docs/audits/B1_CLOSURE_AUDIT.md`](audits/B1_CLOSURE_AUDIT.md) | B1 Closure Audit |

### Beta

| Document | Purpose |
| --- | --- |
| [`docs/BETA_CHARTER.md`](BETA_CHARTER.md) | Beta Charter |

### Promotions (transition runbooks)

Readiness checklists for capability promotions gated on operator approval. All five are currently
**Pending Approval** — none of these transitions have happened.

| Document | Purpose |
| --- | --- |
| [`docs/promotions/public_cut_over.md`](promotions/public_cut_over.md) | Public / open-source cut-over readiness checklist (`BUILDER-II-TRK-B4`) |
| [`docs/promotions/deepagent_native.md`](promotions/deepagent_native.md) | DeepAgent native backends transition runbook (`BUILDER-II-TRK-B3`) |
| [`docs/promotions/s3_multi_agent.md`](promotions/s3_multi_agent.md) | S3 dynamic multi-agent orchestration transition runbook (`BUILDER-II-TRK-B1`) |
| [`docs/promotions/telemetry_monitoring.md`](promotions/telemetry_monitoring.md) | Telemetry & monitoring backend transition runbook (`BUILDER-II-TRK-B5`) |
| [`docs/promotions/vllm_backend.md`](promotions/vllm_backend.md) | vLLM backend promotion transition runbook (`BUILDER-II-TRK-B2`) |

### Design notes, RFCs, and plans

| Document | Purpose |
| --- | --- |
| [`docs/architecture/CORE_WORKBENCH_BOUNDARY.md`](architecture/CORE_WORKBENCH_BOUNDARY.md) | V.5 CORE Workbench boundary (builder-II helps code, is not Workbench) |
| [`docs/WRP_CONTROL_PLANE.md`](WRP_ABSOLUTE_MASTERY_SYNTHESIS.md) | WRP/Vision absolute mastery synthesis (planning+evidence+smoke; not S3/S4 flip) |
| [`docs/architecture/MCP_POLICY_CONTRACT.md`](architecture/MCP_POLICY_CONTRACT.md) | MCP policy artifact contract |
| [`docs/architecture/MCP_TOOL_INVENTORY_CONTRACT.md`](architecture/MCP_TOOL_INVENTORY_CONTRACT.md) | MCP tool inventory contract |
| [`docs/architecture/GOVERNED_RUN_LIFECYCLE.md`](architecture/GOVERNED_RUN_LIFECYCLE.md) | Plan Set 1 governed-run lifecycle and runtime-adapter seam |

### Process and tooling

| Document | Purpose |
| --- | --- |
| [`docs/TOOLING.md`](TOOLING.md) | External tooling |
| [`docs/BRANCH_PROTECTION_REQUIRED.md`](BRANCH_PROTECTION_REQUIRED.md) | Local Merge Verification Policy |
| [`docs/BRIEF_ALPHA.md`](BRIEF_ALPHA.md) | BRIEF ALPHA: GEMINI-3.1-PRO (High Compute) |
| [`docs/BRIEF_BETA.md`](BRIEF_BETA.md) | BRIEF BETA: GEMINI-3.5-FLASH (High Context) |

## Keeping this index honest

This table is generated from `docs/**/*.md`'s first-level (`# `) heading, grouped by subsystem.
When adding a new doc under `docs/`, add its row here in the matching (or a new) section — a
missing entry is a broken funnel, not a cosmetic gap. There is no automated check for this yet;
treat it as a review-time convention until one exists.
