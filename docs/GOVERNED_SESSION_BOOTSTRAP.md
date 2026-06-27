# Governed Session Bootstrap

This guide shows the operator-grade path for starting a governed builder-II local development session.

builder-II is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench, not CORE UI/UX, and not a second CORE runtime. CORE is only a target profile.

## Purpose

The platform spine is now proven. This document explains the minimal practical path from a clean checkout to a governed session preparation package.

This bootstrap does not grant runtime authority. It does not execute target-repo work. It prepares artifacts that a human can inspect.

## Bootstrap chain

```text
target repo
-> target profile
-> session workflow plan
-> Goose read-only session plan
-> verification profile report
-> handoff note
-> optional deepagents readiness report
```

## Required operator decisions

Before preparing a session, the operator must choose:

- target repository path
- target profile: `generic`, `builder`, or `core`
- agent profile
- prompt profile
- verification profile
- output artifact directory

## Read-only preparation

The bootstrap path is read-only with respect to target-repo execution.

Allowed:

- inspect repository metadata
- resolve profiles
- render plans
- write explicit artifact files
- validate artifacts

Not allowed by default:

- shell execution against the target repo
- autonomous source writes
- model/runtime execution
- deepagents delegation
- Goose activation
- Deephaven changes
- hidden authority escalation

## Example: builder-II self-development session

```bash
builder-session plan \
  --target builder \
  --repo . \
  --agent patch_planner \
  --mode read_only \
  --task "prepare governed builder-II development session" \
  --output .builder/artifacts/session-workflow.json
```

```bash
builder-session validate .builder/artifacts/session-workflow.json
```

```bash
builder-session goose-readonly-plan \
  --session-plan .builder/artifacts/session-workflow.json \
  --output .builder/artifacts/goose-readonly-session.json
```

```bash
builder-session validate-goose-readonly-plan .builder/artifacts/goose-readonly-session.json
```

## Verification report

A verification profile report records planned verification. It must not claim checks passed unless checks were actually run and evidenced.

The report is a planning artifact, not proof of successful execution.

## Handoff note

A governed handoff note summarizes the session state and references relevant artifacts.

Handoff notes are summary artifacts. They do not execute commands and do not become authority.

## Optional deepagents readiness

A deepagents bridge readiness report may describe whether optional future integration is ready for dry-run/spec use.

It must remain optional.

It must not:

- make deepagents a hard dependency
- import deepagents at module import time
- execute commands
- delegate to agents
- grant runtime authority

## Completion criteria

A bootstrap is complete when:

- all generated artifacts validate
- the operator can inspect every artifact path
- no runtime authority has been granted
- any future execution remains HITL-gated
- the target profile remains explicit
- CORE-specific behavior is scoped to the `core` target profile only
