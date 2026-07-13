# builder-II roadmap

builder-II is a generic governed platform for local agent-assisted software development.

It is CORE-born and carries CORE's engineering signet, but it is not the CORE runtime, not CORE Workbench/UI, and not a second CORE runtime. CORE is supported as a first-class target profile and lineage context; builder-II remains generic-first in architecture.

The governing product doctrine is captured in [`docs/MANIFESTO.md`](MANIFESTO.md), [`docs/adrs/ADR-0001-core-builder-ii-governed-engineering-extension.md`](adrs/ADR-0001-core-builder-ii-governed-engineering-extension.md), [`docs/adrs/ADR-0002-builder-convention-layer-over-codename-goose.md`](adrs/ADR-0002-builder-convention-layer-over-codename-goose.md), and [`docs/adrs/ADR-0003-builder-ii-generic-platform-identity-and-capability-factory.md`](adrs/ADR-0003-builder-ii-generic-platform-identity-and-capability-factory.md).

Repository docs, schemas, tests, command registries, and source code are the authoritative project record. Notion planning artifacts are supportive planning material unless reconciled back into the repository.

## Current status - v0 passive governed artifact platform (as of 2026-06-30)

builder-II has a source-backed passive v0 artifact proof harness (`scripts/verify_v0_release.py`). The platform truth state is maintained by `builder-platform matrix`, `builder-platform status`, and `builder-platform audit-docs`.

Current truth summary:

- passive foundation state: `PASSIVE_FOUNDATION`
- operational runtime capability state: not `OPERATIONALLY_VERIFIED`
- setup/config kernel state: present in the matrix and non-operational until R1
- next sequence: `R0 -> R1 -> B1`

R1 Config + Onboarding Kernel must precede B1 verification execution because execution authority depends on canonical target roots, artifact roots, config source precedence, setup receipts, rollback artifacts, and auditable capability defaults.

### Passive artifact spine (PRs #95-138)

**Session and preparation lane**
- Governed session workflow plan artifact (`builder_ii.session_workflow_plan`)
- Governed session configuration spine (`builder_ii.session_configuration`)
- Governed prepare-package command, validation, and summarization lane
- Repo map artifact (`builder_ii.repo_map`) — read-only filesystem scan
- Context pack artifact (`builder_ii.context_pack`) — high-signal subset extraction
- Operator command surface index (`docs/OPERATOR_COMMAND_SURFACE.md`)
- Governed session bootstrap guide (`docs/OPERATOR_QUICKSTART.md`)

**Goose projection and planning**
- Goose projection artifact (`builder_ii.goose_projection`) — PLANNED_ONLY
- Goose wrapper plan artifact (`builder_ii.goose_wrapper_plan`)
- Goose recipe/context projection artifact (`builder_ii.goose_recipe_context_projection`)
- Goose read-only session plan rendering (`builder_ii.goose_readonly_session_plan`)
- Runtime activation approval spec (`builder_ii.runtime_activation_approval_spec`) — PROPOSED_ONLY

**Orchestration and verification**
- Orchestration plan artifact (`builder_ii.orchestration_plan`) — all roles UNBOUND
- Orchestration dry-run artifact (`builder_ii.orchestration_dry_run`)
- Verification profile reports (`builder_ii.verification_profile_report`) — planned checks, NOT_RUN
- B1.1 verification execution plan artifact (`builder_ii.verification_execution_plan`) — planned-only, execution disabled
- B1.2 verification execution approval artifact (`builder_ii.verification_execution_approval`) — digest-bound HITL approval only, execution disabled
- B1.3A verification execution receipt artifact (`builder_ii.verification_execution_receipt`) — passive receipt contract
- B1.3B bounded approved verification runner (`builder-verify run-approved`) — one approved `platform_status` profile, fixed argv, `shell=False`, receipt-bound
- B1.4A/B/C/D passive verification execution ledger indexing, query, integrity, and reconstruction reports (`builder_ii.verification_execution_ledger_record`, `builder_ii.verification_execution_ledger_query_report`, `builder_ii.verification_execution_ledger_integrity_report`, `builder_ii.verification_execution_ledger_reconstruction_report`) — artifact reconstruction only, no execution replay
- Full governed preparation lane scenario tests

