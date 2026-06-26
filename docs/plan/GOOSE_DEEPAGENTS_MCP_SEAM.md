# Goose × deepagents × MCP seam

Status: design-only RFC.

This document defines how builder-II should keep Goose, deepagents, and Model Context Protocol (MCP) integration composable without granting hidden runtime authority.

## Core posture

```text
builder-II governs.
Goose operates.
deepagents composes and delegates.
MCP connects external tools and context.
Artifacts prove.
Humans approve.
Verification closes.
```

Goose, deepagents, and MCP should not compete for authority. They occupy different layers:

| Layer | Responsibility |
| --- | --- |
| builder-II | Governance, artifacts, target profiles, approval, verification, audit, rollback. |
| Goose | Local operator/runtime envelope under builder-II policy. |
| deepagents | Optional planning/subagent/middleware harness inside approved runtime modes. |
| MCP | External tool/context/prompt connection surface, always policy-gated. |

## Non-goals

This RFC does not authorize:

- Goose runtime activation;
- deepagents construction;
- MCP server connection;
- MCP tool execution;
- source collection;
- web search;
- shell execution;
- command execution;
- source writes;
- patch application;
- memory mutation;
- model routing execution;
- sampling requests;
- autonomous subagent execution;
- CORE Workbench/UI coupling.

## MCP capability mapping

MCP separates server features from client features. Server-side features include resources, prompts, and tools. Client-side features include sampling, roots, and elicitation.

builder-II maps these as follows:

| MCP concept | Meaning | builder-II treatment |
| --- | --- | --- |
| Tools | Functions the model may invoke | Deny by default; require inventory, policy, approval, and audit. |
| Resources | Context/data exposed by servers | Treat as provenance-carrying context refs; never automatic truth. |
| Prompts | Server-provided templates/workflows | Treat as prompt-profile candidates; never instruction authority by default. |
| Roots | Filesystem or URI boundaries exposed by client | Derive only from target profiles and explicit artifact roots. |
| Sampling | Server-initiated LLM calls | Disabled by default; model-call authority requires separate promotion. |
| Elicitation | Server requests user input | Convert to human-gate or clarification artifacts. |
| Authorization | Protected server access | Store token refs only; never raw credentials in artifacts. |

## Goose role

Goose is the operator-facing runtime lane. It should:

- start only after a builder-II runtime policy says it may;
- consume builder-II session manifests and linked policy artifacts;
- present MCP/deepagents actions to the operator;
- surface human gates;
- record runtime decisions;
- write audit artifacts;
- never invent authority.

Goose may host deepagents only through an explicit `deepagents_policy` artifact linked from a Goose session manifest.

Goose may expose MCP only through an explicit `mcp_policy` artifact linked from a Goose session manifest.

Example future manifest links:

```json
{
  "links": {
    "deepagents_policy": ".builder/artifacts/deepagents-policy.json",
    "mcp_policy": ".builder/artifacts/mcp-policy.json",
    "mcp_inventory": ".builder/artifacts/mcp-inventory.json"
  }
}
```

## deepagents role

deepagents should remain an optional inner harness. It may eventually provide:

- TODO planning;
- context isolation;
- subagent delegation;
- restricted filesystem access;
- summarization/offloading;
- backend routing;
- event streams for audit;
- HITL middleware integration.

It must not:

- receive raw MCP tools without builder-II policy filtering;
- receive write/edit/execute tools by default;
- receive persistent memory write authority by default;
- spawn subagents outside declared policy;
- treat subagent output as authority;
- bypass Goose or builder-II approval.

## MCP role

MCP should be easy to integrate, but easy must mean:

- easy to inventory;
- easy to hash;
- easy to classify;
- easy to allowlist;
- easy to deny;
- easy to approve;
- easy to audit;
- easy to revoke.

MCP must not mean:

- arbitrary server tools automatically available to agents;
- trusted tool descriptions;
- trusted tool annotations;
- hidden sampling;
- hidden external requests;
- hidden source collection;
- hidden credential use.

## Required artifact chain

A governed MCP-enabled Goose/deepagents session should require:

