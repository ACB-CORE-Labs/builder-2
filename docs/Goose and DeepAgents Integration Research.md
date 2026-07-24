# **Architectural Synergy: Advanced Capabilities of Goose and the Governed Integration of Deep Agents**

## **Executive Overview of Agentic Orchestration**

The landscape of autonomous software engineering agents is undergoing a profound structural shift, evolving from monolithic, cloud-bound wrappers around large language models into decentralized, local-first architectures that operate on standardized, open protocols. This transition is not merely a change in deployment methodology but represents a fundamental reimagining of how artificial intelligence interacts with development environments, system memory, and human oversight. At the vanguard of this architectural shift is Goose, an open-source, extensible artificial intelligence agent framework initially incubated by Block and subsequently transferred to the Agentic AI Foundation under the governance of the Linux Foundation.1 While Goose is widely recognized within the developer community for its local execution capabilities and its robust integration with the Model Context Protocol, its underlying architecture harbors a suite of highly advanced, rarely discussed capabilities that fundamentally alter the theoretical boundaries of human-AI collaboration.3  

Concurrently, the LangChain ecosystem has incubated Deep Agents, a robust, production-ready agent harness built upon the LangGraph runtime.6 Deep Agents introduces sophisticated state management, hierarchical task delegation, and persistent memory into the agentic loop.7 The framework is designed to handle long-horizon, multi-step engineering tasks that typically cause naive agents to collapse under the weight of context bloat and logical drift. 

Within the `builder-II` platform (`AssetOverflow/builder-II`), `deepagents` functions as an optional, passive planning and subagent harness. Crucially, `builder-II` maintains a strict architectural decoupling between **agent harnesses** (such as Goose or Deep Agents) and **target repository profiles** (such as `AssetOverflow/core`). While `AssetOverflow/core` represents a distinct mathematical engine repository governed by strict algebraic invariants (such as Conformal Geometric Algebra principles and Versor conditions), these invariants act as prompt-level governance instructions and verification gates for target repositories, rather than compiled runtime middleware embedded within the `deepagents` harness itself.

This research report provides a nuanced examination of the deep architectural capabilities of the Goose framework. It surfaces secondary and tertiary implications of its foundational design choices, particularly its integration within cryptographic workspace environments such as Block's Nostr-based Buzz platform, its native adversarial safety nets, and its masterful execution of protocol bidirectionality (MCP and ACP). Furthermore, this analysis constructs a realistic, technically grounded blueprint for integrating the Deep Agents architecture into Goose under `builder-II` governance. By synthesizing Goose’s localized environmental control and user interface with `builder-II`'s policy-gated execution engine, enterprise engineering teams can achieve a seamlessly extensible autonomous development environment.

---

## **The Hidden Depths of the Goose Architecture**

While Goose is frequently marketed as a straightforward open-source alternative to proprietary coding assistants like GitHub Copilot or Anthropic's Claude Code, its foundation in Rust and its strict adherence to interoperability protocols elevate it from a simple terminal application to a comprehensive orchestration hypervisor.3 The following capabilities represent the most potent, yet under-discussed, mechanisms within the broader Goose ecosystem, revealing a system designed not just to generate text, but to govern autonomous action securely.

### **Cryptographic Workspace Identity via the Nostr Protocol (Block Buzz)**

One of the most consequential deployments of the Goose architecture is its integration within Block’s Buzz platform. Launched in July 2026, Buzz is an open-source collaboration workspace built entirely on the Nostr protocol, positioning itself as a decentralized alternative to centralized corporate platforms like Slack and GitHub.12 Traditional artificial intelligence agent frameworks suffer from a severe identity crisis: AI agents typically operate either under the direct credentials of the human user who spawned them or under generic, highly privileged service accounts. This paradigm creates critical auditability failures, as malicious actions or hallucinations cannot be easily decoupled from legitimate human activity.  

