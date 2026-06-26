# MCP tool inventory RFC

Status: design-only RFC.

This document defines a future inventory artifact for Model Context Protocol (MCP) servers. Inventory is a read-only discovery record. It does not authorize tool execution, resource reads, prompt use, sampling, or elicitation.

## Purpose

MCP servers may expose tools, resources, and prompts, and their available tool list can change over time. builder-II needs a stable, reviewable snapshot before any policy can allow usage.

```text
server config
→ inventory request
→ inventory artifact
→ risk classification
→ policy artifact
→ approval artifact
→ invocation audit
```

Inventory comes before policy. Policy comes before execution.

## Non-goals

This RFC does not authorize:

- MCP tool calls;
- MCP resource reads;
- MCP prompt execution;
- MCP sampling;
- MCP elicitation responses;
- Goose runtime activation;
- deepagents construction;
- source collection;
- web search;
- external mutation;
- command execution;
- shell execution;
- source writes;
- memory mutation.

## Artifact kind

```text
builder_ii.mcp_inventory
```

## Draft schema

```json
{
  "kind": "builder_ii.mcp_inventory",
  "schema_version": 1,
  "target_profile": "builder",
  "capability_state": "inventory_only",
  "created_at_utc": "2026-06-26T00:00:00Z",
  "server": {
    "server_id": "github",
    "transport": "streamable_http",
    "url_hash": "...",
    "auth_required": true,
    "auth_ref_present": true,
    "trust_state": "operator_declared"
  },
  "capabilities": {
    "tools": true,
    "resources": false,
    "prompts": false,
    "list_changed": false,
    "sampling_requested": false,
    "roots_requested": false,
    "elicitation_requested": false
  },
  "tools": [],
  "resources": [],
  "prompts": [],
  "risk_summary": {
    "unknown": 0,
    "read_external_metadata": 0,
    "read_external_content": 0,
    "search_external": 0,
    "mutate_external_state": 0,
    "execute_code": 0,
    "credential_sensitive": 0
  },
  "inventory_hash": "...",
  "errors": [],
  "warnings": [],
  "denied_actions": [],
  "artifact_is_authority": false
}
```

## Tool entries

Each tool entry should record stable metadata and hashes.

```json
{
  "server_id": "github",
  "tool_name": "list_pull_requests",
  "tool_ref": "github.list_pull_requests",
  "title": "List pull requests",
  "description_hash": "...",
  "input_schema_hash": "...",
  "output_schema_hash": "...",
  "annotations_hash": "...",
  "risk_class": "read_external_metadata",
  "risk_reason": "lists remote PR metadata but does not mutate state",
  "requires_approval": true,
  "default_policy": "denied",
  "first_seen_at_utc": "2026-06-26T00:00:00Z",
  "last_seen_at_utc": "2026-06-26T00:00:00Z"
}
```

Tool descriptions and annotations must be treated as untrusted. Their hashes are evidence for change detection, not authority.

## Resource entries

Resource entries should not fetch content by default.

```json
{
  "server_id": "docs",
  "uri_hash": "...",
  "name": "project-readme",
  "mime_type": "text/markdown",
  "annotations_hash": "...",
  "content_fetched": false,
  "default_policy": "denied"
}
```

## Prompt entries

Prompt entries are prompt-profile candidates only.

```json
{
  "server_id": "workflow",
  "prompt_name": "research-plan",
  "description_hash": "...",
  "arguments_schema_hash": "...",
  "content_fetched": false,
  "default_policy": "denied"
}
```

No prompt may be injected into a runtime system prompt without a separate prompt profile policy.

## Inventory hash

The inventory hash should be computed from canonicalized stable fields:

- server id;
- transport;
- tool names;
- input schema hashes;
- output schema hashes;
- description hashes;
- resource metadata hashes;
- prompt metadata hashes;
- capability flags.

The hash must exclude volatile fields such as timestamps and warnings.

## Change detection

A later inventory should be compared with the previous inventory.

Changes that require re-review:

- new tool;
- removed tool;
- changed input schema hash;
- changed output schema hash;
- changed description hash;
- changed annotations hash;
- changed capabilities;
- new resource or prompt exposure;
- tool risk class changed;
- server trust state changed.

## Risk classification

Initial classifier should be conservative. If classification is uncertain, use `unknown` and deny.

Suggested classifier inputs:

- tool name;
- tool title;
- tool description;
- input schema fields;
- output schema fields;
- annotations;
- server trust state;
- transport;
- auth requirement.

Suggested output:

```json
{
  "risk_class": "unknown",
  "risk_reason": "classifier could not determine whether tool mutates external state",
  "default_policy": "denied",
  "requires_approval": true
}
```

## Commands

Future command surface:

```bash
builder-mcp inventory \
  --server github \
  --config .builder/mcp/github.json \
  --output .builder/artifacts/mcp-inventory-github.json

builder-mcp validate-inventory .builder/artifacts/mcp-inventory-github.json

builder-mcp diff-inventory \
  .builder/artifacts/mcp-inventory-github-old.json \
  .builder/artifacts/mcp-inventory-github-new.json
```

All commands must be no-execution. Inventory may connect only to the configured MCP server for capability listing.

## Denied actions in inventory mode

Inventory mode must deny:

- `tools/call`;
- resource content fetch;
- prompt content injection;
- sampling;
- elicitation response;
- root exposure beyond explicitly declared inventory need;
- shell execution;
- command execution;
- source writes;
- memory mutation;
- Goose runtime start;
- deepagents construction.

## Invocation audit preview

Inventory does not invoke tools, but it should define the future call audit shape.

Future invocation audits should include:

```json
{
  "kind": "builder_ii.mcp_invocation_audit",
  "schema_version": 1,
  "server_id": "github",
  "tool_name": "list_pull_requests",
  "tool_ref": "github.list_pull_requests",
  "inventory_ref": ".builder/artifacts/mcp-inventory-github.json",
  "policy_ref": ".builder/artifacts/mcp-policy.json",
  "approval_ref": ".builder/artifacts/approval.json",
  "arguments_hash": "...",
  "started_at_utc": "...",
  "completed_at_utc": "...",
  "status": "success|error|denied",
  "result_summary": {},
  "result_schema_valid": true,
  "result_sanitized": true,
  "artifact_is_authority": false
}
```

## Promotion path

### Phase 1: RFC only

- This document.
- No implementation.

### Phase 2: static schema/validator

- Validate inventory artifacts produced manually or by tests.
- No MCP connection yet.

### Phase 3: server capability listing

- Connect to explicit server config only for list operations.
- No tool/resource/prompt execution.

### Phase 4: risk classifier

- Conservative static classifier.
- Unknown defaults to denied.

### Phase 5: policy linkage

- MCP policy artifacts reference inventory hashes.

### Phase 6: invocation audit

- Only after approval and runtime promotion.

## Acceptance criteria for first implementation

A future implementation PR must prove:

- inventory artifacts validate;
- `artifact_is_authority` must be false;
- tool descriptions and annotations are not trusted;
- unknown tools default to denied;
- schema hash changes are detectable;
- inventory mode cannot call tools;
- inventory mode cannot fetch resources;
- inventory mode cannot inject prompts;
- sampling is disabled;
- secrets are not serialized.

## Governing sentence

MCP inventory is a snapshot for review and policy. It is not permission to use tools, trust servers, expose roots, call models, or consume external content.
