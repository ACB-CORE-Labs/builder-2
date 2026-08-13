# Deepagents dependency-readiness artifacts

Status: passive readiness artifact for the separately approved native runtime lane.

builder-II can record whether the optional `deepagents` dependency appears available in the local environment without constructing an agent or granting runtime authority.

This sits between the policy artifact and the native runtime adapter:

```text
builder-II governed policy artifact
  -> dependency-readiness artifact
  -> digest-bound candidate and human approval
  -> Builder-II native runtime adapter
```

## Modes

### `metadata_only`

Default. Renders an artifact with the expected package/module/export contract but does not check the Python environment.

```bash
builder-deepagents readiness \
  --mode metadata_only \
  --output .builder/artifacts/deepagents-readiness.json
```

### `import_check`

Checks Python import metadata for the `deepagents` package/module and official `create_deep_agent` export. It does not construct an agent, invoke tools, call models, or start runtime behavior.

```bash
builder-deepagents readiness \
  --mode import_check \
  --output .builder/artifacts/deepagents-readiness.json
```

Validate:

```bash
builder-deepagents validate-readiness .builder/artifacts/deepagents-readiness.json
```

## What the artifact records

- expected package name;
- expected module name;
- expected official factory name;
- expected exports;
- observed dependency state;
- observed module availability;
- observed package version, when available;
- observed export availability;
- denied runtime actions;
- governance state.

## Boundary

The artifact denies:

- agent construction;
- official factory calls;
- runtime start;
- subagent invocation;
- model calls;
- command and shell execution;
- repository reads as runtime;
- source writes and patch application;
- memory mutation;
- MCP connections.

Even when `mode=import_check` reports `available`, the readiness artifact is not runtime authority.

## Non-goals

This artifact does not:

- make `deepagents` a hard dependency;
- install dependencies;
- import builder-II into deepagents;
- construct an agent;
- start Goose;
- invoke subagents;
- inspect target repositories;
- persist memory;
- connect to MCP;
- call a model;
- couple builder-II to CORE Workbench/UI.

## Promotion path

The native runtime caller still requires:

- a passing backend-readiness gate for `deepagents>=0.6.12,<0.7.0`;
- a candidate bound to model registry/policy and a sealed WRP obligation envelope;
- digest-bound approval plus `--native-backend-acknowledged`;
- `builder-deepagents run-approved` with at least two obligation paths; and
- exact-checkpoint approval for `resume-approved`.

See [`architecture/NATIVE_DEEPAGENTS_RUNTIME.md`](architecture/NATIVE_DEEPAGENTS_RUNTIME.md). The readiness artifact remains non-authoritative even though the separately approved caller is implemented.