**HITL governance chain**
- HITL execution request/receipt records (`builder_ii.hitl_execution_request`, `builder_ii.hitl_execution_receipt`)
- Execution postflight/verification records (`builder_ii.execution_postflight_record`, `builder_ii.execution_verification_record`)
- HITL evidence bundle (`builder_ii.hitl_evidence_bundle`)
- HITL chain binding artifact (`builder_ii.hitl_chain_binding`) — cryptographic lifecycle binding
- HITL approved verification execution candidate (`builder_ii.hitl_approved_verification_execution_candidate`) — candidate only, no execution

**Platform governance**
- ConventionKernel as governed platform spine (`ConventionKernelPlatformBundle`)
- Command authority tier registry (`docs/COMMAND_AUTHORITY.md`)
- Model capability registry artifact (`builder_ii.model_capability_registry`)
- Artifact index and chain verification registry (all v0 kinds registered and closure-tested)
- v0 release manifest + operator-run proof harness (`builder_ii.v0_release_manifest`, `scripts/verify_v0_release.py`)
- Capability promotion registry (`docs/CAPABILITY_PROMOTION.md`)
- Generic-first identity pivot (PR #129) — CORE scoped to target profile throughout

**Supporting infrastructure (earlier PRs)**
- Target profiles: `generic`, `builder`, `core`
- Generic agent profiles
- Profile resolution layer
- Handoff note lifecycle (`builder_ii.handoff_note`)
- deepagents bridge readiness reports (`builder_ii.deepagents_bridge_readiness_report`)
- Artifact index and chain verification
- Runtime governance and release audit tests
- Builder platform release audit
- Passive profile-pack substrate (`builder_ii.profile_pack_manifest`, `builder_ii.profile_pack_render_plan`, `builder_ii.profile_pack_dry_run`, `builder_ii.profile_pack_validation_report`, `builder_ii.profile_pack`) for capability-factory composition without runtime authority

### Non-authority boundaries (enforced)

- No autonomous source writes
- No shell execution as an agent capability
- No deepagents runtime construction
- No model execution through the bridge
- No Goose runtime activation from specs or manifests
- No command execution from quality gates or verification candidates
- No arbitrary repository inspection
- No memory mutation
- No commit/push automation
- No CORE Workbench/UI coupling
- No Deephaven changes
- No CodeVault output as execution, verification, or promotion authority ([`ADR-0005`](adrs/ADR-0005-codevault-boundary-and-authority.md))

### CodeVault (intelligence substrate — vision set)

CodeVault is builder-II's governed reconstructive intelligence substrate (layout, identity, and
future structure/relations/change/evidence → reconstruction). **F0–F1** exist at staged-acceptance
capability states; F2+ and engineering utility on real repositories are gated, not claimed by docs.

Official vision set index: [`CODE_VAULT.md`](CODE_VAULT.md) (vision section) and
[`plan/CODE_VAULT_MASTER_PLAN.md`](plan/CODE_VAULT_MASTER_PLAN.md).

## Current operating loop

