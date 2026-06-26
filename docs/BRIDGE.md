# deepagents bridge

The bridge renders builder-II agent profiles into deepagents-style subagent specs.

This is a specification layer only. It does not import deepagents as a required dependency, run models, edit files, execute shell commands, or write notes.

## Commands

```bash
builder-bridge doctor
builder-bridge render patch_planner --target generic
builder-bridge render patch_planner --target builder
builder-bridge render verification_planner --target core
```

## Boundary

Runtime is disabled by default.

Every bridge spec denies:

- `write_file`
- `edit_file`
- `execute_shell`
- `commit`
- `push`

Future runtime work must add HITL gates, smoke tests, docs, rollback path, and verification before any denied action can be promoted.

## Target separation

The bridge consumes explicit target profiles. CORE remains a target profile, not builder-II's platform identity. CORE Workbench/UI remains separate.

## Future path

A later PR may make deepagents an optional dependency after an import and construction audit. The first runtime step must be read-only.
