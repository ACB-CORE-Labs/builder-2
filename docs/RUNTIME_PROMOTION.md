# Runtime promotion contract

builder-II runtime behavior must be promoted deliberately. Code existence, imported dependencies, rendered profiles, valid artifacts, Goose availability, or deepagents availability do not grant runtime authority.

This document defines the gates required before Goose, deepagents, command execution, patch application, model routing, source collection, repository file reads, git status inspection, linked target artifact reads, or any other runtime behavior may move beyond disabled/spec/artifact/validation/candidate state.

## Promotion states

Runtime-related capabilities follow the existing capability promotion ladder:

```text
unavailable
spec_only
smoke_only
artifact_only
validation_only
read_only_runtime_candidate
hitl_runtime_candidate
enabled
```

## Required promotion gates

A runtime capability can become enabled only when it has all of the following:

- docs
- tests
- command surface
- failure mode
- human approval boundary
- output artifact
- rollback path
- verification path

Missing any item keeps the capability below enabled.

## Runtime-specific gates

Runtime promotion additionally requires:

- explicit runtime mode
- denied-action tests
- audit artifact schema
- session manifest schema when Goose is involved
- approval artifact schema when actions are gated
- target profile compatibility check
- agent profile compatibility check
- verification profile compatibility check
- quality gate compatibility check
- rollback requirement check
- no hidden writes test
- no hidden shell test
- no hidden model/tool escalation test
- clear recovery path after interruption

## Mode promotion checklist

### read_only

Current state: `read_only_runtime_candidate`.

Implemented candidate surfaces:

- `docs/GOOSE_READONLY.md`
- `builder-goose readonly-audit`
- `builder-goose validate-audit`
- read-only audit artifact schema
- denied-action tests proving the audit candidate does not start Goose, read repository files, inspect git status, read linked target artifacts, execute commands, execute shell, call models, construct deepagents, mutate memory, write source, commit, push, open pull requests, collect sources, run web search, or run MCP tools
- `docs/GOOSE_INSPECTION.md`
- `builder-goose inspect-readonly`
- `builder-goose validate-inspection`
- bounded read-only inspection artifact schema
- explicit operator-requested relative repository file reads
- file metadata recording without file content recording
- denied-action tests proving bounded inspection does not start Goose, inspect git status, read linked target artifacts, execute commands, execute shell, call models, construct deepagents, mutate memory, write source, commit, push, open pull requests, collect sources, run web search, or run MCP tools

Required before richer read-only runtime inspection is enabled:

- git status recording
- linked artifact read recording
- optional target-boundary expansion beyond explicit files, if needed
- no-write enforcement tests
- no-shell enforcement tests
- no-command-execution enforcement tests
- no-model-call enforcement tests
- denied action failure mode
- handoff artifact output path
- interruption recovery behavior

Must remain denied:

- source writes
- command execution
- commit/push
- arbitrary shell
- model/tool escalation
- runtime memory mutation unless separately approved

### command_proposal

Required before promotion:

- command proposal artifact
- command risk classification
- approval boundary
- quality gate binding
- target and verification profile binding
- invalid-command denial tests

Must remain denied:

- command execution
- shell execution outside proposal rendering
- destructive command approval by default

### verification_execution

Required before promotion:

- approved command artifact
- exact command matching
- approved target matching
- output capture artifact
- timeout and failure behavior
- rollback/no-mutation statement for verification commands

Must remain denied:

- unapproved command execution
- command mutation after approval
- git push
- destructive filesystem operations

### patch_proposal

Required before promotion:

- patch proposal artifact
- changed-file list
- risk explanation
- rollback plan
- verification plan
- human approval boundary

Must remain denied:

- patch application
- commit/push
- hidden source writes

### hitl_write

Required before promotion:

- approved patch artifact
- exact patch matching
- apply audit artifact
- verification after apply
- rollback command or revert path
- postflight handoff

Must remain denied:

- autonomous writes by default
- unapproved writes
- unapproved commits
- unapproved pushes

### model_routing

Required before promotion:

- model routing policy artifact
- allowed and forbidden model lane lists
- local-first and frontier-escalation rules
- privacy/cost approval boundary
- audit artifact for model selection and execution
- fallback behavior
- no-hidden-call tests

Must remain denied:

- hidden external model calls
- silent cost-bearing execution
- frontier escalation without approval
- treating model output as authority without verification

## Governance boundary

Builder-II governance is the sovereign boundary.

No runtime, harness, model, bridge, artifact, target profile, or dependency may bypass:

- target profiles
- agent profiles
- verification profiles
- quality gates
- approval artifacts
- audit artifacts
- rollback requirements
- verification requirements

## Goose boundary

Goose is the preferred local runtime/operator after explicit promotion, but builder-II governs when and how Goose may operate.

Goose must not:

- bypass builder-II governance
- bypass target profiles
- bypass agent profiles
- bypass verification profiles
- bypass quality gates
- bypass approvals
- mutate target repos without approved mode
- conflate builder-II with CORE Workbench/UI

## deepagents boundary

deepagents is optional and subordinate to builder-II governance.

deepagents must not:

- become a hard dependency before promotion
- execute tools directly outside approved runtime mode
- write files directly
- execute shell directly
- bypass builder-II governance
- bypass approval artifacts
- bypass audit artifacts
- change Deephaven-related work

If deepagents is used inside a Goose-governed runtime mode, it must also respect that runtime boundary. The fundamental invariant is no bypass of builder-II governance.

## Artifact authority rule

Validated artifacts are evidence, not authority. Authority requires a promoted runtime mode plus the required approval boundary for that mode.

A valid artifact alone never authorizes:

- model execution
- agent construction
- command execution
- shell execution
- source mutation
- memory mutation
- commit/push
- pull request creation
- source collection
- MCP execution
- web/search execution
- Goose runtime start
- deepagents construction
- arbitrary repository file reads
- repository file content recording
- git status inspection as runtime behavior
- linked target artifact reads as runtime behavior

## Rollback requirement

Every promoted runtime mode must define rollback behavior before it can run.

Examples:

- read-only candidate audit rollback: delete the emitted audit artifact; no source rollback is needed because no runtime inspection or mutation occurs
- bounded read-only inspection rollback: delete the emitted inspection audit artifact; no source rollback is needed because no mutation occurs and file contents are not recorded
- read-only mode rollback: no source rollback needed, but audit and handoff must record interruption state
- command proposal rollback: discard proposal artifact
- verification execution rollback: no source rollback expected; record command output and failure state
- patch proposal rollback: discard proposal artifact
- hitl write rollback: revert patch or restore pre-apply state
- model routing rollback: discard routing artifact and record no execution if no model call was approved

## Verification requirement

Every promoted runtime mode must define how it is verified.

Examples:

- unit tests for artifact validation
- CLI smoke tests
- denied-action tests
- target compatibility tests
- audit artifact validation
- postflight checks
- no-hidden-model-call tests

## Non-promotion statement

This document is itself `spec_only`. It does not enable any runtime mode.

The current platform remains artifact-first. Bounded read-only inspection is a candidate surface that reads only explicit operator-requested relative file paths and records metadata without contents. Goose runtime start, git status inspection, linked target artifact reads, shell, commands, models, deepagents, source mutation, patch application, rollback execution, memory mutation, commits, pushes, pull requests, source collection, web search, and MCP remain unpromoted.
