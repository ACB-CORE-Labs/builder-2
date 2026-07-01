# HITL Patch Application Specification

## Platform Identity & Scope

builder-II is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench/UI/UX, and not a second CORE runtime. CORE is only a target profile.

This document is the **design specification** for a future Human-In-The-Loop (HITL) patch proposal and application path. In its current phase (`DESIGN_ONLY`) all patch-application and runtime capabilities remain strictly inactive. No patches are applied by any current code path.

## Spec Artifact Definition

The specification artifact kind is:

```
builder_ii.hitl_patch_proposal
```

### Current State

| Field | Value |
|---|---|
| `mode` | `DESIGN_ONLY` |
| `runtime` | `DISABLED` |
| `artifact_is_authority` | `false` |

The artifact is not authority. It cannot grant permissions, bypass system guards, or trigger any runtime action.

---

## Future Governed Patch Path

When the capability is promoted to active runtime only after all required gates pass and a human operator explicitly authorizes it, the governed state machine must traverse the following eight stages in order:

1. **patch proposal** — A structured proposal artifact is created describing the exact diff, target file(s), target repository, rationale, and expected effect. No file is touched at this stage.
2. **human approval record** — An explicit human approval record is created and persisted. Automated approval is not permitted. The record is the authority for all downstream stages.
3. **preflight record** — Environment, target file hashes, and safety constraints are captured. The preflight record is validated against the proposal before any further action.
4. **explicit patch application request** — A separate, intentional invocation (distinct from proposal creation) requests application, bound to an approved preflight state. This is not automatic.
5. **patch application receipt** — The result of the application (success, failure, diff applied, file hashes before/after, timing) is captured in a receipt artifact.
6. **rollback artifact** — A rollback artifact is produced alongside every application receipt, containing the inverse patch and the pre-application snapshot necessary to restore the target to its prior state.
7. **verification record** — Post-application state is verified against expected hashes and a test gate. If verification fails, the human-gated rollback path becomes available through its own approval/request/receipt chain; rollback is not automatic.
8. **handoff/postflight** — The full chain (proposal → approval → preflight → receipt → rollback → verification) is indexed into the artifact chain and a handoff record is produced.

---

## Denied Current Behavior

While in `DESIGN_ONLY` mode the runtime strictly denies all of the following:

* no patch application
* no source writes
* no file mutation
* no git mutation
* no commit/push
* no shell execution
* no subprocess execution
* no model execution
* no network/MCP execution
* no Goose runtime activation
* no deepagents runtime
* no CORE Workbench/UI coupling

---

## Required Future Gates

All of the following quality and safety gates must pass before any promotion to active runtime patch application:

* docs
* tests
* command surface
* failure mode
* human approval boundary
* output artifact
* rollback path
* verification path

---

## Governance & Authority

| Field | Value |
|---|---|
| `capability_state` | `DESIGN_ONLY` |
| `runtime_execution` | `DISABLED` |
| `patch_application` | `DISABLED` |
| `source_writes` | `DISABLED` |
| `file_mutation` | `DISABLED` |
| `git_mutation` | `DISABLED` |
| `commit_push` | `DISABLED` |
| `shell_execution` | `DISABLED` |
| `subprocess_execution` | `DISABLED` |
| `model_execution` | `DISABLED` |
| `network_mcp_execution` | `DISABLED` |
| `goose_runtime_activation` | `DISABLED` |
| `deepagents_runtime` | `DISABLED` |
| `artifact_is_authority` | `false` |
| `core_workbench_coupling` | `NONE` |
