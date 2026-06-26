# Goose session manifests

Goose session manifests are governed JSON artifacts that describe a future Goose session before any runtime starts.

This surface is artifact-only. It does not start Goose, run commands, execute shell, construct agents, call models, or mutate source.

## Commands

```bash
builder-goose manifest --target builder --agent patch_planner --task "inspect repo state"
builder-goose manifest --target builder --agent patch_planner --mode read_only --task "inspect repo state" --output .builder/artifacts/goose-session.json
builder-goose validate .builder/artifacts/goose-session.json
```

Optional artifact links:

```bash
builder-goose manifest \
  --target builder \
  --agent patch_planner \
  --mode read_only \
  --task "inspect repo state" \
  --bundle .builder/artifacts/target-bundle.json \
  --verification .builder/artifacts/verification-profile.json \
  --quality-gate .builder/artifacts/quality-gate.json \
  --research-plan .builder/artifacts/research-plan.json \
  --handoff .builder/artifacts/handoff.json \
  --context-pack .builder/context-pack.md \
  --output .builder/artifacts/goose-session.json
```

Read-only candidate audit artifacts:

```bash
builder-goose readonly-audit \
  .builder/artifacts/goose-session.json \
  --output .builder/artifacts/goose-runtime-audit.json
builder-goose validate-audit .builder/artifacts/goose-runtime-audit.json
```

The `readonly-audit` command validates a read-only manifest and emits an audit artifact. It still does not start Goose, inspect repository files, inspect git status, read linked artifacts, execute commands, execute shell, call models, or mutate source.

Bounded read-only inspection artifacts:

```bash
builder-goose inspect-readonly \
  .builder/artifacts/goose-session.json \
  --read-file README.md \
  --output .builder/artifacts/goose-readonly-inspection.json
builder-goose validate-inspection .builder/artifacts/goose-readonly-inspection.json
```

The `inspect-readonly` command reads only explicit operator-requested relative file paths inside the target repository and records metadata, not contents. It still does not start Goose, inspect git status, read linked artifacts, execute commands, execute shell, call models, construct deepagents, or mutate source.

See `docs/GOOSE_READONLY.md` and `docs/GOOSE_INSPECTION.md`.

## Artifact contents

A Goose session manifest includes:

- `kind: builder_ii.goose_session_manifest`
- `schema_version: 1`
- task
- target profile and repo path
- agent profile
- default verification profile artifact
- requested future runtime mode
- current runtime state
- whether the manifest starts Goose
- linked artifact paths
- expected future audit artifact path
- allowed manifest-only actions
- denied runtime actions
- approval requirements
- governance boundary

## Runtime boundary

The manifest may describe a requested future mode such as `read_only`, but it does not activate that mode.

The manifest always records:

```text
current_runtime_state: DISABLED
manifest_starts_goose: false
runtime_execution: DISABLED
goose_runtime_start: DISABLED
```

Validated manifests are evidence and configuration. They are not authority.

## Denied actions

Goose session manifests deny:

- starting Goose as a governed runtime
- command execution
- shell execution
- source writes
- patch application
- memory mutation
- commits
- pushes
- pull request creation
- deepagents construction
- model calls

## Validation

`builder-goose validate PATH` checks:

- manifest kind and schema version
- valid target profile
- valid agent profile
- supported requested runtime mode
- runtime remains disabled
- manifest does not start Goose
- linked artifact object shape
- expected audit artifact path
- non-empty allowed actions, denied actions, and approval requirements
- required denied actions are present
- governance denies runtime, shell, command, source write, model, memory, commit, and agent-construction authority

`builder-goose validate-audit PATH` checks the read-only audit artifact shape and confirms that runtime authority remains disabled.

`builder-goose validate-inspection PATH` checks bounded read-only inspection records and confirms that file contents, shell, commands, models, writes, commits, pushes, PR creation, source collection, web search, MCP, git status, and linked target artifact reads remain denied.

## Relationship to later work

This is the first runtime-adjacent artifact surface after the Goose runtime spec.

Implemented surfaces:

- `builder-goose manifest`
- `builder-goose validate`
- `builder-goose readonly-audit`
- `builder-goose validate-audit`
- `builder-goose inspect-readonly`
- `builder-goose validate-inspection`

Future PRs may add:

- git status recording
- linked artifact read recording
- command proposal artifacts
- HITL approval artifacts

Those later capabilities still require explicit promotion. The manifest and audit artifacts alone never grant runtime authority.
