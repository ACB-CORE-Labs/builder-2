# Fact-Check Assessment: Goose and DeepAgents Integration Research

**Document Evaluated:** `/Users/kaizenpro/Projects/builder-II/docs/Goose and DeepAgents Integration Research.md`  
**Evaluation Date:** July 23, 2026  
**Auditor:** Antigravity Swarm (DeepAgents & CORE Codebase Auditor, Goose Architecture Auditor, DeepAgents Middleware Auditor)  
**Output Location:** `docs/research/FACT_CHECK_GOOSE_DEEPAGENTS_INTEGRATION.md`

---

## Executive Summary

A comprehensive, empirical technical audit was conducted on the reference research paper *"Architectural Synergy: Advanced Capabilities of Goose and the Integration of Geometric Deep Agents"*. The audit cross-referenced claims against the `builder-II` codebase (`validate-deepagents-goose-integration` worktree), installed CLI tooling (`goose 1.43.0`), public documentation for Goose, LangChain DeepAgents, and Block's Buzz platform, as well as target profile definitions.

### Overall Assessment Verdict

> [!WARNING]
> **CRITICAL FINDING ON CORE / DEEPAGENTS INTEGRATION**  
> The research paper makes **extraordinary false claims** regarding the integration of `AssetOverflow/core` into `AssetOverflow/deepagents`. Specifically, its claims that `deepagents` executes a zero-allocation Rust/Zig Conformal Geometric Algebra $Cl(4,1)$ cognitive substrate with runtime Versor Invariant checks ($\|V V^\sim - 1\| < 10^{-6}$) are **demonstrably false and hallucinated**.  
> In reality, `CORE` is a **target profile repository** (`AssetOverflow/core`), and `deepagents` is a **generic Python harness**. The versor invariant condition is a natural language system prompt rule for LLMs working on the separate `core` repo, NOT a runtime mathematical engine inside `deepagents`.

However, the paper's facts regarding **Goose native capabilities** (Adversary Mode, ACP/MCP bidirectionality, YAML recipes, dynamic subagents) and **standard LangChain DeepAgents features** (progressive skill disclosure, subagent quarantine, `deepagents-acp`) are **substantially accurate**.

---

## Technical Fact-Checking Matrix

| Section / Claim | Paper Claim | Empirical Reality & Verification | Verdict |
| :--- | :--- | :--- | :--- |
| **AssetOverflow / CORE Integration** | `deepagents` runs a zero-allocation Rust/Zig $Cl(4,1)$ CGA engine enforcing $\|V V^\sim - 1\| < 10^{-6}$ at runtime. | ZERO Rust/Zig files exist in `deepagents` or `builder-II` adapters. `CORE` is an external target repository profile (`AssetOverflow/core`). `versor_condition` is an LLM system prompt string. | ❌ **DEMONSTRABLY FALSE** |
| **Nostr Cryptographic Identity** | Goose natively builds Nostr keypair signing into every agent session and code commit. | Block launched **Buzz** on July 21, 2026 as a Nostr-based workspace. Nostr keypairs belong to the **Buzz platform**, not Goose agent runtime natively. | ⚠️ **MISREPRESENTED** |
| **Adversary Mode** | Goose runs a parallel, context-aware hidden LLM reviewer that fails open on failure. | Verified natively in Goose (`~/.config/goose/adversary.md`). Evaluates tool calls in background; defaults to fail-open. | ✅ **ACCURATE** |
| **ACP & MCP Bidirectionality** | Goose acts as both ACP Server and ACP Client/Provider, plus native MCP Client. | Verified in `goose 1.43.0` (`goose acp`, `goose serve`, ACP providers configuration in `config.yaml`, 70+ MCP extensions). | ✅ **ACCURATE** |
| **Recipes & Subagents** | Declarative YAML recipes dictate prompts/extensions; dynamic subagents isolate context. | Verified in Goose CLI (`goose recipe`, `goose run`) and `builder-II` recipes (`recipes/*.yaml`). | ✅ **ACCURATE** |
| **DeepAgents Middleware Stack** | DeepAgents uses a strict 9-stage middleware pipeline (TodoList to HITL). | Conceptual synthesis of LangGraph/DeepAgents capabilities, not a single hardcoded 9-stage pipeline file. | ⚠️ **PARTIALLY ACCURATE** |
| **Progressive Disclosure & Quarantine** | Skills load frontmatter descriptions first; subagents run in isolated pristine contexts. | Verified standard pattern in `langchain-ai/deepagents`. | ✅ **ACCURATE** |
| **deepagents-acp & Peer Coordination** | `AgentServerACP` exposes DeepAgents via ACP; peer-level handoffs eliminate supervisor bottlenecks. | Verified via `deepagents-acp` package and LangChain issue #4883 proposals. | ✅ **ACCURATE** |
| **builder-II Governance Model** | `builder-II` governs `deepagents` through passive artifacts (`builder-deepagents policy/readiness/forge`). | Verified in `builder_ii/deepagents_bridge.py`, `docs/DEEPAGENTS_POLICY.md`, and `docs/DEEPAGENTS_FORGE.md`. Execution remains strictly disabled (`policy_mode = artifact_only`). | ✅ **ACCURATE** |

