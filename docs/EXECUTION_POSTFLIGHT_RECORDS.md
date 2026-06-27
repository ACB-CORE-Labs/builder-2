# Execution Postflight and Verification Records

This document defines the schema and role of the execution postflight and verification records in the builder-II platform.

> [!IMPORTANT]
> **Design-Only Specifications**
> - These are postflight/verification record specs only.
> - They do not prove execution occurred.
> - They do not execute verification commands.
> - They do not run tests.
> - They do not grant authority.
> - verification_state: PASS is only an externally supplied record state — not produced by runtime in this PR.


## Scope and Intent

- **builder-II is generic-first**
- **builder-II is not CORE Workbench/UI/UX**
- **CORE is only a target profile**

## Artifact Schemas

### 1. Execution Postflight Record

- **Kind**: `builder_ii.execution_postflight_record`
- **Schema Version**: `1`

An execution postflight record is written after a command has been proposed, approved, preflighted, and received. It records expected outcomes and lists references to the preceding stages of execution.

#### Fields

- `kind`: `builder_ii.execution_postflight_record`
- `schema_version`: `1`
- `target`: Target profile object representing the target workspace (e.g. generic, builder, core)
- `request_ref`: Non-empty string reference to the corresponding execution request
- `receipt_ref`: Non-empty string reference to the execution receipt
- `preflight_ref`: Non-empty string reference to the preflight record
- `approval_ref`: Non-empty string reference to the approval record
- `expected_outcome`: Description of the expected changes or outcomes
- `observed_state_ref`: String reference to the observed system state
- `postflight_state`: Fixed to `NOT_RUN` in this specification
- `performed_actions`: Fixed to `[]`
- `artifact_is_authority`: Fixed to `false`
- `governance`: The disabled governance block

### 2. Execution Verification Record

- **Kind**: `builder_ii.execution_verification_record`
- **Schema Version**: `1`

An execution verification record captures the results of checking that the executed action met expectations.

#### Fields

- `kind`: `builder_ii.execution_verification_record`
- `schema_version`: `1`
- `target`: Target profile object representing the target workspace
- `request_ref`: Non-empty string reference to the execution request
- `receipt_ref`: Non-empty string reference to the execution receipt
- `postflight_ref`: Non-empty string reference to the execution postflight record
- `verification_state`: Must be one of `NOT_RUN`, `PASS`, or `FAIL`
- `verification_summary`: Human-readable summary of the verification check
- `evidence_refs`: List of string references pointing to supporting evidence (logs, outputs, diffs)
- `performed_actions`: Fixed to `[]`
- `artifact_is_authority`: Fixed to `false`
- `governance`: The disabled governance block

## Governance Block

Both record types contain the following disabled governance block:

```json
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
  "artifact_is_authority": false,
  "core_workbench_coupling": "NONE"
}
```

## Chain Evidence Status

These artifacts are not currently used for outbound chain verification fallback links. The references (`request_ref`, `receipt_ref`, `preflight_ref`, `approval_ref`, `postflight_ref`) are documented as plain string references until a future typed chain-link PR.
