# Comprehensive Research Report: DeepSeek Harness & Goose ACP Integration

## 1. Executive Summary

This investigation evaluates the architectural alignment, feasibility, implementation complexity, and strategic value of integrating **DeepSeek Harness (`dsh`)** with **Goose ACP (`goose acp`)** under **builder-II** governance.

### Verdict: GO (Strict Goose-Proxy Mode)
The integration is technically sound, feasible, and strategically advantageous. Both platforms provide the precise architectural extension seams needed for a clean integration without requiring source forks of either tool.

---

## 2. Platform Extension Seams Analysis

### DeepSeek Harness (`@deepseek-ai/dsh`)
- **Microkernel Foundation**: Built on the **Cordis** framework where all capabilities are swappable plugins.
- **Custom Agent Loop Seam**: Exposes `AgentFactory` (`packages/core/agent/src/types.ts`). By registering a custom factory via `ctx.agents.setFactory()`, the default agent loop, native bash executors, and local model adapters are bypassed cleanly.
- **ACP Interoperability**: Implements ACP client and server mechanics over JSON-RPC 2.0 (`stdio`/WebSocket).
- **Trajectory Projection**: Separates event storage/projection from model execution, enabling rich UI streaming while keeping execution authority external.

### Goose Agent (`aaif-goose/goose`)
- **North-Bound Protocol**: Supports `goose acp` (Agent Client Protocol over `stdio` using JSON-RPC 2.0).
- **Hermetic Isolation**: Fully respects `GOOSE_PATH_ROOT`, isolating configuration, data, session sqlite databases, and extension registries.
- **South-Bound Tool Confinement**: Passing `--with-builtin ""` or setting `developer.enabled: false` completely deactivates native shell/filesystem access, restricting the tool surface exclusively to builder-II's governed MCP server.

---

## 3. Implementation Difficulty Matrix

| Dimension | Difficulty Score | Key Technical Challenge |
| :--- | :---: | :--- |
| **ACP Connectivity Spike** | **3 / 10** | Basic JSON-RPC handshake, prompt dispatch, and terminal output streaming over stdio. |
| **Governed Read-Only Candidate** | **6 / 10** | Strict `GOOSE_PATH_ROOT` and `DSH_HOME` isolation, credential stripping, MCP-only tools, preflight/postflight receipt generation. |
| **Interactive UI with In-UI Approvals** | **8 / 10** | Real-time trajectory streaming, cancelation, and bridging in-UI "Approve" button clicks to builder-II HITL receipt minting. |
| **Promoted Governed Write Capability** | **9 / 10** | Crash-consistent multi-session recovery, digest-bound artifact reconciliation, and adversarial tamper-resistance. |

---

## 4. Why It Is Worth It

1. **Superior Operator Experience**: DeepSeek Harness provides a modern, interactive TUI/Web UI with live trajectory visualization, step-by-step reasoning expansion, and visual tool inspection.
2. **Preserved Governance & Safety**: By restricting DSH to an observational/interaction facade and routing all effects through Goose into builder-II MCP, all execution receipts, state ledgers, and cryptographic invariants remain strictly protected.
3. **No Terminal Context-Switching**: The operator remains entirely in the DSH UI. HITL approvals are rendered in-line and securely minted via background API calls to builder-II.
4. **Zero Upstream Forks**: Utilizes standard Cordis plugin hooks and standard Goose ACP interfaces.

---

## 5. Risk Assessment & Mitigations

| Identified Risk | Impact | Enforced Mitigation |
| :--- | :--- | :--- |
| **Ambient Config Leakage** | Medium | Strict enforcement of `DSH_HOME` and `GOOSE_PATH_ROOT` per session. Ambient `~/.dsh` and `~/.config/goose` ignored. |
| **Authority Splitting** | High | Banning DSH native shell/fs tools. DSH cannot grant authority; it can only invoke builder-II HITL gates. |
| **Session Drift / Desynchronization** | Medium | Cryptographically bound session mapping artifact (`dsh_session_id` $\leftrightarrow$ `goose_session_id` $\leftrightarrow$ `builder_session_id`). |
| **Upstream Upgrades / API Shifts** | Medium | Strict version and SHA pinning in `PINNED_MANIFEST` with automated compatibility checks. |
