# Centralized Glossary of builder-II Terminology

To help new operators navigate the builder-II architecture and codebase, this glossary compiles and defines core terms, concepts, and acronyms used throughout the documentation.

---

## 1. Core Architecture & Artifact Pipeline

### Kind
The structural identifier of a builder-II JSON artifact (represented by the `"kind"` field). A `kind` binds the JSON data to a specific Pydantic schema or dataclass structure (e.g., `builder_ii.patch_proposal` or `builder_ii.preflight_record`).

### Spine
The horizontal or vertical sequence of artifact files generated during a governed session, visualized inside the **STRATUM** console. It represents the living timeline of actions (Intake → Preflight → Proposal → Evidence → Receipt) from start to finish.

### Chain / Chain Integrity
A security model where each generated artifact references the SHA-256 content digest of its predecessor in the spine. This creates a cryptographically linked ledger. Any manual editing or tampering with an artifact breaks the chain integrity (e.g. showing "Chain Valid: FALSE").

### Digest-Bound
Any process, structure, or reference that is anchored to a cryptographic content hash (SHA-256 digest) of its input files or artifacts. This ensures that the system works only with explicitly declared and unmutated assets.

### Speculative vs. Promoted
* **Speculative:** A capability, command, or role that is in design or prototype phase and has not cleared all automated gates.
* **Promoted:** A capability that has cleared its verification gates, passed CI requirements, and is officially active in the runtime control plane. These states are defined in `docs/CAPABILITY_PROMOTION.md`.

---

## 2. Adapters & Harnesses

### deepagents
A sandboxed subagent runtime environment. Unlike generic LLM chat windows, deepagents are defined by strict capability gates, system personas, human approval boundaries, and verification targets.

### deepagents Forge
An interactive wizard (TUI or headless) used to generate new deepagent configuration manifests (`DeepAgentSpec`).

### The deepagents Bridge
The interface layer bridging external model engines to local tool registries and sandboxes, ensuring that no agent can execute arbitrary shell commands without matching verification profiles.

### WRP (Workload-Router-Pool)
The advanced workload-routing control plane under `builder_ii/cli/wrp_cli.py`. It uses mathematical modeling (adjoint/forward operators, experience stores, and MSDA gates) to distribute tasks efficiently across models while verifying security compliance.

### Convention Layer
The compilation substrate that translates builder-II high-level governed representations down into Codename-Goose-native runtime actions and manifests.

---

## 3. Execution & Philosophy

### The Third Door
The engineering pillar stating that *planned ≠ executed ≠ verified ≠ promoted*. No action or model output possesses inherent authority; every authority change requires separate docs, tests, validation gates, and human approval boundaries.

### Builder's Signet
The core design doctrine stating that builder-II is optimized for Apple Silicon (M1/M2/M3) unified memory footprints and maintains mechanical sympathy by sandbox-isolating external cloud egress.

### Passive vs. Active Modes
* **Passive:** The control plane generates plans, checks configurations, and audits schemas, but does not execute modifying system commands or call external model runtimes directly.
* **Active:** The control plane is fully enabled to route tasks, invoke agents, run test verification loops, and apply patches.

### B9
An internal reference code designating the Governed Operator Golden Path milestone (Phase 9 of the initial platform roadmap).