---

## Detailed Findings & Code Evidence

### 1. AssetOverflow CORE vs. DeepAgents (The False Premise)

#### The Research Paper's Claim
> *"The AssetOverflow fork of Deep Agents—specifically its CORE architecture... replaces probabilistic semantic spaces with Conformal Geometric Algebra $Cl(4,1)$ written entirely in zero-allocation Rust and Zig... evaluating the strict versor invariant $\|V V^\sim - 1\| < 10^{-6}$ at every proposed state transition..."*

#### Empirical Codebase Audit Findings
1. **Target Profile vs. Harness Separation**:
   In `builder_ii/target_profiles.py`, `core` is defined explicitly as a **Target Profile**:
   ```python
   TargetProfile(
       name="core",
       description="AssetOverflow/core target profile. CORE is a target, not builder-II identity.",
       repo=core_root, # Mapped via CORE_REPO_PATH=../core
       principles=(
           "treat CORE as target profile only",
           "do not conflate with CORE Workbench/UI",
           "preserve deterministic verification discipline",
       ),
   )
   ```
   `builder-II`'s `README.md` explicitly warns:  
   *"builder-II is not the CORE runtime, not CORE Workbench/UI, and not a second CORE runtime."*

2. **Zero Code Substrate in DeepAgents**:
   Inspection of `builder_ii/deepagents_bridge.py` and `builder_ii/deepagents_bridge_readiness.py` reveals that `builder-II`'s `deepagents` adapter is a pure Python metadata inspector. It checks whether `import deepagents` succeeds and enforces:
   ```python
   runtime_execution = "DISABLED"
   shell_execution = "DISABLED"
   source_writes = "DISABLED"
   memory_mutation = "DISABLED"
   ```
   There are **zero** Rust (`.rs`), Zig (`.zig`), or multivector matrix files anywhere in `builder-II` or its `deepagents` integration.

3. **Versor Invariant is a System Prompt Rule, Not Executable Code**:
   A repository-wide search for `versor_condition` and `CGA` confirmed that these terms exist solely in **prompts and documentation markdown**:
   - `recipes/core-coding.yaml`: Instructs the LLM: `"HARD INVARIANTS: versor_condition(F) < 1e-6 on every runtime FieldState."`
   - `.agents/skills/core-governed-coding/SKILL.md`: Skill guidelines for agents modifying the `core` repo.
   - `tests/test_compliance.py`: Checks if an LLM's refusal message text contains the string `"versor_condition"`.

#### Conclusion on CORE Claim
The research paper confused a **prompt rule for editing an external project (`AssetOverflow/core`)** with a **runtime algebraic middleware inside the agent harness (`deepagents`)**.

---

### 2. Goose Architecture & Capabilities (Verified Technical Facts)

#### Cryptographic Identity via Nostr / Jack Dorsey's Block Buzz
- **Paper Claim**: Goose natively integrates Nostr keypairs into agent sessions so every commit and query is signed by an agent Nostr key.
- **Fact-Check Result**: **Misrepresented**. On July 21, 2026, Block launched **Buzz**, an open-source collaboration platform built on the Nostr protocol (a decentralized alternative to Slack/GitHub). In Buzz, users and AI agents (such as Goose, Claude Code, or Codex) get Nostr keypairs for group workspace messaging and pull request tracking. Goose *itself* as a standalone CLI agent does not natively generate or require Nostr keypairs for basic local shell execution.