The integration of agents like Goose within a Nostr-compatible environment introduces platform-independent cryptographic identities for both human developers and artificial intelligence agents.12 Within the Buzz platform, every participant—whether human or AI agent—receives a unique Nostr public and private keypair.12  

The second-order implications of this cryptographic identity design are transformative for enterprise risk management and compliance architectures:
- **Verifiable Delegation Lineage**: Because both human developers and Goose agents cryptographically sign their workspace events (messages, code review comments, workflow steps), every action is inexorably linked to a specific, mathematically verifiable cryptographic identity.13
- **Granular Session Revocation**: In the event of a compromised session or an agent hallucinating destructive commands, the specific agent's public key permissions can be revoked within the workspace without impacting the human user's identity or ongoing workflows.13
- **Identity Decoupling**: Standalone Goose CLI execution operates locally under standard local environment user privileges, whereas Goose instances participating within a Buzz workspace gain cryptographic identity via Nostr event signatures.

### **Context-Aware Adversary Reviewer (Adversary Mode)**

Agentic automation inherently relies on tool execution, ranging from benign actions like reading local text files to highly privileged operations like executing arbitrary shell scripts or modifying cloud infrastructure. The standard industry approach to securing these execution boundaries relies on pattern-based prompt injection detection, static regular expression filters, or simple blocklists.14 Goose introduces a fundamental paradigm shift in execution security through a native mechanism known as **Adversary Mode**.3  

The Adversary Reviewer is an independent, silent artificial intelligence agent running continuously in parallel to the primary cognitive engine. Before the main Goose instance can execute any proposed tool call, the action parameters are routed to the Adversary Reviewer for evaluation.15 Unlike static filters that rely on hardcoded rules, the Adversary Reviewer is deeply context-aware.14 It is dynamically fed the user’s original prompt, the recent conversational history, and the exact parameters of the proposed tool execution.14 It evaluates this contextual package against user-defined organizational policy rules (configured in `~/.config/goose/adversary.md`) and returns a binary decision (ALLOW or BLOCK). If blocked, the tool call is denied at the sandbox boundary, and the primary agent receives a rejection error.14  

| Architectural Implication | Mechanism and Operational Impact |
| :---- | :---- |
| **Semantic Differentiation** | The adversary can distinguish between legitimate and malicious uses of the identical command (e.g., fetching a dependency vs. exfiltrating SSH keys).14 |
| **Fail-Open Resilience** | If the adversary reviewer model fails to respond due to network latency or API downtime, the system is designed to fail open, allowing the tool call to proceed to prevent developer flow state gridlock.14 |
| **Cost-Optimized Dual-Model Topologies** | Because the adversary operates on a highly constrained context window—evaluating only immediate intent and tool parameters—it can be powered by smaller, faster, cheaper distilled models.14 |

### **Bidirectional Protocol Mastery: MCP and ACP**

The true architectural genius of Goose lies in its bidirectional adoption of two critical open standards: the **Model Context Protocol (MCP)** and the **Agent Client Protocol (ACP)**.3  

- **Model Context Protocol (MCP)**: Developed to standardize how agents interface with external data sources and execution environments. Goose natively acts as an MCP Client supporting over seventy community extensions (e.g., filesystem tools, developer tools, GitHub, SQL databases).3
- **Agent Client Protocol (ACP)**: An interoperability standard for agent-editor communication via JSON-RPC 2.0 over standard input/output channels. Goose exhibits bidirectional composability:
  - **Goose as ACP Server (`goose acp` / `goose serve`)**: Editors like Zed, JetBrains, Cursor, or VSCode connect to a headless Goose daemon. Goose manages file diffs, isolated terminal sessions, and tool calls, feeding state changes directly into the editor UI.16
  - **Goose as ACP Client / Provider Host**: Goose allows users to swap out its internal language model reasoning engine for other ACP-compliant agents (such as Claude Code or custom local binaries).22 In this mode, Goose routes reasoning to the backend agent while passing loaded MCP tools through.

