# HITL Command Execution Specification

## Platform Identity & Scope

builder-II is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench/UI/UX, and not a second CORE runtime. CORE is only a target profile.

This document serves as the design specification for future Human-In-The-Loop (HITL) command execution. In its current phase, all runtime execution capabilities remain strictly inactive.

## Spec Artifact Definition

The specification artifact kind is defined as:
`builder_ii.hitl_command_execution_spec`

### Current State
* `DESIGN_ONLY`
* `DISABLED`

### Allowed Future Transitions
To promote a proposed command to execution in future runtime iterations, the system must traverse the following governed state transitions:
1. **command proposal**: Generation of a proposal artifact describing the exact command and target repository.
2. **approval record**: Cryptographic or explicit human authorization boundary.
3. **preflight record**: Validation of environment readiness and risk level assessment.
4. **explicit execution request**: Intentional invocation request bound to approved preflight state.
5. **execution receipt**: Capture of exit code, stdout, stderr, and timing metrics.
6. **postflight/handoff**: Indexing verification and audit log persistence.

### Denied Current Behavior
While in `DESIGN_ONLY` mode, the runtime strictly denies all active execution operations:
* no subprocess
* no shell execution
* no command execution
* no model execution
* no source writes
* no git mutation
* no commit/push
* no network/MCP execution
* no Goose runtime activation
* no deepagents runtime

### Required Future Gates
Before any future promotion to active runtime execution, all of the following quality and safety gates must pass:
* docs
* tests
* command surface
* failure mode
* human approval boundary
* output artifact
* rollback path
* verification path

## Governance & Authority
* **Artifact Authority**: The design artifact is not authority (`artifact_is_authority: false`). It cannot grant permissions or bypass system guards.
* **Workbench Coupling**: CORE Workbench coupling is `NONE`.
