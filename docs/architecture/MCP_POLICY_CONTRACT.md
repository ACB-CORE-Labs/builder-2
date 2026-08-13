# MCP policy artifact RFC

Status: design-only RFC.

This document defines the first builder-II policy artifact for Model Context Protocol (MCP) integrations. It does not implement MCP connectivity, tool execution, resource reads, sampling, or Goose/deepagents runtime behavior.

## Purpose

MCP makes external tools, resources, prompts, roots, sampling, and elicitation composable with agent systems. That is useful, but it is also a high-authority integration surface.

builder-II should make MCP easy to integrate by making it easy to govern:

```text
inventory first
classification first
allowlist first
approval first
audit first
execution later
```

## Non-goals

This RFC does not authorize:

- MCP server connections;
- MCP tool calls;
- MCP resource reads;
- MCP prompt injection into runtime prompts;
- MCP roots exposure;
- MCP sampling;
- credential storage;
- Goose runtime activation;
- deepagents construction;
- source collection;
- web search;
- shell execution;
- command execution;
- source writes;
- memory mutation.

## Artifact kind

```text
builder_ii.mcp_policy
```

## Draft schema

```json
{
  "kind": "builder_ii.mcp_policy",
  "schema_version": 1,
  "target_profile": "builder",
  "task": "inspect approved MCP integration surface",
  "capability_state": "policy_only",
  "server_refs": [],
  "inventory_refs": [],
  "allowed_tools": [],
  "denied_tools": [],
  "allowed_resources": [],
  "denied_resources": [],
  "allowed_prompts": [],
  "denied_prompts": [],
  "roots": [],
  "sampling": {
    "state": "disabled",
    "approval_required": true
  },
  "elicitation": {
    "state": "human_gate_required"
  },
  "authorization": {
    "mode": "none",
    "token_refs_only": true
  },
  "limits": {
    "max_tool_calls": 0,
    "max_parallel_tool_calls": 0,
    "tool_timeout_ms": 30000,
    "max_resource_bytes": 0
  },
  "result_policy": {
    "structured_output_validation": "required_when_schema_present",
    "text_sanitization": "required",
    "resource_links": "record_refs_only",
    "embedded_resources": "deny_by_default"
  },
  "approval_policy": {
    "default": "required",
    "sensitive_tools": "required",
    "external_requests": "required",
    "mutation_tools": "required"
  },
  "denied_actions": [],
  "rollback": {
    "mode": "delete_policy_artifact",
    "source_mutation_performed": false
  },
  "verification": {
    "required": true,
    "validator": "builder-mcp validate-policy"
  },
  "artifact_is_authority": false
}
```

## Server refs

A server ref should identify a server without leaking secrets.

Suggested fields:

```json
{
  "server_id": "github",
  "transport": "streamable_http",
  "url_hash": "...",
  "auth_required": true,
  "auth_ref": "env:GITHUB_MCP_TOKEN",
  "trust_state": "untrusted|operator_declared|trusted_local|trusted_remote",
  "inventory_ref": ".builder/artifacts/mcp-inventory-github.json"
}
```

Raw tokens must not appear in the artifact.

## Tool policy entries

Allowed tools should be explicit and hash-bound to inventory.

```json
{
  "server_id": "github",
  "tool_name": "list_pull_requests",
  "tool_ref": "github.list_pull_requests",
  "risk_class": "read_external_metadata",
  "input_schema_hash": "...",
  "output_schema_hash": "...",
  "approval_required": true,
  "max_calls": 3,
  "result_policy": "structured_output_validation_required"
}
```

Denied tool entries should explain why:

```json
{
  "server_id": "github",
  "tool_name": "merge_pull_request",
  "risk_class": "mutate_external_state",
  "denied_reason": "mutation tools are not promoted"
}
```

## Risk classes

Initial risk classes:

| Risk class | Meaning | Default |
| --- | --- | --- |
| `read_local_metadata` | Reads local metadata only | denied until policy allows |
| `read_local_content` | Reads local content | denied |
| `read_external_metadata` | Reads external metadata | denied |
| `read_external_content` | Reads external content | denied |
| `search_external` | Performs external search/source collection | denied |
| `write_local` | Writes local files/artifacts | denied |
| `mutate_external_state` | Mutates remote systems | denied |
| `execute_code` | Executes code/commands | denied |
| `send_message` | Sends email/chat/comments | denied |
| `spend_money` | May incur cost | denied |
| `credential_sensitive` | Uses credentials or secrets | denied |
| `sampling` | Requests LLM completion | denied |
| `unknown` | Cannot classify | denied |

Unknown must fail closed.

## Roots policy

Roots must be explicit. A root entry should look like:

```json
{
  "name": "builder artifacts",
  "uri": "file:///path/to/repo/.builder/artifacts",
  "mode": "read_only",
  "source": "target_profile",
  "expose_to_servers": false
}
```

Early policy should avoid exposing roots to MCP servers. Prefer inventory and artifact-level refs.

## Sampling policy

Sampling is disabled by default because it grants model-call authority to the server side.

A future approved sampling policy must include:

- server id;
- purpose;
- prompt preview/hash;
- model lane;
- cost boundary;
- result visibility;
- human approval ref;
- audit ref.

## Elicitation policy

Elicitation becomes a human gate artifact. MCP servers may request additional information, but builder-II should mediate:

```text
MCP elicitation request
→ builder_ii.human_gate_request
→ operator response
→ builder_ii.human_gate_result
→ optional MCP response
```

## Result policy

MCP tool results should not flow directly into prompts or artifacts as truth.

Policy must define:

- structured output validation when output schema exists;
- text sanitization;
- resource link handling;
- embedded resource handling;
- max byte limits;
- allowed MIME types;
- redaction behavior;
- provenance recording;
- error handling.

## Denied defaults

The validator should require that all high-authority defaults are denied unless explicitly overridden:

```text
tools: denied unless allowed_tools entry exists
resources: denied unless allowed_resources entry exists
prompts: denied unless allowed_prompts entry exists
roots: none unless explicit roots entry exists
sampling: disabled
elicitation: human_gate_required
mutation: denied
execution: denied
external search: denied
credential exposure: denied
```

## Promotion path

### Phase 1: RFC only

- This document.
- No implementation.

### Phase 2: schema and validator

- Add `builder-mcp validate-policy`.
- Invalid authority claims fail closed.

### Phase 3: inventory linkage

- Policy must reference inventory artifacts.
- Tool schema hashes must match inventory.

### Phase 4: approval linkage

- Sensitive tools require approval refs.

### Phase 5: invocation audit linkage

- Every call produces an invocation audit artifact.

### Phase 6: Goose/deepagents integration

- Goose reads policy.
- deepagents receives only policy-filtered tools.

## Acceptance criteria for first implementation

A future implementation PR must prove:

- policy artifacts validate;
- unknown tools fail closed;
- missing inventory refs fail closed;
- changed schema hashes fail closed;
- sampling is disabled by default;
- roots are empty by default;
- credentials are refs only;
- `artifact_is_authority` must be false;
- no MCP connection or tool execution occurs during validation.

## Governing sentence

MCP policy artifacts define what may be considered for use. They do not execute tools, trust servers, expose roots, authorize sampling, or make MCP results authoritative.
