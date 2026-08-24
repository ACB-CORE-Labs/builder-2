# builder-II Documentation Index

This is the comprehensive reference index for all documentation under `docs/`.

---

## Documentation Navigation Paths

```text
┌───────────────────────────────────────┐
│ 1. "I want to try it in 60 seconds"   │ ──► QUICKSTART.md
└───────────────────────────────────────┘
┌───────────────────────────────────────┐
│ 2. "I want a guided first session"    │ ──► FIRST_SESSION.md
└───────────────────────────────────────┘
┌───────────────────────────────────────┐
│ 3. "I want to understand the paradigm"│ ──► docs/MANIFESTO.md + docs/PROJECT_OVERVIEW.md
└───────────────────────────────────────┘
┌───────────────────────────────────────┐
│ 4. "I want to operate it day-to-day"  │ ──► docs/GETTING_STARTED.md + docs/OPERATOR_GUIDE.md
└───────────────────────────────────────┘
┌───────────────────────────────────────┐
│ 5. "I need exact technical truth"     │ ──► docs/COMMAND_AUTHORITY.md + Platform Matrix
└───────────────────────────────────────┘
```

---

## 1. Understand builder-II

Foundational philosophy, engineering pillars, and core system boundaries.

| Document | Description |
| :--- | :--- |
| [`docs/MANIFESTO.md`](MANIFESTO.md) | The Builder's Signet: Mechanical Sympathy, Semantic Rigor, The Third Door |
| [`docs/PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md) | Platform identity, subsystem boundaries, and architecture guardrails |
| [`docs/GLOSSARY.md`](GLOSSARY.md) | Centralized definitions for kinds, spines, authority tiers, and assurance states |
| [`docs/HONESTY_PINS_VS_IMPLEMENTATION.md`](HONESTY_PINS_VS_IMPLEMENTATION.md) | Doctrine: Honesty pins reject false claims; they do not ban implementation |
| [`docs/adrs/README.md`](adrs/README.md) | Architecture Decision Records (ADRs) index |
| [`docs/adrs/ADR-0001-core-builder-ii-governed-engineering-extension.md`](adrs/ADR-0001-core-builder-ii-governed-engineering-extension.md) | ADR-0001: builder-II as a Governed Engineering Extension |
| [`docs/adrs/ADR-0002-builder-convention-layer-over-codename-goose.md`](adrs/ADR-0002-builder-convention-layer-over-codename-goose.md) | ADR-0002: Builder Convention Layer over Codename Goose |
| [`docs/adrs/ADR-0003-builder-ii-generic-platform-identity-and-capability-factory.md`](adrs/ADR-0003-builder-ii-generic-platform-identity-and-capability-factory.md) | ADR-0003: Generic Platform Identity & Capability Factory |
| [`docs/adrs/ADR-0004-core-born-builders-signet-doctrine.md`](adrs/ADR-0004-core-born-builders-signet-doctrine.md) | ADR-0004: CORE-Born Builder's Signet Doctrine |

---

## 2. Install and Start

Setup instructions, environment configuration, and quickstart paths.

| Document | Description |
| :--- | :--- |
| [`QUICKSTART.md`](../QUICKSTART.md) | 60-second mechanical setup for macOS Apple Silicon and Linux |
| [`FIRST_SESSION.md`](../FIRST_SESSION.md) | 30-minute clone-to-patch walkthrough with interactive receipts |
| [`docs/GETTING_STARTED.md`](GETTING_STARTED.md) | Comprehensive onboarding guide: setup order, mental model, and STRATUM overview |
| [`docs/CONFIG_ONBOARDING.md`](CONFIG_ONBOARDING.md) | Configuration precedence, `.env` schema, and setup wizard mechanics |
| [`docs/RATIFICATION_GRANTS.md`](RATIFICATION_GRANTS.md) | Standing ratification grants: delegable confirmations vs ungrantable decisions |

---

## 3. Daily Operator Workflows

Day-to-day operations, recipe execution, STRATUM navigation, and session packages.

| Document | Description |
| :--- | :--- |
| [`docs/OPERATOR_GUIDE.md`](OPERATOR_GUIDE.md) | Daily operator workflows, recipe structures, and validation boundaries |
| [`docs/OPERATOR_QUICKSTART.md`](OPERATOR_QUICKSTART.md) | Operator golden path commands (`operator-status`, `next`, `golden-path`) |
| [`docs/OPERATOR_PLAYBOOK.md`](OPERATOR_PLAYBOOK.md) | Playbook for session management and error recovery |
| [`docs/STRATUM.md`](STRATUM.md) | STRATUM TUI reference: keymaps, flags, spatial instruments, and composer |
| [`docs/MAXIMIZING_PROFICIENCY.md`](MAXIMIZING_PROFICIENCY.md) | Advanced operator guide for multi-agent workflows and debugging |
| [`docs/manual.md`](manual.md) | Command manual and platform interface reference |
| [`docs/CORE_DEMO_WALKTHROUGH.md`](CORE_DEMO_WALKTHROUGH.md) | Governed demo walkthrough script with temporary worktree isolation |
| [`docs/demos/FLAGSHIP_DEMO_SCRIPT.md`](demos/FLAGSHIP_DEMO_SCRIPT.md) | 15-minute flagship demo script with live tamper-detection beat |

---

## 4. Governance, Authority, and Assurance

Authority tiers, human-in-the-loop gates, promotion ladders, and invariants.

| Document | Description |
| :--- | :--- |
| [`docs/COMMAND_AUTHORITY.md`](COMMAND_AUTHORITY.md) | Authoritative command authority registry and tier definitions (Tiers 0–5) |
| [`docs/CAPABILITY_PROMOTION.md`](CAPABILITY_PROMOTION.md) | 8-state capability promotion ladder and the Eight Promotion Gates |
| [`docs/KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) | Verbatim non-operational capabilities and recorded blockers from the truth matrix |
| [`docs/GOVERNANCE_INVARIANTS.md`](GOVERNANCE_INVARIANTS.md) | Cross-artifact governance invariants and fail-closed validation rules |
| [`docs/PROMOTION_READINESS.md`](PROMOTION_READINESS.md) | Promotion readiness criteria and evidence verification |
| [`docs/PROMOTION_DECISIONS.md`](PROMOTION_DECISIONS.md) | Promotion decision artifact specifications |
| [`docs/RUNTIME_PROMOTION.md`](RUNTIME_PROMOTION.md) | Runtime-specific promotion contracts for adapters |
| [`docs/capability_gates.md`](capability_gates.md) | Capability gates definition |
| [`docs/COMMAND_SURFACE_AUDIT.md`](COMMAND_SURFACE_AUDIT.md) | Audit of CLI entry points against authority tiers |

