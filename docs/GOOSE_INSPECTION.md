# Goose bounded read-only inspection

This document defines the first actual bounded repository-file inspection surface for builder-II.

It is stacked after the read-only candidate audit surface. It still does not start Goose, inspect git status, read linked target artifacts, execute commands, execute shell, call models, construct deepagents, mutate memory, write source, apply patches, commit, push, open pull requests, collect sources, run web search, or run MCP tools.

## Purpose

The inspection surface proves builder-II can perform narrowly bounded read-only repository inspection while preserving the governance boundary.

It consumes a valid Goose session manifest whose `requested_runtime_mode` is `read_only`, then reads only explicit operator-requested relative file paths inside the manifest's target repository.

```text
Goose session manifest
→ validate manifest
→ inspect explicit relative repo file paths
→ emit read-only inspection audit artifact
→ validate inspection audit artifact
```

## Commands

Create a read-only session manifest:

```bash
builder-goose manifest \
  --target generic \
  --agent repo_mapper \
  --mode read_only \
  --task "inspect explicit files" \
  --generic-repo /path/to/target/repo \
  --output .builder/artifacts/goose-session.json
```

Inspect explicit file paths:

```bash
builder-goose inspect-readonly \
  .builder/artifacts/goose-session.json \
  --read-file README.md \
  --read-file pyproject.toml \
  --output .builder/artifacts/goose-readonly-inspection.json
```

Validate the inspection audit artifact:

```bash
builder-goose validate-inspection .builder/artifacts/goose-readonly-inspection.json
```

Omitting `--output` prints the audit JSON to stdout and writes no file.

## Path boundary

`--read-file` accepts only explicit relative repository file paths.

Denied paths include:

- absolute paths;
- empty paths;
- `.`;
- paths containing `..`;
- paths entering `.git`;
- missing paths;
- directories;
- files exceeding `--max-bytes`.

The default maximum read size is 65,536 bytes per file.

## Content boundary

The inspection audit does not record file contents.

For each inspected file, it records only:

- relative path;
- byte count;
- SHA-256 digest;
- line count;
- `content_recorded: false`.

This provides provenance and evidence without turning the audit artifact into a content dump.

## Audit artifact contents

A read-only inspection audit artifact records:

- `kind: builder_ii.goose_readonly_inspection_audit`
- `schema_version: 1`
- `runtime_mode: read_only`
- `capability_state: read_only_runtime_candidate`
- `current_runtime_state: CANDIDATE_INSPECTION`
- `runtime_started: false`
- `goose_process_started: false`
- manifest path and manifest metadata
- task, target, and agent profile copied from the manifest
- declared linked artifact paths
- expected and actual audit artifact paths
- timestamps for artifact creation only
- explicit requested repository paths
- repository file metadata for inspected files
- `repository_file_contents_recorded: false`
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

The inspection audit must record:

```text
runtime_execution: READ_ONLY_CANDIDATE_INSPECTION
repository_file_reads: ENABLED_FOR_EXPLICIT_OPERATOR_PATHS_ONLY
target_artifact_reads: DISABLED_IN_THIS_CANDIDATE
git_status_inspection: DISABLED_IN_THIS_CANDIDATE
artifact_is_authority: false
core_workbench_coupling: NONE
```

It must record disabled authority for:

- Goose runtime start;
- model execution;
- agent construction;
- deepagents construction;
- shell execution;
- command execution;
- source writes;
- memory mutation;
- commits and pushes;
- pull request creation;
- source collection;
- web search;
- MCP execution.

## What this still does not promote

This surface does not promote a full Goose runtime. It does not start Goose and does not let a model, agent, harness, or shell decide what to read.

It also does not yet provide:

- git status recording;
- linked artifact reading;
- recursive directory reading;
- glob expansion;
- command proposal;
- verification execution;
- patch proposal;
- source mutation.

Those require separate promotion steps.

## Non-promotion statement

A valid read-only inspection audit artifact is evidence, not authority. It proves only that builder-II inspected explicitly requested repository files within the target boundary and emitted an audit artifact while preserving all other denied runtime actions.
