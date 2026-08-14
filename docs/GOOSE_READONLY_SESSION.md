# Goose Governed Read-Only Session Plan

This document details the design, schema, and operational rules for the Goose governed read-only session plan (`builder_ii.goose_readonly_session_plan`). 

This artifact integrates Goose ergonomically as a governed read-only target, enabling `builder-II` to render instructions compiled from target, agent, prompt, context pack, and verification profiles, while strictly enforcing safety boundaries without executing Goose.

## Design Goals
- **Deterministic compilation**: Instruction sets are rendered consistently using unified profile resolution.
- **Strict safety borders**: Mode is set to `read_only`, shell execution is disabled, and autonomous writes are disabled.
- **Governance visibility**: Explicit references to Human-in-the-Loop (HITL) boundaries and the Verification Plan are embedded directly.

## Plan Schema

A Goose read-only session plan contains:

- `kind: builder_ii.goose_readonly_session_plan`
- `schema_version: 1`
- `task`: The task description for the session.
- `target_profile`: The resolved target metadata.
- `selected_agent_profile`: The resolved agent profile record.
- `selected_prompt_profile`: The resolved prompt profile.
- `selected_verification_profile`: The resolved verification profile.
- `context_pack`: Embedded context pack record if provided.
- `goose_instructions`: The fully compiled prompt instructions text intended for Goose.
- `runtime_mode`: Always set to `"read_only"`.
- `shell_execution`: Always set to `"DISABLED"`.
- `autonomous_writes`: Always set to `"DISABLED"`.
- `hitl_boundaries`: A list of rules outlining what actions require human-in-the-loop validation.
- `verification_plan`: References to out-of-band verification command templates.
- `governance`: The standard platform governance block.

## CLI Usage

### Generate a read-only Goose session plan:
```bash
builder-session goose-readonly-plan generic \
  --agent repo_mapper \
  --prompt generic_default \
  --verification generic_basic \
  --task "Audit dependencies" \
  --output .builder/goose-readonly-plan.json
```

### Validate a plan file:
```bash
builder-session validate-goose-readonly-plan .builder/goose-readonly-plan.json
```

## Governance Limits
The plan artifact enforces strict safety controls:
```json
"governance": {
  "capability_state": "goose_readonly_session_plan",
  "runtime_execution": "DISABLED",
  "model_execution": "DISABLED",
  "shell_execution": "DISABLED",
  "source_writes": "DISABLED",
  "memory_mutation": "DISABLED",
  "artifact_is_authority": false,
  "core_workbench_coupling": "NONE"
}
```
No subprocess spawning, active model loading, or repository writing is allowed or triggered during the generation of the plan.
