# Centralized Glossary of builder-II Terminology

This glossary compiles and defines core terms, concepts, acronyms, and governance mechanisms across builder-II.

---

## 1. Core Architecture & Artifact Pipeline

### Kind
The structural identifier of a builder-II JSON artifact (specified in the `"kind"` field). A `kind` binds the JSON data to an explicit Pydantic schema or dataclass structure (e.g. `builder_ii.patch_proposal`, `builder_ii.verification_execution_plan`, `builder_ii.verification_execution_receipt`).

### Spine
The sequence of artifact files generated during a governed session, visualized inside the **STRATUM** console. It represents the living timeline of actions (Intake $\rightarrow$ Preflight $\rightarrow$ Proposal $\rightarrow$ Approval $\rightarrow$ Execution $\rightarrow$ Evidence $\rightarrow$ Receipt) from start to finish.

### Chain / Chain Integrity
A security model where each generated artifact references the cryptographic SHA-256 content digest of its input artifacts and predecessors in the spine. Tampering with or altering an artifact breaks the chain integrity, causing subsequent validators to fail closed.

### Digest-Bound
Any process, structure, or reference anchored to a cryptographic content hash (SHA-256 digest) of its input files or artifacts. This guarantees that operations act only on explicitly reviewed, unmutated inputs.

### Human-In-The-Loop (HITL)
An explicit interactive approval boundary required before any authority-changing action can execute. In builder-II, approvals are typed at a TTY prompt and bind the exact prefix of the artifact digest.

### Standing Ratification Grants
A governed mechanism allowing an operator to delegate routine re-confirmation friction (e.g. applying previously authored setup plans) without delegating human approval authority. Grants are revocable, scoped, and recorded on the event ledger.

---

## 2. Capability States & Assurance Lattice

builder-II rejects coarse "passive vs. active" switches. Authority is capability-scoped and categorized by two orthogonal dimensions: **Capability Promotion State** and **Assurance State**.

### The 8 Capability Promotion States:
1. **`NOT_STARTED`:** Concept identified, no artifacts or code implemented.
2. **`DESIGN_ONLY`:** Architecture decision record (ADR) or request for comment (RFC) written; no code.
3. **`ARTIFACT_ONLY`:** Typed schema and serialization logic exist; no runtime execution.
4. **`PASSIVE_FOUNDATION`:** Validator, parser, and passive planning tools exist; does not invoke runtime side effects.
5. **`IMPLEMENTED_ON_BRANCH`:** Feature implemented in an isolated branch; undergoing review.
6. **`PR_OPEN`:** Pull request opened against `main`; undergoing CI gate validation.
7. **`MERGED_BUT_NOT_OPERATIONAL`:** Merged into `main`, but gated behind an unpromoted capability switch or disabled default.
8. **`OPERATIONALLY_VERIFIED`:** Cleared all eight promotion gates (docs, tests, command surface, failure mode, human boundary, output artifact, rollback path, verification path) and verified by machine-checked evidence.

### The 9 Assurance Lattice States:
*Authoritative for risk interpretation of operational capabilities:*

1. **`PASSIVE_ARTIFACT_VERIFIED`:** Generates, validates, or renders artifacts. Starts no processes, spawns no subshells, and mutates no repository state.
2. **`LOCAL_STATE_MUTATION_VERIFIED`:** Mutates local metadata files or configuration within `.builder/` under explicit operator action.
3. **`READ_ONLY_RUNTIME_VERIFIED`:** Starts a local runtime or tool under an explicit read-only policy that rejects write mutations.
4. **`BOUNDED_EXECUTION_VERIFIED`:** Executes commands inside a fixed, pre-approved envelope (`shell=False`, fixed argv, environment allowlist, timeout, digest-bound receipt). **Note: Bounded invocation is NOT a sandbox.**
5. **`MUTATION_WITH_ROLLBACK_VERIFIED`:** Writes to the target repository source tree or working copy, behind an interactive digest-bound approval, preflight snapshot, and reverse-patch rollback generator.
6. **`LIVE_PROVIDER_VERIFIED`:** Dispatches requests over the network to external model providers through the governed execution gateway with budget accounting.
7. **`DEMO_ONLY_VERIFIED`:** Verified strictly against a disposable, detached fixture worktree in a controlled demo environment.
8. **`BLOCKED_BY_EVIDENCE`:** Execution blocked because a prerequisite evidence check, verification receipt, or security gate failed.
9. **`SAFETY_CRITICAL_PROHIBITED`:** Permanently denied by system invariant (e.g. autonomous remote Git pushes, unprompted arbitrary shell execution).

---

## 3. Adapters & Governance Seams

### Codename Goose Adapter
The approved operator runtime substrate for interactive pairing. Goose supplies local session mechanics, while builder-II provides policy, manifests, and authority boundaries.

### deepagents
An optional inner orchestration harness for graph planning, subagent decomposition, and task delegation. Deep Agents operates behind builder-II work artifacts and approval boundaries.

### deepagents Forge
An interactive wizard (TUI or headless) used to author new deepagent specifications (`DeepAgentSpec`) with explicit capability gates.

### MCP (Model Context Protocol) Seam
An inventory-first, deny-by-default capability seam for external tools and resources. Capabilities must be inventoried, policy-checked, and wrapped before invocation.

### Model Execution Gateway
The unified runtime gateway through which all model requests (local MLX, Ollama, Google Vertex AI, OpenAI-compatible endpoints) flow, enforcing routing policy, budget successors, and receipt generation.

### WRP (Workload-Router-Pool)
The advanced model routing control plane (`builder-model-policy` / `builder-wrp`) that evaluates task complexity, privacy tier, and budget constraints to select optimal models.

---

## 4. The Builder's Signet & Core Doctrines

### The Third Door
Rejecting the false choice between powerless safety theater (Door 1) and unconstrained autonomous chaos (Door 2). The Third Door is **powerful because governed**: automating aggressively where authority does not change, while placing tamper-evident, digest-bound friction at every authority boundary.

### Mechanical Sympathy
Designing software with direct awareness of the host hardware and existing developer tools. Optimized for Apple Silicon unified memory footprints (2GB–7GB local models), native Git workflows, and zero simulated abstractions.

### Semantic Rigor
Preserving exact meaning across all system claims:
- *Planned* is not *executed*.
- *Executed* is not *verified*.
- *Verified* is not *promoted*.
- *Artifact* is not *authority*.
- *Model output* is not *approval*.
- *Subagent output* is not *truth*.