```bash
# Setup
builder-setup plan --output /tmp/builder-ii-setup-plan.json
builder-setup validate-plan /tmp/builder-ii-setup-plan.json
builder doctor
builder-targets validate
builder-agent validate

# Legacy / focused context and profile surfaces
builder-context pack
builder-profile-pack scaffold --target builder --output .builder/profile-pack/manifest.json
builder-profile-pack render .builder/profile-pack/manifest.json --output .builder/profile-pack/render-plan.json
builder-profile-pack dry-run .builder/profile-pack/manifest.json --render-plan .builder/profile-pack/render-plan.json --output .builder/profile-pack/dry-run.json
builder-profile-pack validate .builder/profile-pack/manifest.json --output .builder/profile-pack/validation-report.json
builder-verification artifact
builder-verification validate
builder-verify plan --target-profile builder --verification-profile builder_full --output .builder/verification/verification-execution-plan.json
builder-verify validate-plan .builder/verification/verification-execution-plan.json
builder-verify approve-plan .builder/verification/verification-execution-plan.json --approval-actor "Jane Operator" --approval-reason "Approve passive B1.1 verification plan for future B1.3 runner testing." --output .builder/verification/verification-execution-approval.json
builder-verify validate-approval .builder/verification/verification-execution-approval.json --plan .builder/verification/verification-execution-plan.json
builder-bundle create
builder-bundle validate
builder-research plan
builder-research validate
builder-quality plan
builder-quality validate
builder-notes handoff
builder-notes validate

# Session preparation
builder-session prepare-package --target builder --task "..." --output .builder/session/
builder-session validate-prepare-package .builder/session/
builder-session summarize-prepare-package .builder/session/

# ConventionKernel platform spine
builder-session config --target builder --task "..."
builder-session goose-projection ...
builder-session goose-readonly-plan ...
builder-goose manifest ...
builder-goose validate ...
builder-goose readonly-audit ...
builder-goose validate-audit ...
builder-goose inspect-readonly ...
builder-goose validate-inspection ...

# HITL governance artifacts
builder-hitl request ...
builder-hitl receipt ...

# Verification and handoff
builder-notes handoff ...
builder-verification artifact ...

# Optional deepagents / bridge artifacts
builder-deepagents policy ...
builder-deepagents validate ...
builder-deepagents readiness ...
builder-deepagents validate-readiness ...
builder-bridge render ...
builder-bridge validate-artifact ...
```

Every command above renders a reviewable artifact or validates an existing one. None grants runtime authority.

## Remaining extension surfaces (what comes after v0)

These are the next capability promotions. Each requires the full capability promotion gate (docs, tests, command surface, failure mode, HITL boundary, output artifact, rollback path, verification path) before it can move from candidate to enabled.

### R0 -> R1 -> B1 ladder

- R0: completion truth matrix, platform status CLI, docs truth audit, command authority coverage, and tests.
- R1: Config + Onboarding Kernel for canonical source precedence, setup plan/apply/validate, receipts, rollback artifacts, and capability defaults.
- B1: HITL-approved verification execution after R1 has made target roots, artifact roots, and setup state auditable. B1.1 is only a passive verification execution plan artifact, B1.2 is only a digest-bound HITL approval binding artifact, B1.3 adds the bounded `platform_status` runner receipt, and B1.4 completes the passive ledger/reconstruction layer before any broader execution authority. B2 starts with promotion gating and the smallest governed live-read template, not patching.

### Phase: profile-pack / capability-factory substrate (next planning spine)
- Introduce user-created profile packs for target profiles, agents, subagents, tasks, tools, context, verification, approval, Goose projections, deepagents projections, MCP policies, and handoff profiles
- Add scaffold, render, validate, and dry-run lifecycle commands before any runtime authority
- Require deterministic hashes, denied defaults, schema versions, source refs, and authority classifications

### Phase: read-only file inspection
- Promote bounded file inspection into actual runtime reads against operator-specified paths
- Canonical template for all subsequent execution gate promotions

### Phase: model/provider execution gateway
- Passive model registry and routing artifacts already exist through `builder-model-policy`
- Provider execution remains unpromoted until B6 adds an envelope, prompt/context digest, budget, receipt, ledger, and replay declaration

### Phase: WRP orchestration & routing control plane (ADR-0007 Proposed)
- Geometry-first Workload–Router–Pool plane under `builder_ii/wrp/` and `builder-wrp` (Tier 1)
- Waves G0–W5: classifier, collaboration topology, fleet allocation, MSDA gates, experience/adjoint, reconstructive replay
- Dual-platform Maker (Grok Build) / Governor (Antigravity) file-mediated merge ceremony
- Default state remains recommendation/plan/validation only — no live multi-agent execution promotion by module existence
- See `docs/WRP_CONTROL_PLANE.md`, `docs/WRP_ACCEPTANCE.md`

### Phase: live deepagents render (planning mode)
- Render deepagents planning artifacts from session config
- No agent construction or delegation until HITL gate is crossed