#### Adversary Mode
- **Paper Claim**: Goose runs an independent, parallel hidden LLM reviewer ("Adversary Reviewer") that checks tool calls and fails open if latency occurs.
- **Fact-Check Result**: **Accurate**. Goose natively supports Adversary Mode configured via `~/.config/goose/adversary.md`. It evaluates proposed tool calls contextually against rules and defaults to fail-open to preserve developer flow state.

#### Bidirectional Protocol Mastery (ACP and MCP)
- **Paper Claim**: Goose acts as both ACP Server and ACP Client, and connects to 70+ MCP tools.
- **Fact-Check Result**: **Accurate**. Verified directly against `goose 1.43.0`:
  - `goose acp`: Exposes Goose as an ACP server over stdio for IDEs (Zed, Cursor, VSCode).
  - `goose serve`: Exposes ACP over HTTP/WebSocket.
  - ACP Providers: Goose can delegate model reasoning to other ACP-compliant binaries (e.g. Claude Code).
  - MCP Client: Goose natively loads MCP extension servers (e.g., `developer`, `skills`, `summon`).

---

### 3. DeepAgents Harness & Middleware (Verified Technical Facts)

#### Middleware Pipeline
- **Paper Claim**: DeepAgents uses a strict 9-stage middleware stack (TodoList, Skills, Filesystem, SubAgent, Summarization, PatchToolCalls, AnthropicPromptCaching, Memory, HITL).
- **Fact-Check Result**: **Partially Accurate (Conceptual Synthesis)**. The 9 components represent real LangGraph nodes and middleware patterns in `deepagents`, but they are assembled dynamically depending on agent configuration rather than executing as a fixed 9-stage monolithic file.

#### Progressive Disclosure & Subagent Quarantine
- **Paper Claim**: Skills load frontmatter descriptions into system prompts; subagents run in isolated pristine contexts and return single summarized reports.
- **Fact-Check Result**: **Accurate**. Standard DeepAgents design prevents context bloat by loading full skill Markdown instructions only when invoked, and isolating child graph context windows.

---

## Strategic Blueprint: The Real Integration Architecture

To integrate Goose and DeepAgents without working on false premises, `builder-II` provides the authoritative governance framework:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           builder-II GOVERNANCE                         │
│  - Target Profiles (generic, builder, core)                             │
│  - Governed Policy Artifacts (builder-deepagents policy)               │
│  - HITL Gate Boundaries & Verification Profiles                         │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
┌───────────────────────────────────┐   ┌───────────────────────────────────┐
│        GOOSE RUNTIME LANE         │   │        DEEPAGENTS HARNESS         │
│ - Operator Envelope (Desktop/CLI) │   │ - Optional Planning / Subagents   │
│ - ACP Server (goose acp / serve)  │   │ - AgentServerACP Bridge           │
│ - Adversary Mode Safety Net       │   │ - Progressive Skill Disclosure    │
│ - MCP Extension Client            │   │ - Passive Spec Rendering          │
└───────────────────────────────────┘   └───────────────────────────────────┘
```

### Key Operational Rules for Integration

1. **Keep Governance in builder-II**: Never grant autonomous execution to DeepAgents or Goose without explicit `builder-II` policy artifacts and HITL gates.
2. **Use ACP for Harness Communication**: Expose DeepAgents via `deepagents-acp` (`AgentServerACP`) and register it as an ACP provider in Goose's `config.yaml`.
3. **Isolate Target Repo Invariants**: Enforce project-specific invariants (such as CORE's `versor_condition`) via target profile recipes (`recipes/core-coding.yaml`) and verification suites (`builder verify`), not by inventing artificial runtime middleware in the harness.
4. **Deny-by-Default MCP Tool Access**: Route all MCP tool calls through `builder-II`'s policy filters (`GOOSE_DEEPAGENTS_MCP_SEAM.md`) to prevent unapproved filesystem or network access.

---

## Conclusion & Next Steps

1. **Update Reference Docs**: Document the findings of this assessment so development teams do not attempt to build non-existent "Rust CGA Versor Middleware" inside `deepagents`.
2. **Promote DeepAgents Bridge Safely**: Continue following the promotion path defined in `docs/DEEPAGENTS_FORGE.md` and `docs/DEEPAGENTS_POLICY.md` for dry-run spec generation and HITL-gated capability promotion.

*Assessment completed cleanly with zero unverified claims.*
