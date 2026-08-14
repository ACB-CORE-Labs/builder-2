# Human-in-the-Loop (HITL) Execution Evidence Bundle

This document defines the schema, validations, and role of the read-only HITL execution evidence bundle/index in the builder-II platform.

> [!IMPORTANT]
> **Design-Only Metadata Specification**
> - The evidence bundle is purely read-only metadata and acts as an index/manifest of manifests.
> - It does **not** grant any runtime execution authority.
> - It does **not** perform execution of commands or patches.
> - All execution/runtime capabilities (shell, subprocess, model, DeepAgents, Goose execution) remain strictly disabled.
> - The bundle is an aggregation and index record, not a proof of execution.

## Scope and Intent

- **builder-II is generic-first**: Designed to support generic workspaces.
- **builder-II is not CORE Workbench/UI/UX**: It remains decoupled from any CORE runtime UI/UX.
- **CORE is only a target profile**: CORE targets are treated as configuration profiles without special runtime execution authority.

## Artifact Schema

- **Kind**: `builder_ii.hitl_evidence_bundle`
- **Schema Version**: `1`

An HITL execution evidence bundle represents the aggregated and validated governance trail across the execution lifecycle. It links all required stage artifacts into a single cohesive record.

### Fields

- `kind`: `builder_ii.hitl_evidence_bundle`
- `schema_version`: `1`
- `target_name`: Must be one of `generic`, `builder`, or `core`
- `bundle_id`: Unique identifier for the bundle
- `created_at`: Creation timestamp
- `created_by`: Username or actor who created the bundle
- `proposal_ref`: Required non-empty path/reference to the `builder_ii.goose_command_proposal` artifact
- `approval_ref`: Required non-empty path/reference to the `builder_ii.approval_record` artifact
- `preflight_ref`: Required non-empty path/reference to the `builder_ii.preflight_record` artifact
- `request_ref`: Required non-empty path/reference to the `builder_ii.hitl_execution_request` artifact
- `postflight_ref`: Required non-empty path/reference to the `builder_ii.execution_postflight_record` artifact
- `verification_ref`: Required non-empty path/reference to the `builder_ii.execution_verification_record` artifact
- `rollback_plan_ref`: Optional path/reference to the `builder_ii.rollback_plan` artifact (None or string)
- `rollback_receipt_ref`: Optional path/reference to the `builder_ii.rollback_receipt` artifact (None or string)
- `execution_authority`: Must be `"NOT_GRANTED"`
- `runtime_execution`: Must be `"NOT_PERFORMED_BY_BUNDLE"`
- `bundle_state`: Must be `"INDEX_ONLY"`
- `governance`: The standard disabled governance block

### Suggested Schema Structure

```json
{
  "kind": "builder_ii.hitl_evidence_bundle",
  "schema_version": 1,
  "target_name": "generic",
  "bundle_id": "...",
  "created_at": "...",
  "created_by": "...",
  "proposal_ref": "...",
  "approval_ref": "...",
  "preflight_ref": "...",
  "request_ref": "...",
  "postflight_ref": "...",
  "verification_ref": "...",
  "rollback_plan_ref": null,
  "rollback_receipt_ref": null,
  "execution_authority": "NOT_GRANTED",
  "runtime_execution": "NOT_PERFORMED_BY_BUNDLE",
  "bundle_state": "INDEX_ONLY",
  "governance": {
    "runtime_execution": "DISABLED",
    "shell_execution": "DISABLED",
    "command_execution": "DISABLED",
    "model_execution": "DISABLED",
    "source_writes": "DISABLED",
    "git_mutation": "DISABLED",
    "network_access": "DISABLED",
    "goose_runtime_activation": "DISABLED",
    "deepagents_runtime": "DISABLED",
    "subprocess_execution": "DISABLED",
    "artifact_is_authority": false,
    "core_workbench_coupling": "NONE"
  }
}
```

## Validation & Chain Evidence Status

The bundle is registered with the artifact index and the chain verifier. The chain verifier extracts outbound references from the bundle to all referenced stage artifacts (from command proposal to verification, and optionally rollback plan and receipt). 

- **Required reference existence**: All required ref files must exist, match their expected kinds, and validate successfully.
- **Fail Closed**: Any unknown artifact kind resolved in the chain verification process fails the verification.
- **Verification vs. Approval**: The verification state cannot imply approval, and the execution state cannot imply authority.
