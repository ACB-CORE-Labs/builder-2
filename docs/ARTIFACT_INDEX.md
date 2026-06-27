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
- `builder_ii.convention_kernel_platform_bundle`

## Governance / spec / record artifacts

The following artifact kinds are **governance, specification, and record artifacts** introduced in PR W, PR X, PR Y, PR AD, PR AE, and PR AF.  They are design-only records that document future runtime governance paths.  They do **not** grant runtime authority, execute commands, mutate source, invoke subprocesses, or activate any runtime.

| Kind | Category | Source PR |
|------|----------|-----------|
| `builder_ii.hitl_execution_request` | Governance record | PR W |
| `builder_ii.hitl_execution_receipt` | Governance record | PR W |
| `builder_ii.hitl_patch_application_spec` | Design specification | PR X |
| `builder_ii.rollback_plan` | Governance record | PR Y |
| `builder_ii.rollback_receipt` | Governance record | PR Y |
| `builder_ii.execution_postflight_record` | Governance record | PR AD |
| `builder_ii.execution_verification_record` | Governance record | PR AD |
| `builder_ii.hitl_evidence_bundle` | Evidence bundle index | PR AE |
| `builder_ii.session_workflow_plan` | Session plan specification | PR AF |
| `builder_ii.convention_kernel_platform_bundle` | Platform spine bundle | PR AG |

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
