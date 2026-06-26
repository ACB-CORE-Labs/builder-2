# Deepagents dependency-readiness artifacts

Status: readiness artifact only.

builder-II can record whether the optional `deepagents` dependency appears available in the local environment without constructing an agent or granting runtime authority.

This sits between the policy artifact and any future runtime adapter:

```text
builder-II governed policy artifact
  -> dependency-readiness artifact
  -> future human approval boundary
  -> future runtime adapter
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

Checks Python import metadata for the `deepagents` package/module and expected exported names. It does not construct an agent, call `create_governed_deep_agent`, invoke tools, call models, or start runtime behavior.

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
- expected governed factory name;
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
- governed factory calls;
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

A future runtime adapter still requires:

- optional dependency policy;
- explicit command surface;
- human approval boundary;
- failure-mode handling;
- output audit artifact;
- rollback path;
- verification path.
