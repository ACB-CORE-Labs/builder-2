# ADR 0010: DeepSeek Harness / Goose ACP Integration

## Status
Proposed

## Context
builder-II has a governed runtime using Goose. DeepSeek Harness (DSH) provides an advanced developer UI and plugin/session projection, and exposes an Agent Context Protocol (ACP) extension surface. Goose recently exposed `goose acp`, an ACP server over stdio/JSON-RPC.

The goal is to leverage DSH's UI and session projection while keeping Goose as the sole runtime and builder-II as the absolute control plane for model authority, approval, and execution receipts.

DeepSeek Harness is currently in developer preview and breaking changes are expected. Any integration requires exact version pinning and compatibility tests.

## Decision
We will implement a bounded read-only integration program (DSH-0 to DSH-5) with the strict architectural condition that DeepSeek Harness acts as a replaceable projection UI and Goose remains the sole execution runtime.

The chosen integration mode is **Goose-proxy mode**, where DSH's default LLM adapter, agent loop, and native tools are bypassed. A custom DSH `AgentFactory` translates DSH interactions into a persistent Goose ACP session.

The ownership boundary is defined as:
- **Target profiles, context packs, model routing**: builder-II
- **Command authority and capability promotion**: builder-II
- **Approvals, receipts, rollback, verification**: builder-II
- **Model/agent execution loop**: Goose
- **Effectful tools**: builder-II governed MCP (invoked by Goose)
- **UI and interaction projection**: DeepSeek Harness
- **DSH session log**: Observational, non-authoritative
- **Authoritative effect history**: builder-II ledger

### What we will NOT do
- Vendor DeepSeek Harness into builder-II.
- Fork Goose.
- Make DSH a hard dependency or a `target_profile`.
- Give DSH cloud model credentials in Goose-proxy mode.
- Allow arbitrary home-level DSH patches or plugins (`~/.dsh`).
- Treat the DSH session log as effect evidence.
- Promote writes in the first integration phase.

## Consequences
- Requires isolated environment bootstrapping for Goose (`GOOSE_PATH_ROOT`) and DSH (`DSH_HOME`) to prevent configuration drift.
- Requires building an ACP bridging layer (`dsh-goose-agent`) inside builder-II to project ACP events into the DSH UI without conferring authority.
- The default harness remains `goose_native`; `dsh_goose_acp` is strictly experimental until proven.

## Authority Ownership Matrix
| Concern | Owner |
|---------|-------|
| Target profiles, context packs, model routing | builder-II |
| Command authority and capability promotion | builder-II |
| Approvals, receipts, rollback, verification | builder-II |
| Model/agent execution loop | Goose |
| Effectful tools | builder-II governed MCP, invoked by Goose |
| UI and interaction projection | DeepSeek Harness |
| DSH session log | Observational, non-authoritative |
| Authoritative effect history | builder-II ledger |

## Threat Model (Fail-Closed Rules)
The integration must fail-closed if:
1. User `~/.dsh` attempts to inject a plugin.
2. User Goose configuration attempts to re-enable the developer extension.
3. DSH attempts a native shell or filesystem tool.
4. ACP client supplies a foreign MCP server.
5. DSH returns "allow" to a permission request.
6. Child process exits mid-turn or leaves descendants running.
7. Target file changes outside an approved receipt.
8. ACP protocol/version mismatch.
9. DSH session log claims an effect with no builder receipt.
10. DSH or Goose attempts to persist credentials.
11. Cancellation occurs during tool execution.
12. Config digest changes after validation.

