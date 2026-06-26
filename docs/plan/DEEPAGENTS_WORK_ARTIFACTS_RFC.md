# deepagents work artifacts RFC

Status: design-only RFC.

This document defines how builder-II may represent deepagents-style planning work as governed artifacts before any deepagents runtime construction exists.

It does not add deepagents as a hard dependency, construct subagents, execute tools, call models, run shell, write files, or grant runtime authority.

## Purpose

deepagents may eventually help with planning, delegation, HITL gates, filesystem/backend abstractions, memory routes, LangGraph execution patterns, and optional MCP wiring.

builder-II must first define the work artifacts such a harness may produce. Artifacts come before runtime behavior.

```text
intent
→ governed plan artifact
→ subagent assignment artifacts
→ subagent result artifacts
→ review artifacts
→ human gate artifacts
→ handoff artifacts
```

## Governance rule

Builder-II governance is sovereign.

deepagents may only ever operate under:

- target profiles;
- agent profiles;
- verification profiles;
- quality gates;
- approval artifacts;
- audit artifacts;
- rollback requirements;
- verification requirements.

If deepagents is used inside a Goose-governed runtime mode, it must also respect that Goose runtime boundary.

## Non-goals

This RFC does not authorize:

- installing or importing deepagents as a required dependency;
- constructing actual deepagents agents;
- autonomous file writes;
- shell execution;
- command execution;
- model calls;
- MCP execution;
- source collection;
- web search;
- memory mutation;
- commits, pushes, or PR creation;
- bypassing builder-II governance;
- bypassing Goose runtime boundaries when Goose is involved;
- changes to excluded integration areas.

## Work artifact types

### `deepagents_plan`

A high-level plan for decomposing work.

Required fields:

```json
{
  "kind": "builder_ii.deepagents_plan",
  "schema_version": 1,
  "target_profile": "builder",
  "task": "inspect linked artifacts",
  "planner_agent_profile": "context_planner",
  "mode": "artifact_only",
  "subagent_assignments": [],
  "denied_actions": [],
  "required_human_gates": [],
  "required_verification": [],
  "artifact_is_authority": false
}
```

### `subagent_assignment`

A proposed work unit for a named subagent profile.

Required fields:

```json
{
  "kind": "builder_ii.subagent_assignment",
  "schema_version": 1,
  "target_profile": "builder",
  "subagent_profile": "repo_mapper",
  "task": "map files relevant to Goose audit artifacts",
  "inputs": [],
  "expected_outputs": [],
  "declared_authority": "read_only_planning_artifact",
  "denied_actions": [],
  "verification_required": [],
  "artifact_is_authority": false
}
```

### `subagent_result`

A result artifact representing what a subagent would report. Before runtime construction, this is an operator/model-authored artifact only.

Required fields:

```json
{
  "kind": "builder_ii.subagent_result",
  "schema_version": 1,
  "assignment_ref": ".builder/artifacts/subagent-assignment.json",
  "target_profile": "builder",
  "subagent_profile": "repo_mapper",
  "summary": "...",
  "evidence_refs": [],
  "open_questions": [],
  "blocked_actions": [],
  "claim_boundary": "proposal_only",
  "artifact_is_authority": false
}
```

### `subagent_review`

A review artifact for checking subagent outputs against governance boundaries.

Required fields:

```json
{
  "kind": "builder_ii.subagent_review",
  "schema_version": 1,
  "reviewed_result_refs": [],
  "target_profile": "builder",
  "reviewer_profile": "code_reviewer",
  "findings": [],
  "blocking_errors": [],
  "promotion_blockers": [],
  "artifact_is_authority": false
}
```

### `human_gate_request`

A request for human approval. It does not imply approval.

Required fields:

```json
{
  "kind": "builder_ii.human_gate_request",
  "schema_version": 1,
  "target_profile": "builder",
  "requested_action": "execute_verification_command",
  "risk_class": "read_only_command",
  "reason": "...",
  "required_approver": "operator",
  "approval_granted": false,
  "artifact_is_authority": false
}
```

### `blocked_action_record`

A record that an action was considered but denied by policy.

Required fields:

```json
{
  "kind": "builder_ii.blocked_action_record",
  "schema_version": 1,
  "target_profile": "builder",
  "requested_action": "execute_shell",
  "blocked_reason": "shell execution is not promoted",
  "policy_ref": "docs/RUNTIME_PROMOTION.md",
  "artifact_is_authority": false
}
```

## Required common fields

Every deepagents work artifact should include:

- `kind`;
- `schema_version`;
- `target_profile`;
- `task` or action statement;
- relevant agent/subagent profile;
- input artifact refs;
- output artifact refs;
- declared authority;
- denied actions;
- claim boundary;
- required verification;
- rollback or no-mutation statement;
- `artifact_is_authority: false`.

## Initial profile mapping

| Profile | Role in deepagents artifact design |
| --- | --- |
| `repo_mapper` | Propose repo-map tasks and file/path evidence requirements. |
| `context_planner` | Plan context packs and reconstruction artifacts. |
| `code_reviewer` | Review proposed artifacts and governance violations. |
| `patch_planner` | Plan patches as proposals only. |
| `verification_planner` | Plan verification commands without executing them. |
| `handoff_scribe` | Produce handoff artifacts from reviewed evidence. |

Future target-specific profiles may extend these only inside the relevant target profile.

## Future command surfaces

Possible future commands, after this RFC:

```bash
builder-deepagents plan \
  --target builder \
  --agent context_planner \
  --task "prepare linked artifact inspection" \
  --output .builder/artifacts/deepagents-plan.json

builder-deepagents validate .builder/artifacts/deepagents-plan.json

builder-deepagents assignment \
  --plan .builder/artifacts/deepagents-plan.json \
  --subagent repo_mapper \
  --output .builder/artifacts/subagent-assignment.json
```

These should be artifact-only at first.

## Promotion path

1. RFC only.
2. Schema and validators.
3. Artifact rendering commands.
4. Optional dependency readiness smoke.
5. Read-only runtime candidate only after audit artifacts, denied-action tests, and HITL boundaries exist.

## Acceptance criteria for first implementation

A future implementation PR must prove:

- artifacts validate;
- invalid authority claims fail closed;
- denied actions are required;
- artifacts do not construct deepagents;
- artifacts do not grant runtime authority;
- deepagents remains optional;
- builder-II remains generic-first;
- CORE remains a target profile.
