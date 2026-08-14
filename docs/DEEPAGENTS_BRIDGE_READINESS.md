# DeepAgents Bridge Readiness

This document describes the `builder_ii.deepagents_bridge_readiness_report` artifact and its corresponding capabilities.

## Purpose

The deepagents bridge readiness report is an artifact that declares the compatibility and readiness state of the `builder-II` governed agent platform to bridge into an optional `deepagents` runtime in the future.

This component is strictly a **passive**, **read-only**, **informational** artifact. It is designed to prove governance boundaries and bridge readiness without activating any downstream autonomous capabilities.

## Strict Restrictions

To ensure safety and governed execution, this component is subject to the following hard constraints:
- **No Import Side Effects**: It must not import `deepagents` at module level or execute any of its code. Dependency checks are performed safely via `importlib.util.find_spec`.
- **No Shell Execution**: It must not execute shell commands (`os.system`, `subprocess`, etc).
- **No Model/Runtime Execution**: It must not instantiate agents, trigger LLM calls, or invoke the deepagents runtime.
- **No Autonomous Writes**: It must not write to the source tree or mutate memory outside of generating its specific readiness report.
- **No Authority**: It explicitly denies runtime authority (`artifact_is_authority: false`). It cannot bypass HITL (Human-in-the-Loop) gates.

## Required Promotion Gates

Before an actual execution bridge can be established in the future, the following promotion gates must be satisfied as declared in the artifact:
- `docs`
- `tests`
- `command surface`
- `failure mode`
- `human approval boundary`
- `output artifact`
- `rollback path`
- `verification path`

## Artifact Schema

```json
{
  "kind": "builder_ii.deepagents_bridge_readiness_report",
  "schema_version": 1,
  "target_profile": "<string>",
  "agent_profile_compatibility_summary": "<string>",
  "optional_dependency_state": "<PRESENT | ABSENT | UNKNOWN>",
  "bridge_mode": "READINESS_ONLY",
  "disabled_capabilities": [
    "shell_execution",
    "source_writes",
    "runtime_execution",
    "model_execution",
    "delegation",
    "memory_mutation"
  ],
  "required_promotion_gates": [
    "docs",
    "tests",
    "command surface",
    "failure mode",
    "human approval boundary",
    "output artifact",
    "rollback path",
    "verification path"
  ],
  "readiness_verdict": "<READY_FOR_DRY_RUN_SPEC | BLOCKED_PENDING_HITL | NOT_READY>",
  "governance": {
    "capability_state": "bridge_readiness_report",
    "runtime_execution": "DISABLED",
    "model_execution": "DISABLED",
    "shell_execution": "DISABLED",
    "source_writes": "DISABLED",
    "memory_mutation": "DISABLED",
    "artifact_is_authority": false,
    "core_workbench_coupling": "NONE"
  }
}
```