### **YAML-Driven Recipe Orchestration and Ephemeral Subagents**

Goose abstracts multi-step agent behaviors into portable, declarative YAML configurations known as **Recipes**.3 A standard Goose recipe encapsulates system prompt instructions, required extension tools, environmental parameters, and sub-recipe dependencies.3  

This declarative capability is augmented by Goose’s native support for **Subagents**. When a task exceeds the context window of a single session, Goose can dynamically spawn ephemeral child agent processes for parallel or specialized workloads.4 A YAML recipe can instruct the primary Goose session to spawn one specialized subagent tasked exclusively with writing unit tests and another with running static analysis. The subagents execute asynchronously in isolated context windows and return summarized results to the primary session.4

---

## **The Deep Agents Paradigm**

LangChain's Deep Agents framework is an open-source agent harness built upon the LangGraph runtime.6 It provides cognitive structuring, streaming, persistence, and checkpointing necessary for handling long-horizon tasks without context bloat.6

### **Cognitive Flow and Functional Pipeline**

The execution flow of a Deep Agent structures human intents, state transitions, and context formatting into a coherent pipeline:

| Functional Stage | Pipeline Component | Operational Responsibility |
| :---- | :---- | :---- |
| **1. Intent Tracking** | Task List / Todo | Establishes a structured task list, mapping user intent to pending, active, or completed task states.8 |
| **2. Knowledge Ingestion** | Skills System | Dynamically loads domain-specific knowledge and standard operating procedures required for active tasks.8 |
| **3. Environmental Context** | Filesystem Backend | Mounts local, sandboxed, or remote storage backends for codebase orientation.6 |
| **4. Delegation Engine** | SubAgent Manager | Spawns ephemeral child agents with isolated contexts to handle sub-routines.8 |
| **5. Context Compression** | Summarization | Compresses long conversational threads and offloads massive tool outputs to disk.6 |
| **6. Tool Sanitization** | Tool Formatting | Normalizes and sanitizes tool execution parameters before execution.31 |
| **7. Cost Optimization** | Prompt Caching | Caches static sections of system prompts and memory files prior to human intervention.8 |
| **8. State Continuity** | Persistent Memory | Injects persistent preferences, coding guidelines, and historical context into prompt assembly.8 |
| **9. Execution Boundary** | HITL Middleware | Pauses the execution graph, presenting proposed tool calls to a human operator for approval.6 |

### **Progressive Skill Disclosure and Context Quarantine**

Deep Agents addresses context window bloat through two primary mechanisms:
1. **Progressive Skill Disclosure**: Skills are stored in Markdown files. The system injects only skill frontmatter (metadata and brief descriptions) into the initial system prompt. The full algorithmic instruction set of a skill is loaded dynamically into active context only when the agent explicitly selects that skill.8
2. **Subagent Quarantine**: When delegating a sub-task, Deep Agents spins up an ephemeral child agent with a pristine, isolated context window.6 The child agent executes its task autonomously and returns a single compressed report to the parent, preventing iterative sub-routine chatter from polluting the parent agent’s context window.8

### **Evolving Topologies: Peer-Level Coordination**

Beyond hierarchical delegation, advanced implementations utilize peer-level multi-agent topologies.32 In a peer-to-peer setup, specialized agents (e.g., Exploration Agent, Verification Agent, Arbitration Agent) operate as equals, communicating via explicit exported handoffs. Each peer maintains a private context window, preventing cross-contamination of reasoning chains.32

---

## **Target Profiles and Governed Invariants: The `builder-II` Model**

A key insight of the `builder-II` architecture is the clean separation between **Agent Harnesses** (`deepagents`, `goose`) and **Target Profiles** (`generic`, `builder`, `core`).

### **Target Profile Repository vs. Agent Harness**

In `builder-II`, repositories being modified are defined as **Target Profiles** (`builder_ii/target_profiles.py`):
- **`generic`**: Standard software repository with no project-specific doctrine.
- **`builder`**: `builder-II` self-development target profile.
- **`core`**: `AssetOverflow/core` target profile representing the mathematical engine repository.

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