---

## 5. Models, Agents, Runtimes, and Tools

Model gateways, routing policy (WRP), agent profiles, Goose, Deep Agents, and MCP.

| Document | Description |
| :--- | :--- |
| [`docs/model_role_matrix.md`](model_role_matrix.md) | Recommended model aliases, roles, footprints, and avoid boundaries |
| [`docs/MODEL_COSTING.md`](MODEL_COSTING.md) | Model execution gateway costing, token accounting, and budget successor rules |
| [`docs/model_operating_policy.md`](model_operating_policy.md) | Model invocation policies and local-first execution constraints |
| [`docs/AGENTS.md`](AGENTS.md) | Generic agent profiles and authority envelopes |
| [`docs/GOOSE_CONVENTION_LAYER.md`](GOOSE_CONVENTION_LAYER.md) | Goose runtime convention layer and recipe projections |
| [`docs/GOOSE_SESSION.md`](GOOSE_SESSION.md) | Goose session manifest contracts |
| [`docs/GOOSE_READONLY.md`](GOOSE_READONLY.md) | Governed Goose read-only runtime specification |
| [`docs/GOOSE_RUNTIME.md`](GOOSE_RUNTIME.md) | Goose runtime promotion requirements and boundaries |
| [`docs/DEEPAGENTS_FORGE.md`](DEEPAGENTS_FORGE.md) | Deep Agents Forge: interactive agent specification wizard |
| [`docs/DEEPAGENTS_POLICY.md`](DEEPAGENTS_POLICY.md) | Deep Agents governance policy and isolation envelopes |
| [`docs/DEEPAGENTS_RUNTIME.md`](DEEPAGENTS_RUNTIME.md) | Deep Agents runtime harness and protocol_fake execution lane |
| [`docs/DEEPAGENTS_WORK_ARTIFACTS.md`](DEEPAGENTS_WORK_ARTIFACTS.md) | Work artifact specifications for subagent tasks |
| [`docs/ORCHESTRATION_OBLIGATIONS.md`](ORCHESTRATION_OBLIGATIONS.md) | Governed obligation delegation and contract satisfaction (Ladder 4) |
| [`docs/TOOLING.md`](TOOLING.md) | Local and external tool registry index |

