# HITL Patch Application Specification

## Platform Identity & Scope

builder-II is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench/UI/UX, and not a second CORE runtime. CORE is only a target profile.

This document specifies the Human-In-The-Loop (HITL) patch proposal and application path. The proposal, approval, application, and rollback mechanics described below are implemented and execute for real against a target repository (`builder-hitl propose-patch` / `approve-patch` / `apply-patch` / `rollback`), gated at every step by an explicit digest-bound approval artifact, a clean target working tree, and command-authority enforcement (`enforce_command_authority`) checked before any I/O. Code executing under strict HITL gates is not the same as the platform declaring the capability promoted: the completion-plan matrix still tracks this capability as `MERGED_BUT_NOT_OPERATIONAL` (candidate tier `hitl_runtime_candidate`, Tier 3 — see `docs/CAPABILITY_PROMOTION.md`) pending an evidence-gated closure review. This document uses candidate/not-enabled phrasing throughout; it does not assert promotion.

## Spec Artifact Definition

The specification artifact kind is:

```
builder_ii.hitl_patch_proposal
```

### Current State

| Field | Value |
|---|---|
| `capability_state` (platform matrix) | `MERGED_BUT_NOT_OPERATIONAL` |
| `promotion_tier` | `hitl_runtime_candidate` (Tier 3) |
| `runtime` | Executes only via explicit, separately-invoked, human-gated commands; not autonomous, not platform-promoted |
| `artifact_is_authority` | `false` |

The artifacts in this pipeline are not authority: they cannot grant permissions, bypass system guards, or trigger runtime action on their own. Even when `builder-hitl apply-patch` genuinely executes `git apply` against a target repository, it does so only because a human explicitly invoked that command against a bound, unexpired approval artifact — never because a proposal, approval, or receipt artifact "declares" the action authorized.

---

## Governed Patch Path

The pipeline below reflects what is implemented today, distinguished from work still open in the completion plan:

1. **patch proposal** — *Implemented* (`builder-hitl propose-patch` / `builder_ii/governance/hitl/hitl_patch_proposal.py`). A structured proposal artifact is created describing the exact diff, patch digest, and target repository. No file is touched at this stage.
2. **human approval record** — *Implemented* (`builder-hitl approve-patch` / `builder_ii/governance/hitl/hitl_patch_approval.py`). The operator is shown the diff and the full patch digest, then types the first characters of the digest at a TTY prompt — an attention control, not a cryptographic signature. There is no non-interactive approval mode; scripting the prompt would collapse `planned ≠ approved`. The resulting approval artifact is bound to the exact proposal content digest and patch digest, and carries an expiry.
3. **preflight record** — *Implemented as a pre-apply verification receipt* for the bounded `platform_status` / `docs_audit` profiles (`builder_ii/lifecycle/candidate/verification_execution_runner.py`), validated against the proposal's target repository before apply proceeds. Broader target-code-executing profiles (`pytest_full` / `builder_full`) remain gated pending the completion plan's ratified execution-risk envelope.
4. **explicit patch application request** — *Implemented* (`builder-hitl apply-patch` / `builder_ii/governance/hitl/hitl_patch_apply.py`). A separate, intentional invocation (distinct from proposal or approval) applies the patch, bound to the approved proposal and a valid verification receipt. It refuses on a dirty target working tree, an unbound or expired approval, or a patch-digest mismatch.
5. **patch application receipt** — *Implemented*. Records success or failure, the pre-apply HEAD SHA, and content digests of the proposal, approval, and verification receipt.
6. **rollback artifact** — *Implemented*. A rollback plan and reverse patch are generated automatically before apply, and the apply step records a post-apply working-tree fingerprint on the plan. Rollback is itself a governed mutation: `builder-hitl approve-rollback` mints a distinct approval bound to the exact rollback plan (same digest-prefix attention control as `approve-patch`, carrying an expiry), and `builder-hitl rollback` requires it — the machine-generated rollback plan no longer doubles as its own authorization. Before running `git apply -R`, rollback re-fingerprints the target tree against the recorded post-apply state and refuses on drift; it also refuses on a reverse-patch digest mismatch. Any refusal (drift or a failed reverse apply) writes a rollback-failure receipt carrying a recovery block — the pre-apply HEAD SHA, the exact `git reset --hard <sha>` restore command with its data-loss warning, and a chain-invalidation marker — so a failed rollback instructs rather than strands.
7. **verification record** — *Partial*. The pre-apply verification receipt is bound into the apply receipt as verification evidence; the rollback-side working-tree drift preflight is implemented (see item 6), while a dedicated post-apply verification record remains open completion-plan work.
8. **handoff/postflight** — *Implemented* for postflight recording; the full proposal → approval → apply → rollback chain is indexed for `builder-chain verify` / `verify_artifact_chain`.

None of the above changes this pipeline's platform promotion state. The capability remains `MERGED_BUT_NOT_OPERATIONAL` / `hitl_runtime_candidate` until the evidence-gated matrix flip described in the completion plan.

---

## Current Behavior Boundary

The following remain strictly denied by every artifact and command in this pipeline, regardless of invocation:

* autonomous or unattended patch application — no non-interactive approval mode exists by design
* commit or push — apply leaves an uncommitted working-tree diff for the operator to review and commit themselves
* shell or subprocess execution beyond the fixed `git apply` / `git status` / `git rev-parse` invocations
* model execution
* network/MCP execution
* Goose runtime activation
* deepagents runtime
* CORE Workbench/UI coupling

---

## Required Promotion Gates

All of the following quality and safety gates must show verified evidence before this capability is promoted to `enabled` (see `docs/CAPABILITY_PROMOTION.md` §2):

* docs
* tests (including unmocked end-to-end coverage — open completion-plan work)
* command surface
* failure mode
* human approval boundary
* output artifact
* rollback path
* verification path

A capability existing, executing under HITL gates, and passing some of these gates individually does not itself constitute promotion. Promotion is a single evidence-backed matrix flip reviewed against all gates at once, not a gradual accretion of claims.

---

## Governance & Authority

| Field | Value |
|---|---|
| `capability_state` | `MERGED_BUT_NOT_OPERATIONAL` |
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

These flags describe artifact/spec *authority*, not whether the underlying action ever executes through any code path: they mean this specification and its artifacts grant no ongoing or autonomous authority for the named capability. The one-time, human-gated execution that `builder-hitl apply-patch` performs is authorized solely by the operator's explicit invocation and digest confirmation at the moment it happens — never by a document or artifact declaring it so.