### Phase: HITL command proposal → approved execution
- Command proposal artifact → operator approval → HITL chain binding → approved execution candidate → actual execution
- Requires full evidence chain and rollback path

### Phase: HITL patch proposal → approved apply
- Patch proposal artifact → operator review → approved patch application
- Requires full verification evidence

### Phase: artifact memory and context reconstruction
- B8 adds explicit artifact-memory envelopes, indexes, deterministic search results, and replay-stable reconstructions via `builder-memory`
- No hidden memory mutation; summaries remain derived and non-authoritative

### Phase: event ledger and observability
- Define runtime event records for denial, approval, invocation, verification, rollback, handoff, model routing, MCP, Goose, and deepagents activity
- Ensure event records are replayable, chainable, and auditable

### Phase: security and secret-boundary hardening
- Keep raw secrets out of artifacts
- Use token refs, path redaction, prompt/log redaction, and explicit approval for network, cost, credential, and external-provider escalation

### Phase: end-to-end target demos
- One passive demo path per target: `generic`, `builder`, `core`
- Shows the governed lane on real repos without implying runtime authority

### Phase: performance tracks (measurement-gated)
- Rust-backed artifact validation — only if measurement proves value
- MLX + UMA context compression — provenance-preserving only
- See `docs/plan/PERFORMANCE_AND_EFFICIENCY_AMENDMENT.md`

### Phase: CI quality gate enforcement
- Enforce full test suite in CI on every PR
- No merge without green gate

### Phase: production playbooks and release polish
- Failure recovery docs
- Operator runbooks per target
- Formal release checklist

## Design-halt RFCs

During implementation halts, builder-II may advance through design-only RFCs that clarify future artifact contracts without enabling runtime behavior.

Current RFCs:

- `docs/plan/ARTIFACT_MEMORY_RFC.md` — artifact graph memory, memory atom envelope, reconstruction posture, and summary boundaries.
- `docs/plan/DEEPAGENTS_WORK_ARTIFACTS_RFC.md` — deepagents plan/assignment/result/review/gate artifacts before any deepagents runtime construction.
- `docs/plan/PASSIVE_HITL_PROMOTION_BRIDGE_RFC.md` — passive HITL promotion bridge artifacts connecting Goal 2 and Goal 3 proposals to traceable human boundaries.
- `docs/plan/PASSIVE_EXECUTION_CANDIDATE_MANIFEST_RFC.md` — Goal 5 passive execution candidate manifest design that consumes a verified `builder_ii.hitl_approval_boundary` and authorizes only bounded candidate/validation artifacts, not runtime activation.
- `docs/plan/RUST_VALIDATION_SPIKE.md` — measurement-first Rust validation spike plan with Python reference parity.
- `docs/plan/GOOSE_DEEPAGENTS_MCP_SEAM.md` — Goose as operator runtime, deepagents as governed inner harness, and MCP as policy-gated integration seam.
- `docs/plan/MCP_POLICY_ARTIFACT_RFC.md` — deny-by-default MCP policy artifact for tools, resources, prompts, roots, sampling, elicitation, auth, limits, and result handling.
- `docs/plan/MCP_TOOL_INVENTORY_RFC.md` — MCP inventory artifact, tool/resource/prompt hashes, risk classification, and change detection before policy or invocation.

These RFCs are not implementation authority. They do not enable memory mutation, deepagents construction, Rust dependencies, shell execution, model calls, source mutation, MCP connection, MCP tool execution, target repo mutation, execution candidate activation, or Goose runtime activation.

## Performance and integration priorities

See `docs/plan/PERFORMANCE_AND_EFFICIENCY_AMENDMENT.md` for the detailed amendment.

The amendment adds three first-class candidate tracks without promoting runtime behavior:

- Rust-backed artifact validation and processing, gated by measurement and parity evidence.
- MLX + UMA context compression, restricted to provenance-preserving review artifacts.
- Model routing and hybrid execution policy, introduced first as an artifact surface rather than hidden automatic model calls.

These tracks run alongside the existing runtime integration phases. They must preserve the no-runtime governance foundation, the capability promotion rule, target-profile boundaries, and the separation between builder-II and CORE Workbench/UI.
