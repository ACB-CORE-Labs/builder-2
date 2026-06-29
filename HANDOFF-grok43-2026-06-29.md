# Session Handoff: Founder-Demo Release Closure
Date: 2026-06-29
Stateless Agent ID: grok43 (Antigravity Systems Architect)

This document declares the **Founder-Demo Release Closure** milestone officially complete. It outlines the passive developer governance baseline established for `builder-II`, details verification procedures, and registers the strict authority gates holding the active execution backlog.

---

## 1. The Demo Quickstart Guide

This guide details how a new developer or validator clones the repository, ensures environment parity, runs the repeatable proof harness, and generates the passive founder-demo artifacts.

### Step 1: Clone and Clean Checkout
Clone the builder-II repository and verify the clean working branch:
```bash
git clone https://github.com/AssetOverflow/builder-II.git
cd builder-II
git checkout main
```

### Step 2: Environment Alignment Verification
Verify that Python is pinned to the required version and dependencies are synchronized:
```bash
# Verify Python version (must be >= 3.12.13 and < 3.13)
python -V

# Synchronize virtual environment with lockfile
uv sync
```

### Step 3: Run the v0 Release Proof Harness
Execute the repeatable proof harness to verify the passive-only generation loop on fixture targets:
```bash
uv run python scripts/verify_v0_release.py
```
This produces 13 canonical release proof files under `dist/v0-release-proof` and asserts all core invariants are preserved.

### Step 4: Execute the Founder-Demo Target Command
Generate the actual passive read-only demo artifacts targeting the `core` profile:
```bash
uv run builder-targets readonly-founder-demo core --output .builder/demos/core-readonly
```
This creates the following suite of planning and tracking documents:
* **Target Profile**: `.builder/demos/core-readonly/artifacts/target-profile.json`
* **Workflow Session**: `.builder/demos/core-readonly/artifacts/workflow-session.json`
* **Target Inspection Plan**: `.builder/demos/core-readonly/artifacts/CORE_INSPECTION_PLAN_v1.json`
* **Target Patch Proposal**: `.builder/demos/core-readonly/artifacts/CORE_PATCH_PROPOSAL_v1.json`
* **Target Verification Plan**: `.builder/demos/core-readonly/artifacts/CORE_VERIFICATION_PLAN_v1.json`
* **Event Ledger**: `.builder/demos/core-readonly/artifacts/event-ledger.json`
* **Workflow Status**: `.builder/demos/core-readonly/artifacts/workflow-status.json`

### Step 5: Verify the Event Ledger & Artifact Chain
Verify the cryptographic chain of custody and derived workflow status:
```bash
# Replay event ledger (confirms valid stage transitions)
uv run builder-ledger replay wf-core-readonly-founder-demo --workflows-dir .builder/demos

# Verify cryptographic SHA-256 links between plans
uv run builder-workflow verify-chain wf-core-readonly-founder-demo --workflows-dir .builder/demos
```

---

## 2. The Release Closure Checklist

A strict verification matrix confirming the platform is sealed, stable, and running in a completely passive posture.

| Verification Item | Metric / Target | Status |
| :--- | :--- | :---: |
| **All Unit/Integration Tests Green** | 940/940 tests passing locally | **[PASS]** |
| **Clean Working Tree** | `git status` reports working tree clean, no modified files | **[PASS]** |
| **Spine References Validated** | `builder-workflow verify-chain` reports `valid: true` | **[PASS]** |
| **Event Ledger Validity** | Ledger replays to `chain_verified` with 0 validation errors | **[PASS]** |
| **Runtime Authority Hard-Pinned** | Active runtime/execution flags disabled in all planning outputs | **[PASS]** |
| **No Source Code Mutation** | Proof harness verifies target git state is 100% untouched | **[PASS]** |
| **Doctor Diagnostics Clean** | `builder doctor` passes compliance and recipe validation | **[PASS]** |

---

## 3. The Founder Demo Handoff Report

The `builder-II` platform has successfully completed its passive governance implementation phases. The primary goal of establishing a repeatable, passive workflow spine is fully achieved.

### Enabled Passive Capabilities
1. **Target Adapter Registry**: Resolves `core` target profiles, including their workspace roots and metadata adapters.
2. **Deterministic Inspection Scope**: Outlines read-only inspection limits without capturing file contents.
3. **Cryptographically-Linked Plans**: Creates and links target profiles, session plans, inspection plans, patch proposals, and verification plans using SHA-256 hashes.
4. **Immutable Audit Ledger**: Records state transitions in chronological order from `initialized` to `chain_verified`.
5. **Passive Replay Engine**: Projecting current system status dynamically from the event sequence.
6. **Strict Schema Constraints**: Schema-driven validation rules enforced on all generated artifacts.

### Blocked Runtime Authority Backlog (Authority Promotion Backlog)
To guarantee safety and separation, the following capabilities are explicitly **Blocked** and relegated to the authority promotion backlog:

* **Live MCP (Model Context Protocol)**: External tool/server execution and environment interaction are disabled.
* **Active Patch Application**: Direct modification of target codebase files or automated commits are disabled.
* **Live Goose Orchestration**: Spawning active, tool-using Goose agent processes to execute changes is disabled.
* **Direct Model calling Loops**: Autonomous loops permitting LLMs to invoke shell or write commands are disabled.
* **Unbounded Repository Reads**: Extraction of file contents is blocked (only file path metadata and digests are inspected).

---

## 4. Next Operational Gate Declaration

> [!IMPORTANT]
> **HITL-Approved Verification Execution**
> The **only** approved operational step post-release is "HITL-Approved Verification Execution".
> Any promotion to active execution must run in a heavily sandboxed environment.
> Target repository sources are locked; no automated agent is permitted to write patches or execute shell commands on the local host without explicit, out-of-band Human-in-the-Loop (HITL) cryptographic approval records.

---

## 5. Architectural Invariants Verified

Across all generated artifacts and system tests, the following invariants are strictly enforced:

| Invariant Field | Expected Value | Status | Description |
| :--- | :--- | :---: | :--- |
| `model_execution` | `DISABLED` | Verified | LLM cannot invoke runtime tools or commands |
| `agent_construction` | `DISABLED` | Verified | No autonomous child agents can be constructed |
| `shell_execution` | `DISABLED` | Verified | Subprocess and shell invocation is blocked |
| `command_execution` | `DISABLED` | Verified | Execution of tool commands is disabled |
| `source_writes` | `DISABLED` | Verified | Code writing/editing in target repo is blocked |
| `memory_mutation` | `DISABLED` | Verified | Flat state variables cannot be mutated |
| `artifact_is_authority`| `False` | Verified | Artifacts are plans and reports, not executables |
| `core_workbench_coupling`| `NONE` | Verified | Strict separation from CORE runtime engines |

---

## 6. Exact Test Execution Output

All 940 tests are clean and passing on the `main` branch:

```text
$ uv run pytest
........................................................................ [  7%]
........................................................................ [ 15%]
........................................................................ [ 22%]
........................................................................ [ 30%]
........................................................................ [ 38%]
........................................................................ [ 45%]
........................................................................ [ 53%]
........................................................................ [ 61%]
........................................................................ [ 68%]
........................................................................ [ 76%]
........................................................................ [ 84%]
........................................................................ [ 91%]
........................................................................ [ 99%]
....                                                                     [100%]
940 passed in 6.49s
```