---

## 6. Verification, Mutation, Rollback, and Delivery

Artifact pipelines, bounded test runners, patch applications, rollback mechanics, and Git delivery.

| Document | Description |
| :--- | :--- |
| [`docs/HITL_PATCH_PROPOSAL.md`](HITL_PATCH_PROPOSAL.md) | Patch proposal artifact specification |
| [`docs/HITL_PATCH_APPLY.md`](HITL_PATCH_APPLY.md) | Governed patch application with preflight snapshots and reverse patches |
| [`docs/ROLLBACK_ARTIFACTS.md`](ROLLBACK_ARTIFACTS.md) | Reversible mutations, rollback plans, and drift detection |
| [`docs/VERIFICATION_PROFILES.md`](VERIFICATION_PROFILES.md) | Target-scoped verification profiles (`platform_status`, `docs_audit`, `pytest_full`) |
| [`docs/HITL_COMMAND_EXECUTION.md`](HITL_COMMAND_EXECUTION.md) | Bounded command execution specification |
| [`docs/HITL_EVIDENCE_BUNDLE.md`](HITL_EVIDENCE_BUNDLE.md) | Evidence bundle composition and verification binding |
| [`docs/HITL_EXECUTION_RECORDS.md`](HITL_EXECUTION_RECORDS.md) | Request and receipt record specifications |
| [`docs/EXECUTION_POSTFLIGHT_RECORDS.md`](EXECUTION_POSTFLIGHT_RECORDS.md) | Preflight vs postflight git fingerprint validation |
| [`docs/ARTIFACT_CHAIN_VERIFICATION.md`](ARTIFACT_CHAIN_VERIFICATION.md) | Cryptographic SHA-256 chain verification mechanics |
| [`docs/ARTIFACT_INDEX.md`](ARTIFACT_INDEX.md) | Complete registry of all recognized JSON artifact kinds |
| [`docs/ARTIFACT_MEMORY.md`](ARTIFACT_MEMORY.md) | Content-addressed, reviewable artifact memory atoms |
| [`docs/HANDOFF_NOTES.md`](HANDOFF_NOTES.md) | Cross-session handoff notes and context preservation |

---

## 7. Extension and Integration Architecture

CodeVault commercial plugin seam, target profiles, and context packs.

| Document | Description |
| :--- | :--- |
| [`docs/TARGETS.md`](TARGETS.md) | Target repository profiles (`generic`, `builder`, `core`) |
| [`docs/CONTEXT_PACKS.md`](CONTEXT_PACKS.md) | Bounded context pack generation |
| [`docs/REPO_MAPS.md`](REPO_MAPS.md) | Deterministic repository mapping |
| [`docs/PROFILE_PACKS.md`](PROFILE_PACKS.md) | Profile pack composition and dry-run rendering |
| `builder_ii/cli/code_vault_cli.py` | CodeVault commercial plugin CLI seam (fail-closed upgrade guidance) |
| [`docs/demos/CODE_VAULT_DETERMINISM_DEMO.md`](demos/CODE_VAULT_DETERMINISM_DEMO.md) | CodeVault determinism demo walkthrough (Commercial Plugin) |

---

## 8. Release, Security, and Quality Gates

Release proofs, security policies, and quality validation.

