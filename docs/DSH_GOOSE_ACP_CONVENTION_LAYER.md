# DeepSeek Harness / Goose ACP Convention Layer

This document defines the interface conventions and translation layer between DeepSeek Harness (DSH) and the governed Goose ACP runtime in builder-II.

---

## 1. Overview

The DeepSeek Harness convention layer maps DSH user interactions and lifecycle events to the standardized Agent Client Protocol (ACP) JSON-RPC 2.0 interface implemented by `goose acp`.

```text
┌────────────────────────────────────────────────────────┐
│ DeepSeek Harness UI / Cordis Kernel                     │
│  - Trajectory View                                     │
│  - Interactive Chat Box                                │
│  - In-UI Approval Modals                               │
└───────────────────────────┬────────────────────────────┘
                            │ (Cordis context events)
┌───────────────────────────▼────────────────────────────┐
│ dsh-goose-agent Bridge Plugin (`AgentFactory`)          │
│  - Translates DSH turns to ACP `session/prompt`        │
│  - Intercepts ACP tool permission requests             │
│  - Dispatches HITL approval API calls to builder-II    │
│  - Streams ACP notifications into DSH trajectory       │
└───────────────────────────┬────────────────────────────┘
                            │ (JSON-RPC 2.0 over stdio)
┌───────────────────────────▼────────────────────────────┐
│ Goose ACP Server (`goose acp`)                         │
│  - GOOSE_PATH_ROOT isolation                           │
│  - Builtin `developer` disabled                        │
│  - Governed builder-mcp enabled                        │
└────────────────────────────────────────────────────────┘
```

---

## 2. Session Identity Correlation

Every active session involves three distinct identifiers bound by a builder-II session binding artifact:

```text
builder_session_id ──► Root custody & ledger authority (UUIDv4)
dsh_session_id     ──► DSH presentation & trajectory UI key
goose_session_id   ──► Goose ACP internal SQLite session identifier
```

### Invariant Rules
- A session binding artifact (`builder_ii.dsh_goose_session_binding`) must be created at session bootstrap and finalized with cryptographic digests.
- Resume operations must verify that `dsh_session_id` and `goose_session_id` match the binding digest before resuming child processes.
- Mismatched or drifted sessions fail closed.

---

## 3. Protocol Message Mapping

### A. User Prompt Flow
1. User enters text in DSH UI $\rightarrow$ DSH invokes `Agent.send(prompt)`.
2. `dsh-goose-agent` translates to ACP method:
   ```json
   {
     "jsonrpc": "2.0",
     "id": "req-001",
     "method": "session/prompt",
     "params": {
       "session_id": "<goose_session_id>",
       "prompt": "<user_prompt_text>"
     }
   }
   ```
3. Goose streams deltas back via ACP notifications:
   - `session/delta` (reasoning thoughts, text chunks)
   - `session/tool_call_start` (tool metadata)
   - `session/tool_call_update` (progress updates)
   - `session/tool_call_complete` (result)
4. `dsh-goose-agent` pushes these events into DSH's append-only trajectory stream.

### B. Tool Authorization Flow (In-UI HITL)
1. Goose encounters a governed tool requiring authorization $\rightarrow$ sends ACP request:
   ```json
   {
     "jsonrpc": "2.0",
     "id": "perm-001",
     "method": "session/request_permission",
     "params": {
       "session_id": "<goose_session_id>",
       "tool_name": "patch_apply",
       "arguments": { "patch_file": ".builder/patches/patch-01.diff" }
     }
   }
   ```
2. `dsh-goose-agent` renders approval modal in DSH UI.
3. Operator clicks **Approve** in DSH UI.
4. `dsh-goose-agent` invokes builder-II HITL command:
   ```bash
   builder-platform approve --session <builder_session_id> --tool patch_apply --digest <args_digest>
   ```
5. builder-II mints `builder_ii.hitl_approval_receipt`.
6. `dsh-goose-agent` responds to Goose ACP:
   ```json
   {
     "jsonrpc": "2.0",
     "id": "perm-001",
     "result": {
       "decision": "grant",
       "approval_receipt_digest": "<sha256_digest>"
     }
   }
   ```
7. Goose executes the tool via `builder-mcp` providing the approval receipt digest.