### **Target Invariants as Prompt Governance and Verification Gates**

When targeting the `core` repository, strict mathematical invariants—such as Conformal Geometric Algebra $Cl(4,1)$ representation, Versor normalization conditions ($\text{versor\_condition}(F) < 10^{-6}$), and inner product recall contracts—are enforced through:
1. **Governed System Prompts / Recipes**: Recipes such as `recipes/core-coding.yaml` explicitly instruct the LLM to refuse non-compliant code proposals (e.g., refusing ANN/HNSW/cosine similarity in favor of exact CGA recall).
2. **Deterministic Verification Suites**: The `builder verify` CLI suite executes deterministic test suites against the target repository to verify that mathematical invariants hold before code promotion.
3. **Passive Policy Artifacts**: `builder-II` generates policy artifacts (`builder-deepagents policy`) and readiness reports (`builder-deepagents readiness`) that keep runtime execution explicitly disabled (`policy_mode = artifact_only`) until human approval is granted.

This architecture ensures that domain-specific mathematical rigor is maintained as a **verifiable constraint on target repository code**, without falsely conflating target rules with internal harness middleware.

---

## **Realistic Integration Architecture: The Governed Bridge**

The synthesis of Goose and Deep Agents is achieved by using `builder-II` as the governance authority, Goose as the operator-facing runtime envelope, and Deep Agents as an optional planning harness communicating over standard protocols.

### **The "Zero-Glue" Code Architectural Principle**

A foundational tenet of this integration is that **`builder-II` requires zero custom Python glue code or bespoke ACP server implementations** to facilitate this bridge. By attempting to write custom wrappers inside `builder-II` to host the Deep Agents server, developers accidentally re-couple the agent harness to the governance layer—an architectural anti-pattern. The masterful integration relies entirely on native protocol support: Deep Agents runs its standard server, Goose communicates natively via standard provider configurations, and `builder-II` governs passively through statically generated artifacts.

