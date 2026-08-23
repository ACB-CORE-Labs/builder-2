# HITL Patch Application Specification

## Platform Identity & Scope

builder-II is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench/UI/UX, and not a second CORE runtime. CORE is only a target profile.

This document specifies the Human-In-The-Loop (HITL) patch proposal and application path. The proposal, approval, application, and rollback mechanics execute against a target repository (`builder-hitl propose-patch` / `approve-patch` / `apply-patch` / `rollback`), gated by an exact digest-bound approval artifact, a clean target working tree, exact target HEAD and verification-receipt binding, and command-authority enforcement before any I/O. The operator-invoked lane is `OPERATIONALLY_VERIFIED` with assurance `MUTATION_WITH_ROLLBACK_VERIFIED`; it remains Tier 3 (`hitl_runtime_candidate`) and is not an unattended or autonomous write capability.

## Spec Artifact Definition

The specification artifact kind is:

```
builder_ii.hitl_patch_proposal
```

### Current State

| Field | Value |
|---|---|
| `capability_state` (platform matrix) | `OPERATIONALLY_VERIFIED` |
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

The promoted scope is only the operator-invoked, approval-gated lane. Autonomous or unattended application remains disabled and is not implied by this state.

### Passive MCP proposal boundary

The MCP `patch_proposal` service shares the canonical proposal binder with
`builder-hitl propose-patch`. The caller supplies patch material, but never the authoritative
patch digest: Builder-II hashes the exact UTF-8 diff bytes, parses a conservative exact file scope,
hashes the exact bytes of a verification receipt resolved beneath the server-controlled artifact
root, binds the server-configured target, and chooses the proposal output location. Only after the
persisted proposal reloads and validates does MCP return `HUMAN_APPROVAL_REQUIRED` with the bound
proposal reference, digests, target, and exact scope.

That decision is state evidence, not approval. MCP does not expose `approve_patch`, `apply_patch`,
rollback, generic shell, or generic write tools. The former environment-flagged MCP
`propose_patch` apply bridge and advertised `run_shell` surface are retired and cannot be restored
by setting `BUILDER_MCP_GOVERNED_APPLY`. Human approval and explicit apply remain out-of-band
operator steps; Plan Set 3C2 is separate and not authorized by this passive service.

## Proposal schema v2 and verification binding

New proposals use `builder_ii.hitl_patch_proposal` schema v2. They bind `target_head_sha`
to the exact clean source state and `verification_receipt_file_sha256` to the exact successful,
mutation-free pre-apply verification receipt. The receipt reconstructs and validates its
referenced plan and approval; the patch approval canonical digest then seals the complete
proposal, including the diff, target, HEAD, and receipt digest.

Schema v1 is retained only for passive historical recognition. `apply-patch` refuses v1
proposals with recovery instructions to regenerate under v2 and obtain a fresh interactive
approval. No approved v1 artifact is auto-upgraded.

## Textual patch envelopes

The operator-authored canonical proposal lane admits UTF-8 unified diffs up to and
including 128 KiB (`131072` bytes). This is a bounded capacity limit on the existing
inline `unified_diff` representation, not a new authority class or schema version.
The exact diff bytes remain sealed by `patch_digest`, reparsed into `exact_scope`,
bound into the interactive approval, applied only after the existing clean-tree and
HEAD checks, and retained byte-for-byte for governed reverse application.

The passive MCP `patch_proposal` ingress remains independently bounded to 64 KiB
(`65536` bytes). MCP refuses a larger `unified_diff` before proposal creation even
though the shared canonical binder can accept the larger operator envelope. Changing
the operator ceiling therefore does not silently enlarge service ingress.

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
| `capability_state` | `OPERATIONALLY_VERIFIED` |
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
