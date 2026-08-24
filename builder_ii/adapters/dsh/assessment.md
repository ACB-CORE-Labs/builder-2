# Final Assessment: DeepSeek Harness / Goose ACP Integration

## Verdict: GO (Conditional)

Integrating DeepSeek Harness (DSH) with Goose ACP under `builder-II` governance is highly feasible and strategically valuable, provided strict architectural boundaries are enforced.

### Why It Is Worth It
1. **Unparalleled UI Projection:** DeepSeek Harness provides a best-in-class UI and trajectory view for session visualization. It excels at projecting complex agent interactions (reasoning streams, tool calls, context injections) that raw CLI tools cannot match.
2. **Modular Architecture:** As confirmed by our research, both systems expose the necessary extension seams:
   - **DSH (via Cordis):** Everything is a plugin. The default `dsh-agent-loop`, native shell/fs tools, and policy engines can be completely disabled in `cordis.yml` or overridden by calling `ctx.agents.setFactory()`.
   - **Goose:** Supports hermetic isolation via `GOOSE_PATH_ROOT` and headless execution (`--with-builtin ""`), meaning it can run securely under builder-II's governed MCP without native filesystem/bash tools escaping policy constraints.
3. **Complementary Strengths:** This integration allows builder-II to leverage DSH's interaction and plugin composition surface while retaining Goose's robust model runtime and builder-II's absolute authority over execution receipts and HITL (Human-In-The-Loop) promotion gates.

### The Difficulty & The Ideal Path
- **Difficulty (6/10 for Read-Only, 9/10 for Write-Capable):** 
  - *The Easy Part:* Hooking the JSON-RPC streams together is trivial (3/10 spike).
  - *The Hard Part:* Establishing singular authority. DSH has its own tool registry, approval service, and sandboxes. Ensuring that a DSH `allow` click does NOT authorize an effectful tool—but instead delegates the decision back to the `builder-II` HITL gate—is critical.
- **The Ideal Path (Goose-Proxy Mode):** 
  We must treat DSH purely as an orchestrator/UI facade. DSH will spawn a custom `AgentFactory` that proxies all reasoning and tool generation to a background `goose acp` process. DSH native tools and default LLM agents are completely disabled. builder-II owns the target profiles, context packs, and execution receipts.

### Conclusion
We proceed with a bounded, phased approach starting with **DSH-0 (Spec & Readiness)** and moving to **DSH-1 (Read-Only Transport Proof)**. We will not vendor DSH, fork Goose, or promote write capabilities until the read-only integration is proven to fail-closed against all threat vectors.

