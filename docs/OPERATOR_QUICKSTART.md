# Operator Quickstart

This guide shows the complete operator golden path lane for builder-II.

builder-II is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench, not CORE UI/UX, and not a second CORE runtime. CORE is only a target profile.

For the canonical taxonomy of operator commands and governance boundaries, see the [Operator Command Surface Index](COMMAND_AUTHORITY.md) and [Platform Completion Audit](PLATFORM_COMPLETION_AUDIT.md).

## Purpose

The B9 governed operator quickstart (golden path) gives an operator one coherent local demonstration of the platform state, next required sequence, and a deterministic map of the setup closure without parsing the underlying truth matrices manually.

This lane is artifact-first and human-governed. It derives entirely from the truth matrix, command authority, and actual local evidence.

## Golden Path

The golden path operates without starting runtimes, calling models, modifying the target repository, or claiming authority.

```bash
builder-platform status
builder-platform operator-status --output .builder/artifacts/operator-status.json
builder-platform next --output .builder/artifacts/operator-next.json
builder-platform golden-path --target builder --output-dir .builder/artifacts/b9-golden-path
builder-platform validate-golden-path .builder/artifacts/b9-golden-path/golden-path-report.json
```

## What the Golden Path Report Proves

The golden path report explicitly categorizes every platform capability as:
- `exercised`
- `validated_only`
- `skipped_disabled`
- `skipped_missing_evidence`
- `unavailable`
- `not_applicable`

It provides a no-mutation proof and an explicit summary of all disabled runtime authorities, ensuring complete operator transparency.

## Runtime Boundary

This quickstart lane does not:
- execute shell commands
- import or use subprocess
- activate Goose
- activate or delegate to deepagents
- execute model/runtime work
- write to the target repository
- touch Deephaven
- grant runtime authority
- claim autonomous writes
- invoke MCP or external tools
- use hidden memory or vector stores

## Human Responsibility

The operator must inspect the generated JSON artifacts, read the next suggested action, and manually initiate any subsequent execution layers or governed setup flows using the exact explicit commands recommended by the `operator-next` primitive.

Any future execution or source write remains strictly HITL-gated by the B1-B8 execution primitives.
