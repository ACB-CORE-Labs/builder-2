# deepagents bridge

The bridge renders builder-II agent profiles into deepagents-style subagent specs.

This is a specification layer only. It does not make deepagents a required dependency, run models, edit files, execute shell commands, or write notes.

## Commands

```bash
builder-bridge doctor
builder-bridge deepagents-smoke
builder-bridge deepagents-smoke --json
builder-bridge deepagents-smoke --output .builder/artifacts/deepagents-smoke.json
builder-bridge render patch_planner --target generic
builder-bridge render patch_planner --target builder
builder-bridge render verification_planner --target core
```

## Optional smoke

`builder-bridge doctor` and `builder-bridge deepagents-smoke` may inspect whether `deepagents` is importable and whether `create_deep_agent` is present.

These commands do not construct agents, run models, enable runtime execution, write files, execute shell commands, or promote deepagents to a required dependency.

### Readiness Artifact

You can generate a machine-readable JSON readiness report (readiness artifact) by running:

```bash
builder-bridge deepagents-smoke --json
builder-bridge deepagents-smoke --output .builder/artifacts/deepagents-smoke.json
```

- `--json` prints the JSON report to stdout.
- `--output PATH` writes the JSON report to the specified path, creating any parent directories as needed.
- Using both `--json --output PATH` prints the report and writes it to the file.
- The readiness artifact is a static readiness report showing import status and capability limits. It is NOT a runtime permission or execution artifact.


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

A later PR may add HITL-gated runtime behavior only after docs, tests, command surface, failure mode, human approval boundary, output artifact, rollback path, and verification path are in place. The first runtime step must be read-only.
