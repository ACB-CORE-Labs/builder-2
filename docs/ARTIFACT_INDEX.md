# Artifact index

Artifact index records scan a directory of JSON artifact files and record metadata for each known governed artifact.

The index records:

- relative path;
- SHA-256 digest;
- byte count;
- artifact kind;
- schema version;
- known/valid flags;
- validation errors.

It is metadata-only and does not activate artifact authority.

## Known artifact kinds

- `builder_ii.goose_command_proposal`
- `builder_ii.approval_record`
- `builder_ii.preflight_record`
- `builder_ii.receipt_record`
- `builder_ii.chain_summary_record`
- `builder_ii.handoff_bundle_record`
- `builder_ii.receive_record`
- `builder_ii.promotion_readiness_record`
- `builder_ii.promotion_decision_record`
- `builder_ii.state_ledger_record`
- `builder_ii.artifact_index_record`
- `builder_ii.snapshot_record`
- `builder_ii.target_profile`
- `builder_ii.verification_profile`
- `builder_ii.context_pack_record`
- `builder_ii.agent_profile_record`
- `builder_ii.git_state_record`
- `builder_ii.research_plan`
- `builder_ii.research_adapter`
- `builder_ii.performance_measurement`
- `builder_ii.readonly_inspection_promotion_spec`
- `builder_ii.readonly_inspection_report`
- `builder_ii.hitl_execution_request`
- `builder_ii.hitl_execution_receipt`
- `builder_ii.hitl_verification_execution_candidate`
- `builder_ii.hitl_patch_proposal`
- `builder_ii.hitl_patch_approval`
- `builder_ii.hitl_rollback_approval`
- `builder_ii.hitl_patch_ledger_record`
- `builder_ii.demo_deterministic_planner`
- `builder_ii.demo_preflight`
- `builder_ii.demo_verification_receipt`
- `builder_ii.demo_loop_report`
- `builder_ii.rollback_plan`
- `builder_ii.rollback_receipt`
- `builder_ii.execution_postflight_record`
- `builder_ii.execution_verification_record`
- `builder_ii.hitl_evidence_bundle`
- `builder_ii.hitl_chain_binding`
- `builder_ii.session_workflow_plan`
- `builder_ii.repo_map`
- `builder_ii.code_vault.hierarchical_frame`
- `builder_ii.code_vault.geometric_linter_report`
- `builder_ii.code_vault.context_projection`
- `builder_ii.code_vault.recall_report`
- `builder_ii.code_vault.bench_report`
- `builder_ii.verification_promotion_evidence`
- `builder_ii.code_vault_corroboration_record`
- `builder_ii.context_pack`
- `builder_ii.convention_kernel_platform_bundle`
- `builder_ii.governed_prepare_package`
- `builder_ii.governed_prepare_package_summary`
- `builder_ii.orchestration_plan`
- `builder_ii.orchestration_dry_run`
- `builder_ii.agent_assignment_plan`
- `builder_ii.orchestration_assignment_plan`
- `builder_ii.orchestration_assignment_dry_run`
- `builder_ii.orchestration_assignment_validation_report`
- `builder_ii.orchestration_obligation`
- `builder_ii.orchestration_lane_policy`
- `builder_ii.runtime_activation_approval_spec`
- `builder_ii.goose_readonly_session_plan`
- `builder_ii.goose_projection`
- `builder_ii.goose_wrapper_plan`
- `builder_ii.verification_profile_report`
- `builder_ii.handoff_note`
- `builder_ii.deepagents_bridge_readiness_report`
- `builder_ii.deepagents_governed_policy`
- `builder_ii.deepagents_dependency_readiness`
- `builder_ii.deepagents_work_plan`
- `builder_ii.deepagents_subagent_assignment`
- `builder_ii.deepagents_subagent_result`
- `builder_ii.deepagents_subagent_review`
- `builder_ii.deepagents_human_gate_request`
- `builder_ii.deepagents_blocked_action_record`
- `builder_ii.deepagents_proposal_result`
- `builder_ii.deepagents_work_validation_report`
- `builder_ii.hitl_promotion_request`
- `builder_ii.hitl_promotion_review`
- `builder_ii.hitl_promotion_decision`
- `builder_ii.hitl_approval_boundary`
- `builder_ii.hitl_rejection_record`
- `builder_ii.hitl_promotion_validation_report`
- `builder_ii.execution_candidate_manifest`
- `builder_ii.execution_candidate_manifest_validation_report`
- `builder_ii.goose_session_manifest`
- `builder_ii.handoff_artifact`
- `builder_ii.session_configuration`
- `builder_ii.v0_release_manifest`
- `builder_ii.artifact_chain_verification_report`
- `builder_ii.model_capability_registry`
- `builder_ii.profile_pack_manifest`
- `builder_ii.profile_pack_render_plan`
- `builder_ii.profile_pack_dry_run`
- `builder_ii.profile_pack_validation_report`
- `builder_ii.profile_pack`
- `builder_ii.model_client_registry`
- `builder_ii.model_routing_policy`
- `builder_ii.model_routing_recommendation`
- `builder_ii.workflow_session`
- `builder_ii.workflow_status`
- `builder_ii.workflow_transition`
- `builder_ii.event_record`
- `builder_ii.event_ledger`
- `builder_ii.ledger_replay_report`
- `builder_ii.gate_battery_receipt`

