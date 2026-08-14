# deepagents bridge

The bridge renders builder-II agent profiles into deepagents-style subagent specs.

This is a specification layer only. It does not make deepagents a required dependency, run models, edit files, execute shell commands, or write notes.

Capability promotion state for this bridge is tracked in [`CAPABILITY_PROMOTION.md`](CAPABILITY_PROMOTION.md).

## Commands

```bash
builder-bridge doctor
builder-bridge deepagents-smoke
builder-bridge deepagents-smoke --json
builder-bridge deepagents-smoke --output .builder/artifacts/deepagents-smoke.json
builder-bridge render patch_planner --target builder --format markdown
builder-bridge render patch_planner --target builder --format json
builder-bridge render patch_planner --target builder --output .builder/artifacts/bridge-spec.json --format json
builder-bridge validate-artifact .builder/artifacts/deepagents-smoke.json
builder-bridge validate-artifact .builder/artifacts/bridge-spec.json
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

### Dry-Run Bridge Spec Artifact

You can generate a dry-run bridge spec artifact (in JSON format) by running:

```bash
builder-bridge render patch_planner --target builder --format json --output .builder/artifacts/bridge-spec.json
```

- `--format FORMAT` specifies the output format: `markdown` (default) or `json`.
- `--output PATH` writes the formatted spec to the specified path, creating any parent directories as needed.
- If `--output` is not specified, it prints the spec directly to stdout (using raw stdout representation for JSON format).
- This is a dry-run bridge spec artifact and NOT a runtime/execution authorization.

### Artifact Validation

`builder-bridge validate-artifact PATH` validates builder-II bridge artifacts produced by the smoke and render commands.

Validation checks schema kind/version, disabled runtime state, optional dependency mode for smoke artifacts, and required denied tools for bridge spec artifacts.

This command only reads and validates JSON artifacts. It does not execute artifact contents, construct agents, run models, write files, execute shell commands, or treat artifacts as permission grants.

## Boundary

Runtime is disabled by default.

Every bridge spec denies:

- `write_file`
- `edit_file`
- `execute_shell`
- `commit`
- `push`

Current bridge work is capped at `validation_only`. Future runtime work must add HITL gates, smoke tests, docs, rollback path, and verification before any denied action can be promoted.

## Target separation

The bridge consumes explicit target profiles. CORE remains a target profile, not builder-II's platform identity. CORE Workbench/UI remains separate.

## Future path

A later PR may add HITL-gated runtime behavior only after docs, tests, command surface, failure mode, human approval boundary, output artifact, rollback path, and verification path are in place. The first runtime step must be read-only.
