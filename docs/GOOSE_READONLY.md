# Goose read-only runtime candidate

This document defines the first read-only runtime candidate surface for builder-II.

It is still not a Goose runtime start. It does not start Goose, inspect repository files, inspect git status, read linked target artifacts, execute commands, execute shell, call models, construct deepagents, mutate memory, write source, apply patches, commit, push, open pull requests, collect sources, run web search, or run MCP tools.

## Purpose

The read-only candidate introduces the runtime audit artifact shape before any runtime authority exists.

The candidate consumes a valid Goose session manifest whose `requested_runtime_mode` is `read_only` and emits a read-only audit artifact that proves the current boundary is still disabled.

```text
Goose session manifest
→ validate manifest
→ emit read-only candidate audit artifact
→ validate audit artifact
```

## Commands

Create a read-only session manifest:

```bash
builder-goose manifest \
  --target builder \
  --agent patch_planner \
  --mode read_only \
  --task "inspect repo state" \
  --output .builder/artifacts/goose-session.json
```

Emit a candidate audit artifact:

```bash
builder-goose readonly-audit \
  .builder/artifacts/goose-session.json \
  --output .builder/artifacts/goose-runtime-audit.json
```

Validate the audit artifact:

```bash
builder-goose validate-audit .builder/artifacts/goose-runtime-audit.json
```

Omitting `--output` prints the audit JSON to stdout and writes no file.

## Audit artifact contents

A read-only candidate audit artifact records:

- `kind: builder_ii.goose_readonly_runtime_audit`
- `schema_version: 1`
- `runtime_mode: read_only`
- `capability_state: read_only_runtime_candidate`
- `current_runtime_state: DISABLED`
- `runtime_started: false`
- `goose_process_started: false`
- manifest path and manifest metadata
- task, target, and agent profile copied from the manifest
- declared linked artifact paths
- expected and actual audit artifact paths
- timestamps for artifact creation only
- actions performed by the candidate command
- denied runtime actions
- manifest file read as the only input file
- empty repository file reads
- empty target artifact reads
- empty git status inspection
- empty command execution
- empty shell execution
- empty source writes
- empty patch application
- empty model calls
- no deepagents construction
- rollback reference for deleting the artifact
- governance boundary

## Governance boundary

The audit artifact must record disabled authority for:

- runtime execution
- Goose runtime start
- model execution
- agent construction
- deepagents construction
- shell execution
- command execution
- source writes
- memory mutation
- commits and pushes
- pull request creation
- source collection
- web search
- MCP execution

It must also record:

```text
repository_file_reads: DISABLED_IN_THIS_CANDIDATE_ARTIFACT
target_artifact_reads: DISABLED_IN_THIS_CANDIDATE_ARTIFACT
artifact_is_authority: false
core_workbench_coupling: NONE
```

## Why repository reads remain disabled here

The mature `read_only` runtime mode may eventually inspect repository files and git status after explicit promotion.

This candidate does not do that yet. It validates the manifest-to-audit path first so the audit schema, CLI surface, denied-action tests, and non-authority rule are in place before real read-only inspection is introduced.

## Relationship to bounded inspection

The next inspection surface is documented in `docs/GOOSE_INSPECTION.md`. It allows only explicit operator-requested relative repository file paths and records metadata, not contents.

That later surface still does not start Goose, inspect git status, read linked target artifacts, execute commands, execute shell, call models, construct deepagents, or mutate source.

## Promotion posture

This surface is a `read_only_runtime_candidate`, not an enabled runtime.

A future PR may add actual read-only inspection only after it provides:

- target-boundary rules or file-read allowlists;
- repository file read recording;
- git status recording;
- linked artifact read recording;
- denied-action tests for writes, shell, commands, models, and tool escalation;
- interruption recovery behavior;
- handoff behavior;
- documentation and verification paths.

## Non-promotion statement

A valid read-only audit artifact is evidence, not authority. It proves only that the candidate command validated a read-only Goose session manifest and emitted an audit artifact while keeping runtime authority disabled.
