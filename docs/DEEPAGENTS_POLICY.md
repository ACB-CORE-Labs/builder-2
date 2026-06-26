# Governed deepagents policy artifacts

Status: artifact-only.

builder-II treats deepagents as an optional harness, not as platform authority. A governed deepagents policy artifact records how a future deepagents session should be configured, but it does not construct deepagents, call a model, start a runtime, read repository files, or invoke tools.

## Create a policy artifact

```bash
builder-deepagents policy \
  --target builder \
  --task "render governed deepagents configuration" \
  --output .builder/artifacts/deepagents-policy.json
```

Print to stdout instead of writing:

```bash
builder-deepagents policy --target builder --task "inspect policy"
```

Validate an artifact:

```bash
builder-deepagents validate .builder/artifacts/deepagents-policy.json
```

## What the artifact records

The artifact records:

- target profile binding;
- future governed factory name;
- root binding policy;
- allowed and denied tool names;
- memory policy mode;
- memory path prefixes;
- subagent result mode;
- expected future audit artifact path;
- allowed artifact-rendering actions;
- denied runtime/tool/model actions;
- approval requirements;
- governance state.

## Default posture

Defaults are conservative:

```text
policy_mode = artifact_only
current_runtime_state = DISABLED
policy_constructs_deepagents = false
memory_mode = proposal_only
subagent_result_mode = proposal_only
root_binding = target.repo
```

The artifact denies:

- deepagents construction;
- governed factory calls;
- runtime start;
- subagent invocation;
- repository reads as runtime;
- command and shell execution;
- source writes and patch application;
- memory mutation;
- MCP connections;
- model calls.

## Why this comes before runtime

The deepagents fork now has generic governed seams, including read-only filesystem access, tool policy, audit events, proposal-only subagent results, memory policy, and an opt-in governed factory. builder-II still must not jump directly to runtime behavior.

This artifact is the bridge:

```text
builder-II policy artifact
  -> future Goose/runtime approval boundary
  -> future deepagents governed factory construction
  -> future audit event artifact
```

## Non-goals

This artifact does not:

- import deepagents;
- construct an agent;
- start Goose;
- start a runtime;
- inspect target files;
- execute commands;
- apply patches;
- mutate memory;
- connect to MCP;
- call a model;
- couple builder-II to CORE Workbench/UI.

## Promotion requirement

A future deepagents runtime mode can only be promoted when it has:

- docs;
- tests;
- command surface;
- failure mode;
- human approval boundary;
- output artifact;
- rollback path;
- verification path.
