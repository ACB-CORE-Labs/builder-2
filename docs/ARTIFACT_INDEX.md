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
- `builder_ii.hitl_patch_application_spec`
- `builder_ii.rollback_plan`
- `builder_ii.rollback_receipt`
- `builder_ii.execution_postflight_record`
- `builder_ii.execution_verification_record`
- `builder_ii.hitl_evidence_bundle`
- `builder_ii.session_workflow_plan`
- `builder_ii.repo_map`
- `builder_ii.context_pack`
- `builder_ii.convention_kernel_platform_bundle`
- `builder_ii.governed_prepare_package`
- `builder_ii.governed_prepare_package_summary`
- `builder_ii.orchestration_plan`
- `builder_ii.orchestration_dry_run`
- `builder_ii.runtime_activation_approval_spec`
- `builder_ii.goose_readonly_session_plan`
- `builder_ii.goose_projection`
- `builder_ii.goose_wrapper_plan`
- `builder_ii.verification_profile_report`
- `builder_ii.handoff_note`
- `builder_ii.deepagents_bridge_readiness_report`
- `builder_ii.goose_session_manifest`
- `builder_ii.handoff_artifact`
- `builder_ii.session_configuration`
- `builder_ii.v0_release_manifest`
- `builder_ii.artifact_chain_verification_report`

## Governance and Authority Boundaries

Artifacts validate structure and governance invariants. They are design-only and passive record objects.
- **Artifacts are not runtime authority.** A valid artifact does not grant permission to run models or execute commands.
- **Valid artifacts do not run commands.** They are structurally audited configurations, not active scripts.
- **Valid artifacts do not mutate source.** The verification and projection steps are read-only and leave repository source untouched.
- **Valid artifacts do not prove planned verification was executed.** Emitting a verification plan or summary artifact does not substitute for actual execution evidence. Evidence receipts must be recorded after out-of-band execution.

## Governance / spec / record artifacts

The following artifact kinds are **governance, specification, and record artifacts** introduced in PRs #118 through #133.

| Kind | Category | Source PR |
|------|----------|-----------|
| `builder_ii.hitl_execution_request` | Governance record | #118 |
| `builder_ii.hitl_execution_receipt` | Governance record | #118 |
| `builder_ii.hitl_patch_application_spec` | Design specification | #120 |
| `builder_ii.rollback_plan` | Governance record | #122 |
| `builder_ii.rollback_receipt` | Governance record | #122 |
| `builder_ii.execution_postflight_record` | Governance record | #124 |
| `builder_ii.execution_verification_record` | Governance record | #124 |
| `builder_ii.hitl_evidence_bundle` | Evidence bundle index | #126 |
| `builder_ii.session_workflow_plan` | Session plan specification | #128 |
| `builder_ii.convention_kernel_platform_bundle` | Platform spine bundle | #131 |
| `builder_ii.governed_prepare_package` | Package specification | #132 |
| `builder_ii.governed_prepare_package_summary` | Package summary record | #132 |
| `builder_ii.orchestration_plan` | Orchestration plan | #133 |
| `builder_ii.orchestration_dry_run` | Dry run specification | #133 |
| `builder_ii.runtime_activation_approval_spec` | Runtime activation spec | #133 |
| `builder_ii.goose_readonly_session_plan` | Goose readonly plan | #133 |
| `builder_ii.goose_projection` | Projection spec | #133 |
| `builder_ii.goose_wrapper_plan` | Launch plan spec | #133 |
| `builder_ii.verification_profile_report` | Verification report plan | #133 |
| `builder_ii.handoff_note` | Handoff note | #133 |
| `builder_ii.deepagents_bridge_readiness_report` | Bridge readiness check | #133 |
| `builder_ii.goose_session_manifest` | Goose session manifest | #133 |
| `builder_ii.handoff_artifact` | Handoff record | #133 |
| `builder_ii.session_configuration` | Session configuration | #133 |
| `builder_ii.v0_release_manifest` | V0 release proof manifest | #135 |
| `builder_ii.artifact_chain_verification_report` | Chain verification report | #135 |

**Chain evidence status:** The standalone governance records do not embed outbound references. However, the `builder_ii.hitl_evidence_bundle` acts as a "manifest of manifests", specifying path references to all required stage artifacts. The chain verifier resolves these references and recursively validates each target record to ensure the governance trail is intact and valid. If any stage artifact has an unknown kind or fails native validation, the entire chain fails closed.

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