```text
Goose session manifest
→ deepagents policy artifact
→ MCP server registry artifact
→ MCP inventory artifact
→ MCP policy artifact
→ approval artifact if any tool is sensitive
→ runtime audit artifact
→ handoff / verification artifact
```

No single artifact grants full authority. Each narrows a boundary.

## Modes

### Mode 0: docs/spec only

Current state. No runtime behavior.

### Mode 1: artifact-only planning

builder-II renders and validates deepagents/MCP policy artifacts. No Goose start, no deepagents construction, no MCP connection.

### Mode 2: MCP inventory only

builder-II connects to explicitly configured MCP servers only to list capabilities. No tool calls. No resource reads unless separately approved. Inventory output records tool/resource/prompt metadata and hashes.

### Mode 3: Goose read-only MCP mediation

Goose may present inventory and policy results to the operator. No MCP calls that mutate state or reach external systems unless approved.

### Mode 4: Goose-hosted deepagents with approved MCP tools

deepagents receives only policy-wrapped MCP tools. Tool calls require event emission and audit. Sensitive tools require HITL approval.

### Mode 5: approved execution

Only after capability promotion: MCP calls may execute under limits, timeouts, result validation, audit, rollback, and verification.

## Deny-by-default requirements

All MCP integrations must default to:

- `tools: denied`;
- `resources: denied`;
- `prompts: denied`;
- `roots: none`;
- `sampling: disabled`;
- `elicitation: human_gate_required`;
- `external_network: denied except configured server connection for inventory`;
- `credentials: token_ref_only`;
- `artifact_is_authority: false`.

## Result handling

MCP results may include unstructured content, structured content, resource links, or embedded resources. builder-II must treat all results as untrusted until processed by policy.

Minimum result handling:

- record server id and tool name;
- record input hash, not raw sensitive input where possible;
- record output type summary;
- validate structured output when schema exists;
- sanitize text before reuse;
- capture resource links as refs, not automatic context;
- require explicit approval before fetching linked resources;
- preserve error state.

## Roots policy

MCP roots must be derived from builder-II target profiles or explicit artifact roots.

Early allowed root types:

- artifact root, read-only;
- context pack root, read-only;
- target repo root, metadata-only or read-only when approved.

Denied root types:

- user home directory;
- system root;
- credential directories;
- `.git` internals unless a future git-state artifact explicitly permits metadata-only inspection;
- arbitrary model-selected paths.

## Sampling policy

MCP sampling is model-call authority. It must remain disabled until a model routing policy artifact and approval flow exist.

A future sampling approval must record:

- server id;
- prompt hash;
- model lane;
- visible prompt preview;
- result visibility to server;
- operator approval;
- cost boundary;
- audit ref.

## Elicitation policy

MCP elicitation should be represented as a builder-II human gate:

```text
server request
→ elicitation artifact
→ operator response
→ response audit
```

No server may directly collect user input outside the operator-visible gate.

## Fork implications for AssetOverflow/deepagents

Because `AssetOverflow/deepagents` is forked, builder-II can later benefit from fork-level seams:

- `ToolPolicyMiddleware` for deny-by-default tool filtering;
- `ReadOnlyFilesystemBackend` for target-repo read-only use;
- MCP namespace wrappers such as `server_id.tool_name`;
- audit callbacks around tool calls and subagent spawns;
- proposal-only memory and subagent result modes.

These should remain generic deepagents features, not builder-II-specific coupling.

## Promotion checklist

Before MCP can move beyond policy/inventory:

- docs exist;
- schemas exist;
- validators exist;
- command surface exists;
- denied defaults are tested;
- inventory is hash-stable;
- unknown tools fail closed;
- changed tool schemas trigger re-approval;
- HITL approval artifact exists;
- invocation audit artifact exists;
- result validation policy exists;
- credential handling uses refs only;
- rollback path exists;
- verification path exists.

## Governing sentence

MCP should become a clean integration seam for Goose and deepagents, not a backdoor around builder-II. Every MCP capability must be inventoried, classified, approved, invoked, audited, and verified through builder-II artifacts.