| Document | Description |
| :--- | :--- |
| [`SECURITY.md`](../SECURITY.md) | Security policy, vulnerability reporting, and non-sandbox threat model |
| [`CONTRIBUTING.md`](../CONTRIBUTING.md) | Development setup, canonical local CI gates, and pull request workflow |
| [`CHANGELOG.md`](../CHANGELOG.md) | Version history and provenance |
| [`docs/RELEASE_PROOF.md`](RELEASE_PROOF.md) | Structural artifact and governance release proof harness |
| [`docs/QUALITY_GATES.md`](QUALITY_GATES.md) | Quality gate planning and merge blocker records |
| [`docs/BRANCH_PROTECTION_REQUIRED.md`](BRANCH_PROTECTION_REQUIRED.md) | Branch protection and CI gate requirements |

---

## 9. Reference

Detailed API specifications, personas, lane guides, and registries.

| Document | Description |
| :--- | :--- |
| [`docs/OPERATOR_COMMAND_SURFACE.md`](OPERATOR_COMMAND_SURFACE.md) | Canonical index of all operator CLI commands |
| [`docs/personas.md`](personas.md) | Standard system personas and prompt definitions |
| [`docs/role_gates.md`](role_gates.md) | Role capability gates |
| [`docs/lane_guides.md`](lane_guides.md) | Reusable prompt lanes for direct ask and planning |
| [`docs/lane_checks.md`](lane_checks.md) | Offline consistency checks for lane wiring |
| [`docs/direct_ask.md`](direct_ask.md) | Direct model ask interface |
| [`docs/ROADMAP.md`](ROADMAP.md) | Platform roadmap and milestone sequence |
| [`docs/BETA_CHARTER.md`](BETA_CHARTER.md) | Beta feedback charter and scope |

---

## 10. Historical Plans, Audits, and Evidence

> [!NOTE]
> **Historical Provenance Archive:**
> The documents below are preserved historical milestones, closure audits, design RFCs, and transition runbooks. They provide immutable evidence of platform evolution and are retained for cryptographic provenance. For current operational guidance, refer to Sections 1–9.

<details>
<summary><b>Expand Historical Closure Audits & Evidence (Click to view)</b></summary>

### Closure Audits
- [`docs/audits/B1_CLOSURE_AUDIT.md`](audits/B1_CLOSURE_AUDIT.md) — B1 Milestone Closure Audit
- [`docs/audits/B4_CLOSURE_AUDIT.md`](audits/B4_CLOSURE_AUDIT.md) — B4 HITL Patch Application Closure Audit
- [`docs/audits/B4_9_DEMO_GENERALIZATION_AUDIT.md`](audits/B4_9_DEMO_GENERALIZATION_AUDIT.md) — B4.9 Demo Generalization Audit
- [`docs/audits/LADDER4_ORCHESTRATION_CLOSURE_AUDIT.md`](audits/LADDER4_ORCHESTRATION_CLOSURE_AUDIT.md) — Ladder 4 Orchestration Closure Audit
- [`docs/audits/LADDER9_ASSURANCE_CLOSURE_AUDIT.md`](audits/LADDER9_ASSURANCE_CLOSURE_AUDIT.md) — Ladder 9 Assurance Closure Audit
- [`docs/audits/R1_CLOSURE_AUDIT_2_6.md`](audits/R1_CLOSURE_AUDIT_2_6.md) — R1 Config & Onboarding Closure Audit
- [`docs/audits/B1_3C_RUNNER_HARDENING_AUDIT.md`](audits/B1_3C_RUNNER_HARDENING_AUDIT.md) — B1.3C Runner Hardening Audit
- [`docs/audits/B1_4A_PASSIVE_EXECUTION_LEDGER.md`](audits/B1_4A_PASSIVE_EXECUTION_LEDGER.md) — B1.4A Passive Execution Ledger Audit
- [`docs/audits/B1_4B_READONLY_LEDGER_QUERIES.md`](audits/B1_4B_READONLY_LEDGER_QUERIES.md) — B1.4B Read-Only Ledger Query Audit
- [`docs/audits/B1_4C_PASSIVE_LEDGER_INTEGRITY.md`](audits/B1_4C_PASSIVE_LEDGER_INTEGRITY.md) — B1.4C Passive Ledger Integrity Audit
- [`docs/audits/B1_4D_LEDGER_RECONSTRUCTION.md`](audits/B1_4D_LEDGER_RECONSTRUCTION.md) — B1.4D Ledger Reconstruction Audit
- [`docs/audits/B1_B2_RUNTIME_GOVERNANCE_COMPLETION_MAP.md`](audits/B1_B2_RUNTIME_GOVERNANCE_COMPLETION_MAP.md) — B1/B2 Governance Map
- [`docs/PLATFORM_COMPLETION_AUDIT.md`](PLATFORM_COMPLETION_AUDIT.md) — Historical Completion Truth Matrix Mirror
- [`docs/BUILDER_II_COMPLETION_TRUTH_REPORT.md`](BUILDER_II_COMPLETION_TRUTH_REPORT.md) — Master Completion Truth Report
- [`docs/FOUNDATION_STATUS.md`](FOUNDATION_STATUS.md) — Foundation Status & R0->R1->B1 Sequence

