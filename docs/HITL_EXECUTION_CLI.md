# HITL Execution Artifact CLI (`builder-hitl`)

## Overview

The `builder-hitl` CLI command surface provides tools to generate, inspect, and validate governance artifacts for the Human-in-the-Loop (HITL) execution path.

> [!IMPORTANT]
> **This CLI creates governance artifacts only. It does not execute commands and it does not grant authority.**
> - A valid execution request is NOT permission to execute.
> - A `NOT_EXECUTED` receipt is a template/record, NOT evidence that execution occurred.

## Platform Identity & Scope

builder-II is a generic governed local agent/developer platform.
builder-II is not CORE, not CORE Workbench/UI/UX, and not a second CORE runtime.
CORE is only a target profile.

---

## Command Surface

### `builder-hitl request`

Creates a HITL execution request artifact (`builder_ii.hitl_execution_request`).

**Usage:**
```bash
builder-hitl request \
  --target-name <target> \
  --command-proposal-ref <proposal-ref> \
  --approval-record-ref <approval-ref> \
  --preflight-record-ref <preflight-ref> \
  --requested-by <user> \
  --requested-at <timestamp> \
  --explicit-operator-intent <intent> \
  --command-preview <command> \
  --output <output-path>
```

- Accepts target profile name (`generic`, `builder`, `core`).
- Validates the artifact constraints before writing the output path.
- Automatically creates parent directories for the declared output path.
- Writes the formatted JSON artifact.

### `builder-hitl receipt`

Creates a template `NOT_EXECUTED` receipt artifact (`builder_ii.hitl_execution_receipt`).

**Usage:**
```bash
builder-hitl receipt \
  --target-name <target> \
  --request-ref <request-ref> \
  --output <output-path>
```

- Generates an execution receipt indicating no execution occurred (`NOT_EXECUTED`).
- Validates the artifact constraints before writing the output path.
- Automatically creates parent directories for the declared output path.
- Writes the formatted JSON artifact.

### `builder-hitl validate`

Validates a local JSON artifact file against request or receipt schemas by kind.

**Usage:**
```bash
builder-hitl validate <path-to-artifact.json>
```

- Inspects the artifact's `kind` field.
- Routes to the appropriate validation logic.
- Unknown or unsupported artifact kinds fail closed.
- Exits with a non-zero code on invalid artifacts and prints errors.