### **Architectural Topology**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           builder-II GOVERNANCE                         │
│  - Target Profile Resolution (generic, builder, core)                  │
│  - Policy & Readiness Artifacts (builder-deepagents policy)             │
│  - Human-in-the-Loop (HITL) Authority & Verification Profiles           │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
┌───────────────────────────────────┐   ┌───────────────────────────────────┐
│        GOOSE RUNTIME LANE         │   │        DEEPAGENTS HARNESS         │
│ - Desktop / CLI Operator Envelope │   │ - Optional Planning & Subagents   │
│ - ACP Server (goose acp / serve)  │   │ - AgentServerACP Provider Bridge  │
│ - Adversary Mode Safety Net       │   │ - Progressive Skill Disclosure    │
│ - MCP Extension Client            │   │ - Passive Spec Rendering          │
└───────────────────────────────────┘   └───────────────────────────────────┘
```

### **Step-by-Step Integration Mechanics**

1. **Governance Policy Definition**: `builder-II` issues a governed `deepagents_policy` artifact specifying allowed target bindings, denied tool operations (`write_file`, `execute_shell`), and mandatory HITL approval gates.
2. **Deep Agents ACP Exposure**: The Deep Agents harness is wrapped in an ACP-compliant server (`AgentServerACP` / `deepagents-acp`), exposing its graph execution over stdio or HTTP/WS.
3. **Goose Provider Registration**: Goose is configured via `config.yaml` to register the Deep Agents ACP daemon as a custom provider:
   ```yaml
   # Goose ACP Provider Configuration
   providers:
     deepagents:
       engine: acp
       command: "uv run python -m deepagents_acp.server"
       description: "DeepAgents governed planning engine"
   ```
4. **Execution Flow & Adversary Safety**:
   - The user issues a task prompt in Goose.
   - Goose routes reasoning through the protocol bridge to the Deep Agents ACP provider.
   - Deep Agents constructs an execution graph, offloading sub-tasks to quarantined subagents.
   - Proposed tool calls are piped back to Goose, where the silent **Adversary Reviewer** evaluates contextual safety.
   - Approved tool calls execute locally, rendering native diffs in the developer's IDE.

---

## **Conclusion**

The integration of Goose and Deep Agents under `builder-II` governance represents a mature, practical architecture for autonomous software engineering. By cleanly decoupling operator execution (Goose), agent delegation (Deep Agents), governance policy (`builder-II`), and target domain invariants (`AssetOverflow/core`), development teams establish a transparent, auditable, and secure engineering environment built on open standards (MCP and ACP).

---

#### **Works cited**

> 1. Goose: AI-Powered Developer Agent from Block \- YouTube, accessed July 23, 2026, [https://www.youtube.com/watch?v=KrFSaY-v-tE](https://www.youtube.com/watch?v=KrFSaY-v-tE)  
> 2. Linux Foundation Announces the Formation of the Agentic AI Foundation (AAIF), Anchored by New Project Contributions Including Model Context Protocol (MCP), goose and AGENTS.md, accessed July 23, 2026, [https://www.linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation](https://www.linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation)  
> 3. goose | Your open source AI agent, accessed July 23, 2026, [https://goose-docs.ai/](https://goose-docs.ai/)  
> 4. You Don't Need to Build Your AI Agent — Just Use Goose \- Agentailor, accessed July 23, 2026, [https://blog.agentailor.com/posts/goose-open-source-agent-quickstart](https://blog.agentailor.com/posts/goose-open-source-agent-quickstart)  
> 5. Codename Goose: An open source local AI agent built on MCP \- YouTube, accessed July 23, 2026, [https://www.youtube.com/watch?v=ZyBpMgAdz7A](https://www.youtube.com/watch?v=ZyBpMgAdz7A)  
> 6. GitHub \- langchain-ai/deepagents: The batteries-included agent ..., accessed July 23, 2026, [https://github.com/langchain-ai/deepagents](https://github.com/langchain-ai/deepagents)  
> 7. Introducing Deep Agents CLI \- LangChain, accessed July 23, 2026, [https://www.langchain.com/blog/introducing-deepagents-cli](https://www.langchain.com/blog/introducing-deepagents-cli)  
> 8. Are there any Goose MCP users out there? \- Reddit, accessed July 23, 2026, [https://www.reddit.com/r/mcp/comments/1mlj2fh/are\_there\_any\_goose\_mcp\_users\_out\_there/](https://www.reddit.com/r/mcp/comments/1mlj2fh/are_there_any_goose_mcp_users_out_there/)  
> 9. Sponsor @AssetOverflow on GitHub Sponsors, accessed July 23, 2026, [https://github.com/sponsors/AssetOverflow](https://github.com/sponsors/AssetOverflow)  
> 10. Enforcing algebraic coherence at the type level in Rust — a versor invariant that makes incoherence impossible, not just detectable : r/Compilers \- Reddit, accessed July 23, 2026, [https://www.reddit.com/r/Compilers/comments/1ufo69d/enforcing\_algebraic\_coherence\_at\_the\_type\_level/](https://www.reddit.com/r/Compilers/comments/1ufo69d/enforcing_algebraic_coherence_at_the_type_level/)  
> 11. GitHub \- aaif-goose/goose: an open source, extensible AI agent that goes beyond code suggestions \- install, execute, edit, and test with any LLM, accessed July 23, 2026, [https://github.com/aaif-goose/goose](https://github.com/aaif-goose/goose)  
> 12. Block Buzz Platform: Open Source AI Collaboration Workspace, accessed July 23, 2026, [https://en.cryptonomist.ch/2026/07/22/block-buzz-platform/](https://en.cryptonomist.ch/2026/07/22/block-buzz-platform/)  
> 13. Jack Dorsey's Block has released 'Buzz,' a free Nostr-based platform for developer group chats, aiming to reduce reliance on Slack and GitHub., accessed July 23, 2026, [https://gigazine.net/gsc\_news/en/20260722-block-buzz/](https://gigazine.net/gsc_news/en/20260722-block-buzz/)  
> 14. Adversary Agent: using a hidden agent to keep the main agent safe \- Goose, accessed July 23, 2026, [https://goose-docs.ai/blog/2026/03/31/adversary-mode/](https://goose-docs.ai/blog/2026/03/31/adversary-mode/)  
> 15. Adversary Mode | goose | Your open source AI agent, accessed July 23, 2026, [https://goose-docs.ai/docs/guides/security/adversary-mode/](https://goose-docs.ai/docs/guides/security/adversary-mode/)  
> 16. Intro to Agent Client Protocol (ACP): The Standard for AI Agent-Editor Integration \- Goose, accessed July 23, 2026, [https://goose-docs.ai/blog/2025/10/24/intro-to-agent-client-protocol-acp/](https://goose-docs.ai/blog/2025/10/24/intro-to-agent-client-protocol-acp/)  
> 17. deepagents-acp \- LangChain Reference, accessed July 23, 2026, [https://reference.langchain.com/javascript/deepagents-acp](https://reference.langchain.com/javascript/deepagents-acp)  
> 18. Agent Client Protocol (ACP) \- Docs by LangChain, accessed July 23, 2026, [https://docs.langchain.com/oss/python/deepagents/acp](https://docs.langchain.com/oss/python/deepagents/acp)  
> 19. GitHub \- agentclientprotocol/agent-client-protocol, accessed July 23, 2026, [https://github.com/agentclientprotocol/agent-client-protocol](https://github.com/agentclientprotocol/agent-client-protocol)  
> 20. Agent Client Protocol (ACP): Use Any Coding Agent in Any IDE \- JetBrains, accessed July 23, 2026, [https://www.jetbrains.com/acp/](https://www.jetbrains.com/acp/)  
> 21. Using goose in ACP Clients | goose | Your open source AI agent, accessed July 23, 2026, [https://goose-docs.ai/docs/guides/acp-clients/](https://goose-docs.ai/docs/guides/acp-clients/)  
> 22. ACP Providers | goose | Your open source AI agent, accessed July 23, 2026, [https://goose-docs.ai/docs/guides/acp-providers/](https://goose-docs.ai/docs/guides/acp-providers/)  
> 23. Stop building agents, start harnessing Goose | adam.yml \- maxamillion.sh, accessed July 23, 2026, [https://maxamillion.sh/blog/stop-building-agents-start-harnessing-goose/](https://maxamillion.sh/blog/stop-building-agents-start-harnessing-goose/)  
> 24. Feature: Native ACP provider for Cursor Agent (or ability to define custom ACP binary paths) · Issue \#9691 · aaif-goose/goose \- GitHub, accessed July 23, 2026, [https://github.com/aaif-goose/goose/issues/9691](https://github.com/aaif-goose/goose/issues/9691)  
> 25. "Bring Your Own Agents": Introducing Goose for Guild, accessed July 23, 2026, [https://www.guild.ai/blog/product/bring-your-own-agents-goose](https://www.guild.ai/blog/product/bring-your-own-agents-goose)  
> 26. Recipes | goose | Your open source AI agent, accessed July 23, 2026, [https://goose-docs.ai/docs/guides/recipes/](https://goose-docs.ai/docs/guides/recipes/)  
> 27. Create Reusable AI Agents with Recipes \- YouTube, accessed July 23, 2026, [https://www.youtube.com/watch?v=8rTliYrQ6Iw](https://www.youtube.com/watch?v=8rTliYrQ6Iw)  
> 28. Subagents | goose | Your open source AI agent, accessed July 23, 2026, [https://goose-docs.ai/docs/guides/context-engineering/subagents/](https://goose-docs.ai/docs/guides/context-engineering/subagents/)  
> 29. 9 Best Open Source AI Coding Assistants in 2026, accessed July 23, 2026, [https://www.opensourcealternatives.to/blog/best-open-source-ai-coding-assistants](https://www.opensourcealternatives.to/blog/best-open-source-ai-coding-assistants)  
> 30. Agent harness built with LangChain and LangGraph. Equipped with a planning tool, a filesystem backend, and the ability to spawn subagents \- Reddit, accessed July 23, 2026, [https://www.reddit.com/r/LangChain/comments/1rzcsf4/github\_langchainaideepagents\_agent\_harness\_built/](https://www.reddit.com/r/LangChain/comments/1rzcsf4/github_langchainaideepagents_agent_harness_built/)  
> 31. docs: add top-level ARCHITECTURE.md covering full system design · Issue \#2505 · langchain-ai/deepagents \- GitHub, accessed July 23, 2026, [https://github.com/langchain-ai/deepagents/issues/2505](https://github.com/langchain-ai/deepagents/issues/2505)  
> 32. Native Communication and Coordination Between Peer-Level DeepAgents \#4883 \- GitHub, accessed July 23, 2026, [https://github.com/langchain-ai/deepagents/issues/4883](https://github.com/langchain-ai/deepagents/issues/4883)  
> 33. AssetOverflow/core: Continuous Orthogonal Resonance ... \- GitHub, accessed July 23, 2026, [https://github.com/AssetOverflow/core](https://github.com/AssetOverflow/core)  
> 34. AgentServerACP | deepagents\_acp \- LangChain Reference, accessed July 23, 2026, [https://reference.langchain.com/python/deepagents-acp/server/AgentServerACP](https://reference.langchain.com/python/deepagents-acp/server/AgentServerACP)  
> 35. Agent Client Protocol: Introduction, accessed July 23, 2026, [https://agentclientprotocol.com/get-started/introduction](https://agentclientprotocol.com/get-started/introduction)  
> 36. Deep Agents — Chapter3: Everything Claude Agent Can Do, Plus More? \- Medium, accessed July 23, 2026, [https://medium.com/@shubham.shardul2019/deep-agents-chapter3-everything-claude-agent-can-do-plus-more-each-feature-explained-with-code-dbebc87f83d7](https://medium.com/@shubham.shardul2019/deep-agents-chapter3-everything-claude-agent-can-do-plus-more-each-feature-explained-with-code-dbebc87f83d7)  
> 37. deepagents-acp \- LangChain Reference, accessed July 23, 2026, [https://reference.langchain.com/python/deepagents-acp](https://reference.langchain.com/python/deepagents-acp)  
> 38. deepagents/libs/acp/README.md at main \- GitHub, accessed July 23, 2026, [https://github.com/langchain-ai/deepagents/blob/main/libs/acp/README.md](https://github.com/langchain-ai/deepagents/blob/main/libs/acp/README.md)  
> 39. Goose Documentation \- Goose, accessed July 23, 2026, [https://block-goose.mintlify.app/](https://block-goose.mintlify.app/)  
> 40. Configuration Files | goose | Your open source AI agent, accessed July 23, 2026, [https://goose-docs.ai/docs/guides/config-files/](https://goose-docs.ai/docs/guides/config-files/)  
> 41. ide-integration | deepagents\_acp \- LangChain Reference, accessed July 23, 2026, [https://reference.langchain.com/python/deepagents-acp/ide-integration](https://reference.langchain.com/python/deepagents-acp/ide-integration)  
> 42. \[bug\] goose gets into endless loop with developer extension · Issue \#5155 \- GitHub, accessed July 23, 2026, [https://github.com/aaif-goose/goose/issues/5155](https://github.com/aaif-goose/goose/issues/5155)  
> 43. deep-agents · GitHub Topics, accessed July 23, 2026, [https://github.com/topics/deep-agents](https://github.com/topics/deep-agents)