### Historical RFCs & Design Plans
- [`docs/plan/MASTERPIECE_PLAN.md`](plan/MASTERPIECE_PLAN.md) — Masterpiece Implementation Plan
- [`docs/plan/B8_B9_GOVERNED_EXECUTION_PLAN.md`](plan/B8_B9_GOVERNED_EXECUTION_PLAN.md) — B8/B9 Governed Execution Plan
- [`docs/plan/MCP_POLICY_ARTIFACT_RFC.md`](plan/MCP_POLICY_ARTIFACT_RFC.md) — MCP Policy Artifact RFC
- [`docs/plan/MCP_TOOL_INVENTORY_RFC.md`](plan/MCP_TOOL_INVENTORY_RFC.md) — MCP Tool Inventory RFC
- [`docs/plan/ORCHESTRATION_OBLIGATIONS_RFC.md`](plan/ORCHESTRATION_OBLIGATIONS_RFC.md) — Orchestration Obligations RFC
- [`docs/plan/PASSIVE_EXECUTION_CANDIDATE_MANIFEST_RFC.md`](plan/PASSIVE_EXECUTION_CANDIDATE_MANIFEST_RFC.md) — Execution Candidate Manifest RFC
- [`docs/plan/PASSIVE_HITL_PROMOTION_BRIDGE_RFC.md`](plan/PASSIVE_HITL_PROMOTION_BRIDGE_RFC.md) — HITL Promotion Bridge RFC
- [`docs/plan/VERIFICATION_ISOLATION_RFC.md`](plan/VERIFICATION_ISOLATION_RFC.md) — Verification Isolation RFC
- [`docs/plan/ARTIFACT_MEMORY_RFC.md`](plan/ARTIFACT_MEMORY_RFC.md) — Artifact Memory RFC
- [`docs/plan/PR_203_DEEPAGENTS_FORGE_EXECUTION_PLAN.md`](plan/PR_203_DEEPAGENTS_FORGE_EXECUTION_PLAN.md) — Deep Agents Forge Plan
- [`docs/plan/GOOSE_DEEPAGENTS_MCP_SEAM.md`](plan/GOOSE_DEEPAGENTS_MCP_SEAM.md) — Goose × Deep Agents × MCP Seam Design
- [`docs/plan/CORE_WORKBENCH_BOUNDARY.md`](plan/CORE_WORKBENCH_BOUNDARY.md) — CORE Workbench Boundary Design

### Transition Runbooks (Pending Execution)
- [`docs/promotions/public_cut_over.md`](promotions/public_cut_over.md) — Public Cut-Over Readiness Checklist
- [`docs/promotions/deepagent_native.md`](promotions/deepagent_native.md) — DeepAgent Native Backends Transition Runbook
- [`docs/promotions/s3_multi_agent.md`](promotions/s3_multi_agent.md) — S3 Multi-Agent Orchestration Runbook
- [`docs/promotions/telemetry_monitoring.md`](promotions/telemetry_monitoring.md) — Telemetry Monitoring Runbook
- [`docs/promotions/vllm_backend.md`](promotions/vllm_backend.md) — vLLM Backend Promotion Runbook

</details>

