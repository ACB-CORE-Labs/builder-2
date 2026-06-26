# Goose runtime design spec

This document defines how builder-II treats Goose as the primary local runtime/operator while preserving builder-II governance.

This is a design specification only. It does not enable a runtime, construct agents, execute commands, mutate files, or grant tool authority.

## Identity boundary

```text
builder-II = governed platform/control plane
Goose      = primary local runtime/operator
deepagents = optional planning/subagent harness
target repo = generic / builder / core / research target / future targets
```

builder-II is not CORE, not CORE Workbench/UI, and not a second CORE runtime. CORE remains a target profile. Goose is not allowed to collapse these boundaries.

## Runtime goal

Goose should eventually provide the local operator loop that can inspect, plan, propose, verify, and later perform human-approved actions in target repositories.

builder-II owns the governance surface around that loop:

- target selection
- target profiles
- context packs
- agent profiles
- verification profiles
- target bundles
- research plans
- quality gates
- handoff artifacts
- approval boundaries
- runtime audit artifacts
- rollback and verification requirements

Goose may perform runtime work only after the relevant mode is explicitly promoted.

## Runtime modes

```text
disabled
read_only
command_proposal
verification_execution
patch_proposal
hitl_write
```

### disabled

Current default. No runtime session is started by this spec.

Allowed:

- render artifacts
- validate artifacts
- produce docs
- produce handoffs

Denied:

- Goose session start as a governed runtime
- command execution
- shell execution
- source mutation
- model execution through a bridge
- agent construction
- commit/push automation

### read_only

Future candidate mode. It may inspect files, repo tree, git status, docs, and artifacts.

Allowed only after promotion:

- read repository files
- inspect git status
- inspect target artifacts
- emit a runtime audit artifact
- emit planning and handoff artifacts

Denied:

- source writes
- arbitrary shell
- test execution
- commit/push
- notes vault mutation unless separately approved
- model/tool escalation beyond the configured runtime boundary

### command_proposal

Future candidate mode. It may propose commands as artifacts but may not execute them.

Allowed only after promotion:

- propose verification commands
- classify command risk
- bind proposed commands to quality gates
- require human approval before execution

Denied:

- executing proposed commands
- bypassing verification profiles
- hidden shell execution

### verification_execution

Future HITL-gated mode. It may execute approved verification commands only.

Allowed only after promotion:

- execute commands from an approved command proposal artifact
- capture output in an audit artifact
- fail closed on mismatched command, target, or approval hash

Denied:

- unapproved commands
- destructive commands
- source writes unless explicitly part of a later approved mode
- git push

### patch_proposal

Future candidate mode. It may produce patch proposals but may not apply them.

Allowed only after promotion:

- produce a proposed diff artifact
- explain changed files and risk
- bind the proposal to verification and rollback plans

Denied:

- applying patches
- committing patches
- pushing patches

### hitl_write

Future HITL-gated mode. It may apply approved patches.

Allowed only after promotion:

- apply an approved patch artifact
- run approved verification path if promoted
- emit postflight and runtime audit artifacts

Denied:

- autonomous writes by default
- direct commits or pushes without explicit approval
- bypassing quality gate or rollback requirements

## Goose session manifest

The next implementation step should introduce a Goose session manifest artifact. It should be created before any runtime session.

Required fields:

- artifact kind and schema version
- target profile
- task
- target repo path or identifier
- selected agent profile
- selected verification profile
- linked context pack path
- linked target bundle path
- linked quality gate path
- linked handoff path when present
- runtime mode
- allowed actions
- denied actions
- approval requirements
- expected audit artifact path

The manifest is evidence and configuration. It is not authority by itself.

## Runtime audit artifact

Every promoted runtime mode must emit an audit artifact.

Required fields:

- runtime mode
- target
- task
- session manifest hash or path
- start and end timestamps
- files read
- artifacts read
- commands proposed
- commands executed if any
- writes proposed
- writes applied if any
- denied action attempts
- approval events
- verification output references
- rollback references
- handoff reference

Audit artifacts are mandatory before any runtime mode can be considered complete.

## deepagents relationship

deepagents may later serve as an optional planning/subagent harness under builder-II governance.

Rules:

- deepagents remains optional
- no hard dependency before readiness is proven
- no direct writes through deepagents
- no direct shell through deepagents
- no bypassing Goose or builder-II approval gates
- no hidden agent authority
- no Deephaven changes

A future deepagents runtime spec may render subagent plans, but Goose remains the primary local runtime/operator.

## CORE target boundary

The `core` target profile may include CORE-specific principles, verification conventions, and repository guidance.

builder-II must not become CORE, CORE Workbench/UI, or a second CORE runtime. Any CORE-specific behavior belongs in the `core` target profile or a future explicit target adapter.

## Non-promotion statement

This document does not promote any runtime capability. It authorizes only future design and artifact work.

Before any mode moves beyond disabled/spec/artifact/validation state, it must satisfy the capability promotion rule: docs, tests, command surface, failure mode, human approval boundary, output artifact, rollback path, and verification path.
