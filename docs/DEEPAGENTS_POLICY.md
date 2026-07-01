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

## Approved protocol lane

builder-II now has a bounded protocol proof lane for deepagents-style delegation:

```text
builder-deepagents execution-candidate
  -> builder-deepagents approve-candidate
  -> builder-deepagents run-approved
  -> builder-deepagents replay-run
  -> builder-deepagents evidence-bundle
```

The first backend is `protocol_fake`, a deterministic backend used to prove the governance surface. It writes only run artifacts: execution candidate, approval, run envelope, hash-chained events, replay report, event ledger, receipt, optional checkpoint, and evidence bundle.

This lane still denies native deepagents construction, native model invocation, direct tool execution, shell execution, source writes, git mutation, Goose activation, MCP calls, hidden memory, and CORE Workbench/UI coupling.

Structural validators check artifact shape and digest bindings only. They do not enforce approval expiry. Expiry is enforced at the runtime gate by `builder-deepagents run-approved` and `builder-deepagents resume-approved` before the bounded protocol lane can append events.

## Real backend readiness

The future `optional_deepagents` backend must pass a separate readiness gate before it can replace `protocol_fake`. Readiness is not a successful import alone. It must include:

- exported protocol version and factory compatibility;
- deterministic contract tests against the `DeepAgentsBackend` interface;
- schema-drift detection for backend outputs;
- denial probes for unexpected tools, model calls, shell, MCP, memory, and source writes;
- partial-failure fixtures for interrupted runs, malformed results, timeouts, and dependency absence;
- evidence that all model work routes through builder-II model call envelopes and receipts;
- replay proof showing state reconstruction from events without rerunning backend work.

The gate is represented by `builder_ii.deepagents_backend_readiness_gate` and produced with:

```text
builder-deepagents backend-readiness --capability-gates-passed --output <gate.json>
```

`builder-deepagents execution-candidate --backend-mode optional_deepagents` rejects candidate creation unless `--backend-readiness-gate <gate.json>` points to a structurally valid gate with `gate_state: PASS`. The runner re-reads that gate by path and digest before execution, emits the gate's denial probes as `action_denied` events, and still requires the normal candidate approval artifact. A stale, missing, or failing gate is a governed denial, not a fallback to hidden runtime authority.

The protocol adapter export is `builder_ii_run_protocol_subagent`. It may return proposal-only payloads, but it must not construct native deepagents agents, invoke models directly, call tools, execute shell, connect MCP, mutate memory, write source, or couple to CORE Workbench. Native deepagents construction and governed factory calls remain a separate future promotion.

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
