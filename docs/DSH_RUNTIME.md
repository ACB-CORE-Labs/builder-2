# DeepSeek Harness (DSH) runtime design spec

This document defines how builder-II integrates DeepSeek Harness (DSH) as an interactive UI and session projection layer over an isolated Goose ACP runtime while preserving builder-II governance and single-authority invariants.

This is a design specification and reference architecture.

---

## 1. Identity & Authority Boundaries

```text
builder-II        = governed control plane / sole authority / receipts & ledger
Goose             = sole agent execution & reasoning runtime (via `goose acp`)
DeepSeek Harness  = interactive UI facade & session projection layer (Cordis plugin)
governed MCP      = sole effectful tool execution surface
target repo       = generic / builder / core / research targets
```

### Absolute Governance Invariants
1. **Planned ≠ Executed ≠ Verified ≠ Promoted**: Model tokens or UI representations are observations, not authority.
2. **Singular Authority**: Neither DSH nor Goose possesses authority to mint permissions or execute ungoverned actions.
3. **Fail-Closed Mediation**: DSH interactive approvals (e.g. clicking "Allow") do not directly authorize tools; they trigger the builder-II Human-In-The-Loop (HITL) gate to mint cryptographic receipts.
4. **Hermetic Root Isolation**: Both runtimes are strictly anchored to builder-owned session roots (`DSH_HOME` and `GOOSE_PATH_ROOT`), completely ignoring user-level ambient configs (`~/.dsh`, `~/.config/goose`).

---

## 2. Architecture: Goose-Proxy Mode

DeepSeek Harness operates exclusively in **Goose-Proxy Mode**:

```text
Operator / User
  │
  ▼ (Interactive Chat, Prompts, Approval Clicks)
DeepSeek Harness (Web UI / TUI / Cordis Kernel)
  │ (Custom AgentFactory replaces default agent loop & native tools)
  ▼ (JSON-RPC 2.0 over stdio)
Goose ACP Server (`goose acp` with GOOSE_PATH_ROOT isolation)
  │ (Reasoning, tool selection, prompt processing)
  ▼ (MCP stdio protocol)
builder-II Governed MCP Server (`builder-mcp`)
  │ (Policy check, approval verification, sandboxing)
  ▼
Target Filesystem / Execution Receipts / State Ledger
```

### Component Roles & Restrictions
| Component | Permitted Capabilities | Prohibited Capabilities |
| :--- | :--- | :--- |
| **DeepSeek Harness** | Interactive chat UI, trajectory display, streaming token rendering, user approval event dispatch | Model execution, local LLM adapters, native bash/shell tools, native fs tools, standalone permission granting |
| **Goose ACP** | Reasoning loop, tool call formation, context window management | Direct raw filesystem mutation outside MCP, unmonitored bash execution (`developer` extension disabled) |
| **builder-II MCP** | Governed file read/write, patch staging, sandboxed verification, cryptographic receipts | Unchecked target mutation without signed receipt |
| **builder-II Control Plane** | Target profile resolution, context pack delivery, HITL approval minting, ledger audit | Delegating authority to external agent plugins |

---

## 3. Integration Levels & Phased Progression

| Phase | Designation | Primary Objective | Authority Status |
| :--- | :--- | :--- | :--- |
| **DSH-0** | Spec & Readiness | Pinned dependency manifests, ADR-0010, threat models, isolated profile renderer, smoke tests | Zero execution; spec & test only |
| **DSH-1** | Read-Only Transport Proof | Fixed `builder-goose start-acp-readonly` launch with isolated `GOOSE_PATH_ROOT`, empty builtins, governed MCP | Read-only target; no mutations permitted |
| **DSH-2** | First-Class DSH Goose Agent | Pinned TypeScript package (`integrations/dsh-goose-agent`) implementing Cordis `AgentFactory` over Goose ACP | Full interactive UI; read-only target |
| **DSH-3** | Custody & Observability | Launch plans, session correlation (`builder_session_id` $\leftrightarrow$ `dsh_session_id` $\leftrightarrow$ `goose_acp_session_id`), close receipts | Full trajectory logging; receipt binding |
| **DSH-4** | Adversarial Qualification | Chaos & lesion testing (unpinned plugins, permission spoofing, sudden exit, orphan processes) | Hard fail-closed verified |
| **DSH-5** | Write-Capable Promotion | Interactive HITL gate in UI triggering backend receipt minting | Governed write capability promoted |

---

## 4. Interactive UX & In-UI HITL Approval Protocol

To prevent context-switching between the DSH UI and CLI terminals:

1. When Goose issues an effectful tool call (e.g. `patch_apply`), builder-II MCP intercepts and returns `APPROVAL_REQUIRED`.
2. Goose halts turn execution and transmits an ACP authorization request upstream to DSH.
3. DSH renders a native interactive approval card in the UI.
4. When the operator clicks **Allow**:
   - The custom DSH bridge intercepts the event.
   - The bridge programmatically calls the `builder-II HITL` command/API.
   - The builder-II control plane mints an immutable, digest-bound approval artifact.
   - The bridge resumes Goose ACP with the bound approval reference.
   - Goose invokes the tool through builder-II MCP with proof of approval.
5. All executions append authoritative records to the builder-II ledger.