## Governance and Authority Boundaries

Artifacts validate structure and governance invariants. They are design-only and passive record objects.
- **Artifacts are not runtime authority.** A valid artifact does not grant permission to run models or execute commands.
- **Valid artifacts do not run commands.** They are structurally audited configurations, not active scripts.
- **Valid artifacts do not mutate source.** The verification and projection steps are read-only and leave repository source untouched.
- **Valid artifacts do not prove planned verification was executed.** Emitting a verification plan or summary artifact does not substitute for actual execution evidence. Evidence receipts must be recorded after out-of-band execution.

## Governance / spec / record artifacts

The following artifact kinds are **governance, specification, and record artifacts** introduced in PRs #118 through #138.

| Kind | Category | Source PR |
|------|----------|-----------|
| `builder_ii.hitl_execution_request` | Governance record | #118 |
| `builder_ii.hitl_execution_receipt` | Governance record | #118 |
| `builder_ii.hitl_verification_execution_candidate` | HITL verification candidate | #138 |
| `builder_ii.hitl_patch_proposal` | Design specification | #120 |
| `builder_ii.rollback_plan` | Governance record | #122 |
| `builder_ii.rollback_receipt` | Governance record | #122 |
| `builder_ii.execution_postflight_record` | Governance record | #124 |
| `builder_ii.execution_verification_record` | Governance record | #124 |
| `builder_ii.hitl_evidence_bundle` | Evidence bundle index | #126 |
| `builder_ii.hitl_chain_binding` | Passive evidence-chain metadata | #136 |
| `builder_ii.session_workflow_plan` | Session plan specification | #128 |
| `builder_ii.convention_kernel_platform_bundle` | Platform spine bundle | #131 |
| `builder_ii.governed_prepare_package` | Package specification | #132 |
| `builder_ii.governed_prepare_package_summary` | Package summary record | #132 |
| `builder_ii.orchestration_plan` | Orchestration plan | #133 |
| `builder_ii.orchestration_dry_run` | Dry run specification | #133 |
| `builder_ii.agent_assignment_plan` | Passive agent assignment plan | Goal 2 |
| `builder_ii.orchestration_assignment_plan` | Passive orchestration assignment plan | Goal 2 |
| `builder_ii.orchestration_assignment_dry_run` | Passive orchestration assignment dry run | Goal 2 |
| `builder_ii.orchestration_assignment_validation_report` | Passive assignment validation report | Goal 2 |
| `builder_ii.orchestration_obligation` | Governed delegation obligation (Law 1 ticket) | Ladder 4 |
| `builder_ii.orchestration_lane_policy` | Obligation-kind → lane → discharge policy (derived view) | Ladder 4 |
| `builder_ii.runtime_activation_approval_spec` | Runtime activation spec | #133 |
| `builder_ii.goose_readonly_session_plan` | Goose readonly plan | #133 |
| `builder_ii.goose_projection` | Projection spec | #133 |
| `builder_ii.goose_wrapper_plan` | Launch plan spec | #133 |
| `builder_ii.verification_profile_report` | Verification report plan | #133 |
| `builder_ii.handoff_note` | Handoff note | #133 |
| `builder_ii.deepagents_bridge_readiness_report` | Bridge readiness check | #133 |
| `builder_ii.deepagents_governed_policy` | Passive deepagents governed policy | Goal 3 prerequisite |
| `builder_ii.deepagents_dependency_readiness` | Passive deepagents dependency readiness | Goal 3 prerequisite |
| `builder_ii.deepagents_work_plan` | Passive deepagents work plan | Goal 3 |
| `builder_ii.deepagents_subagent_assignment` | Passive deepagents subagent assignment | Goal 3 |
| `builder_ii.deepagents_subagent_result` | Passive deepagents subagent result | Goal 3 |
| `builder_ii.deepagents_subagent_review` | Passive deepagents subagent review | Goal 3 |
| `builder_ii.deepagents_human_gate_request` | Passive deepagents human gate request | Goal 3 |
| `builder_ii.deepagents_blocked_action_record` | Passive deepagents blocked action record | Goal 3 |
| `builder_ii.deepagents_proposal_result` | Passive deepagents proposal result | Goal 3 |
| `builder_ii.deepagents_work_validation_report` | Passive deepagents validation report | Goal 3 |
| `builder_ii.goose_session_manifest` | Goose session manifest | #133 |
| `builder_ii.handoff_artifact` | Handoff record | #133 |
| `builder_ii.session_configuration` | Session configuration | #133 |
| `builder_ii.v0_release_manifest` | V0 release proof manifest | #135 |
| `builder_ii.artifact_chain_verification_report` | Chain verification report | #135 |
| `builder_ii.profile_pack_manifest` | Passive profile-pack manifest | current |
| `builder_ii.profile_pack_render_plan` | Passive profile-pack render plan | current |
| `builder_ii.profile_pack_dry_run` | Passive profile-pack dry run | current |
| `builder_ii.profile_pack_validation_report` | Passive profile-pack validation report | current |
| `builder_ii.profile_pack` | Passive profile-pack lifecycle bundle | current |
| `builder_ii.model_client_registry` | Passive model client registry | current |
| `builder_ii.model_routing_policy` | Passive model routing policy | current |
| `builder_ii.model_routing_recommendation` | Passive model routing recommendation | current |
| `builder_ii.workflow_session` | Passive workflow session record | current |
| `builder_ii.workflow_status` | Replayed workflow status record | current |
| `builder_ii.workflow_transition` | Passive workflow transition record | current |
| `builder_ii.event_record` | Event-sourced workflow transition record | current |
| `builder_ii.event_ledger` | Passive workflow event ledger | current |
| `builder_ii.ledger_replay_report` | Deterministic ledger replay report | current |
| `builder_ii.execution_candidate_manifest` | Bounded proposed future execution candidate | Goal 5 |
| `builder_ii.execution_candidate_manifest_validation_report` | Candidate manifest validation report | Goal 5 |

**Chain evidence status:** Most standalone governance records do not embed outbound references. However, the `builder_ii.hitl_verification_execution_candidate` embeds candidate-stage references to proposal, approval, preflight, and request artifacts while encoding future receipt/postflight/verification/chain requirements as requirements, not completed evidence. The `builder_ii.hitl_evidence_bundle` acts as a "manifest of manifests", specifying path references to all required stage artifacts, while `builder_ii.hitl_chain_binding` records passive chain metadata that binds the same evidence slots without granting execution authority. The Goal 2 assignment artifacts also embed source refs so target, agent, task/profile-pack, model-routing, context, verification, tool, HITL, output, and handoff bindings can be resolved and hash-checked without executing them. The chain verifier resolves these references and recursively validates each target record to ensure the governance trail is intact and valid. If any stage artifact has an unknown kind or fails native validation, the entire chain fails closed.

## CLI

```text
builder-index record .builder/artifacts --output .builder/artifacts/artifact-index.json
builder-index record .builder/artifacts --recursive --output .builder/artifacts/artifact-index.json
builder-index validate .builder/artifacts/artifact-index.json
```

## Verification

```bash
uv run pytest tests/test_artifact_index_records.py tests/test_artifact_index_cli.py -q
uv run pytest -q
```
