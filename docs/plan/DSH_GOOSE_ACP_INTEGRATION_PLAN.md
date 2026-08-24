# DeepSeek Harness / Goose ACP Integration Plan

## Objective
Progressively integrate DeepSeek Harness (DSH) as an interactive UI and session projection facade over an isolated Goose ACP runtime under builder-II governance.

---

## Phase Breakdown

### Phase DSH-0: Spec & Readiness (COMPLETED)
- **ADR 0010**: Enforce Goose-proxy mode, single authority, and root isolation (`docs/adrs/ADR-0010-deepseek-harness-goose-acp-integration.md`).
- **Compatibility Matrix & Threat Model**: `builder_ii/adapters/dsh/compatibility_matrix.py` with fail-closed rules.
- **Isolated Profile Renderer**: `builder_ii/adapters/dsh/profile_renderer.py` isolating `DSH_HOME` and `GOOSE_PATH_ROOT`.
- **Readiness Verification**: `builder_ii/adapters/dsh/readiness.py`.
- **No-Mutation ACP Smoke Proof**: `tests/adapters/dsh/test_acp_smoke.py` passing in CI/test suites.

---

### Phase DSH-1: Read-Only Transport Proof
- Implement builder-II CLI command:
  ```bash
  builder-platform goose start-acp-readonly --session-id <id>
  ```
- Scrub all environment variables except loopback model gateway credentials.
- Launch `goose acp` with `GOOSE_PATH_ROOT` and `--with-builtin ""` pointing exclusively to governed `builder-mcp`.
- Emit launch and close execution receipts.
- Run no-mutation postflight audit verifying zero repository modifications.

---

### Phase DSH-2: First-Class DSH Goose Agent Plugin
- Create pinned TypeScript package `integrations/dsh-goose-agent/`.
- Implement custom Cordis `AgentFactory` registering via `ctx.agents.setFactory()`.
- Bridge ACP JSON-RPC streams directly into DSH trajectory view.
- Verify interactive prompt/response loop in DSH Web UI / TUI without native shell tools enabled.

---

### Phase DSH-3: Custody, Observability & In-UI HITL
- Define structured artifacts:
  - `builder_ii.dsh_goose_launch_plan`
  - `builder_ii.dsh_goose_session_binding`
  - `builder_ii.dsh_goose_launch_receipt`
  - `builder_ii.dsh_goose_close_receipt`
- Implement in-UI HITL approval bridge: translate DSH UI approval clicks to `builder-platform approve` invocations and receipt binding.
- Support safe session cancelation and child process tree teardown.

---

### Phase DSH-4: Adversarial Qualification
- Execute failure-mode verification:
  - Injection of unpinned plugins in `DSH_HOME`.
  - Attempts by Goose to re-enable `developer` tools.
  - Out-of-band target filesystem modifications.
  - Subprocess sudden kill and orphan recovery.
- Confirm all violations fail closed with zero state corruption.

---

### Phase DSH-5: Governed Write Promotion
- Validate end-to-end write workflow:
  - Goose proposes patch $\rightarrow$ MCP blocks $\rightarrow$ DSH renders UI approval card $\rightarrow$ User clicks Approve $\rightarrow$ Bridge mints builder-II HITL receipt $\rightarrow$ MCP applies patch $\rightarrow$ Postflight verification passes.
- Final audit and capability promotion into `docs/CAPABILITY_PROMOTION.md`.
