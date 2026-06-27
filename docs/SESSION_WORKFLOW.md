# Governed Local Session Workflow

The governed local session workflow compiles target, profile, context, prompt, and verification inputs into a deterministic, dry-run session plan artifact (`builder_ii.session_workflow_plan`). 

Under the hood, this process is managed by the unified profile resolution layer (see [PROFILE_RESOLUTION.md](file:///Users/kaizenpro/Projects/builder-II-worktrees/pr-ag-target-context-profile-resolution/docs/PROFILE_RESOLUTION.md)), which ensures all lookups, default selections, and compatibility checks are canonical, deterministic, and fail-closed.

This plan serves as inspectable evidence of intended operations before involving any local model or downstream operator tool. It is entirely read-only, carries no execution authority, and is decoupled from any active model or shell runtime.

## CLI Commands

```bash
# Generate a plan for a target (using deterministic profile defaults)
builder-session plan generic
builder-session plan builder
builder-session plan core

# Generate a plan with explicit overrides
builder-session plan core --agent code_reviewer --prompt core_default --verification core_smoke

# Write the plan to a JSON artifact file
builder-session plan builder --output .builder/session-plan.json

# Validate a plan file
builder-session validate .builder/session-plan.json
```

## Profiles and Resolution Defaults

When running `builder-session plan <target>`, the tool resolves default profiles deterministically:

| Target | Default Agent | Default Prompt | Default Verification |
| --- | --- | --- | --- |
| `generic` | `repo_mapper` | `generic_default` | `generic_basic` |
| `builder` | `context_planner` | `builder_default` | `builder_fast` |
| `core` | `code_reviewer` | `core_default` | `core_smoke` |

### Prompt Profiles

Prompt profiles define governed system instruction sets:

- `generic_default`: Standard software development focus.
- `builder_default`: Self-development focus emphasizing platform-safety constraints.
- `core_default`: Strict mathematical and coordinate algebra invariants (CGA, `versor_condition`).

## Plan Artifact Schema

A compiled session plan contains:

- `kind: builder_ii.session_workflow_plan`
- `schema_version: 1`
- `target_profile`: The resolved target profile details.
- `repo_path`: Metadata field indicating target repository root path.
- `selected_agent_profile`: The resolved agent profile.
- `selected_prompt_profile`: The resolved prompt profile.
- `selected_verification_profile`: The resolved verification profile.
- `planned_artifacts`: A list of output file paths planned for the session.
- `planned_commands`: Preview commands showing context packing, session execution, verification, and handoff.
- `governance`: Bounded governance block enforcing no execution privilege.

### Governance Boundaries

The plan artifact strictly disables all execution authority:

```json
"governance": {
  "capability_state": "session_workflow_plan",
  "runtime_execution": "DISABLED",
  "model_execution": "DISABLED",
  "shell_execution": "DISABLED",
  "source_writes": "DISABLED",
  "memory_mutation": "DISABLED",
  "artifact_is_authority": false,
  "core_workbench_coupling": "NONE"
}
```
No shell command, model call, or repository mutation is performed during plan generation or validation.
