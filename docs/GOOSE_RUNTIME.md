# Goose runtime design spec

This document defines how builder-II treats Goose as the preferred local runtime/operator while preserving builder-II governance.

This is a design specification only. It does not enable a runtime, construct agents, execute commands, mutate files, call models, or grant tool authority.

## Identity boundary

```text
builder-II = governed platform/control plane
Goose      = local runtime/operator adapter
deepagents = optional planning/subagent harness
target repo = generic / builder / core / research target / future targets
```

builder-II is not CORE, not CORE Workbench/UI, and not a second CORE runtime. CORE remains a target profile. Goose is not allowed to collapse these boundaries.

Builder-II is the governance boundary. Goose may operate only inside a governed manifest flow with explicit operator action, audit, rollback, and verification requirements. Builder-II represents, constrains, binds, and enforces authority; consequential human decisions originate with the operator.

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
