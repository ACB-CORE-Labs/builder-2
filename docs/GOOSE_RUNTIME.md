# Goose runtime design spec

This document defines how builder-II treats Goose as the preferred local runtime/operator while preserving builder-II governance.

This is a design specification only. It does not enable a runtime, construct agents, execute commands, mutate files, call models, or grant tool authority.

## Identity boundary

```text
builder-II = governed platform/control plane
Goose      = preferred local runtime/operator after explicit promotion
deepagents = optional planning/subagent harness
target repo = generic / builder / core / research target / future targets
```

builder-II is not CORE, not CORE Workbench/UI, and not a second CORE runtime. CORE remains a target profile. Goose is not allowed to collapse these boundaries.

Builder-II governance is the sovereign boundary. Goose may operate only inside a promoted runtime mode with explicit approval, audit, rollback, and verification requirements.

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
- model routing policy

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

Current default. No runtime session is started by this spec, by a Goose session manifest, or by a read-only candidate audit artifact.

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

Candidate mode. The current implemented surface validates a read-only Goose session manifest and emits a read-only runtime candidate audit artifact.

Implemented candidate surfaces:

- `docs/GOOSE_READONLY.md`
- `builder-goose readonly-audit`
- `builder-goose validate-audit`

Current candidate behavior:

- validates an existing Goose session manifest
- requires `requested_runtime_mode: read_only`
- emits a runtime audit artifact
- records that no Goose process started
- records that no repository files were read
- records that no git status inspection happened
- records that no linked target artifacts were read
- records that no commands, shell, model calls, writes, commits, pushes, pull requests, MCP, web search, or source collection occurred

Allowed only after future promotion:

- read repository files inside target-boundary rules
- inspect git status
- inspect target artifacts
- emit planning and handoff artifacts from actual inspection

Denied:

- source writes
- arbitrary shell
- test execution unless a later approved verification mode permits it
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

The governed MCP surface admits passive `patch_proposal` planning. Through the canonical
governed Goose recipe it may persist Builder-II-owned proposal, policy, service-receipt, and
event evidence beneath the configured `platform_artifact_root`; it may not edit target source,
mint approval, or apply a patch.

Allowed:

- produce a proposed diff artifact
- explain changed files and risk
- bind exact diff and verification-receipt bytes to the configured target
- stop at `HUMAN_APPROVAL_REQUIRED`

Denied:

- applying patches
- minting or inferring approval
- shell, generic file writes, rollback, or Git mutation
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

Goose session manifests are the first runtime-adjacent artifact surface after this spec. They describe a future Goose session before any runtime starts.

Implemented surfaces:

- `docs/GOOSE_SESSION.md`
- `builder-goose manifest`
- `builder-goose validate`

A session manifest records:

- artifact kind and schema version
- target profile
- task
- target repo path or identifier
- selected agent profile
- selected verification profile
- linked context pack path when provided
- linked target bundle path when provided
- linked quality gate path when provided
- linked research plan path when provided
- linked handoff path when provided
- requested runtime mode
- current runtime state
- whether the manifest starts Goose
- allowed manifest-only actions
- denied runtime actions
- approval requirements
- expected audit artifact path

The manifest is evidence and configuration. It is not authority by itself. A valid manifest does not start Goose.

## Runtime audit artifact

Every promoted runtime mode must emit an audit artifact.

The current read-only candidate audit artifact is an early audit-surface implementation. It proves only that builder-II can validate a read-only manifest and emit an audit record while runtime authority remains disabled.

Required audit fields include:

- runtime mode
- target
- task
- session manifest path
- timestamps
- files read
- repository files read
- target artifacts read
- git status inspection state
- commands proposed
- commands executed if any
- writes proposed
- writes applied if any
- denied action attempts
- approval events
- verification output references
- rollback references
- handoff reference
- governance boundary

Audit artifacts are mandatory before any runtime mode can be considered complete.

## deepagents relationship

deepagents may later serve as an optional planning/subagent harness under builder-II governance.

Rules:

- deepagents remains optional
- no hard dependency before readiness is proven
- no direct writes through deepagents
- no direct shell through deepagents
- no bypassing builder-II governance, approval artifacts, or audit artifacts
- if used inside a Goose-governed runtime mode, no bypassing that runtime boundary
- no hidden agent authority
- no Deephaven changes

A future deepagents runtime spec may render subagent plans, but deepagents remains subordinate to builder-II governance.

## CORE target boundary

The `core` target profile may include CORE-specific principles, verification conventions, and repository guidance.

builder-II must not become CORE, CORE Workbench/UI, or a second CORE runtime. Any CORE-specific behavior belongs in the `core` target profile or a future explicit target adapter.

## Non-promotion statement

This document does not promote any runtime capability. It authorizes only future design and artifact work.

The current read-only audit artifact does not promote actual read-only repository inspection. Before any mode moves beyond disabled/spec/artifact/validation state, it must satisfy the capability promotion rule: docs, tests, command surface, failure mode, human approval boundary, output artifact, rollback path, and verification path.
