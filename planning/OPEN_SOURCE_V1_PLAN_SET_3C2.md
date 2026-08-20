# Open-Source V1 Plan Set 3C2 — HITL-Approved Patch Apply via MCP

STATUS: `PLANNED_ONLY_AWAITING_HITL_APPROVAL`

PLAN_BASE: `69de04fd78084be43f147b16959690e830b3da70`

PLAN_BASE_TREE: `b1704559cd4a4946c30ff5734abecd6c46a3a4fa`

## Boundary and purpose

This is a passive planning artifact only. It grants no implementation, approval,
mutation, rollback, shell, Git, delivery, or promotion authority. 3C1 is treated as
closed; 3C2 is planned but not admitted.

The planned capability is one narrow MCP transport operation:

```text
patch_apply(proposal_path, approval_path, verification_receipt_path)
```

The MCP adapter may consume already-persisted, independently human-created approval
evidence and a bound verification receipt. It must delegate exactly once to the
canonical `apply_hitl_patch(...)` lane. It must not become an executor, approval
minter, target selector, rollback executor, or generic command surface.

```text
existing 3C1 proposal
  + separate operator-created approval
  + bound verification receipt
        -> MCP patch_apply transport
        -> canonical apply_hitl_patch exactly once
        -> canonical apply receipt, postflight, rollback plan/bundle, ledger
        -> bounded references/digests projection
```

The following remain explicitly unauthorized: MCP approval minting, MCP rollback
execution, generic shell or subprocess access, caller-selected targets or outputs,
and any second patch executor, including resurrected `governed_apply.py` behavior.

## Current-code findings validated for this plan

The named canonical boundaries are present in the inspected checkout:

- `builder_ii/governance/hitl/hitl_patch_apply.py::apply_hitl_patch` re-enforces
  command authority before I/O, validates proposal/receipt/approval bindings, checks
  clean-tree and HEAD/TOCTOU state, performs the governed apply, and emits canonical
  postflight, apply-receipt, rollback, and ledger evidence.
- `rollback_hitl_patch` is a separate source-mutation boundary with its own approval,
  reverse-patch binding, drift protection, and recovery evidence. 3C2 never invokes it.
- `builder_ii/governance/hitl/hitl_patch_approval.py` documents that the constructor
  creates data but is not evidence of human origin; the promoted mint path is the
  interactive operator CLI. MCP therefore accepts an artifact but never constructs it.
- The inspected MCP server currently imports the historical governed apply adapter and
  dispatches `propose_patch` to `run_gated_patch_apply`.  3C2 implementation must remove
  or make unreachable that route, prove all callers, and expose only the new governed
  service through the transport.
- The current MCP policy shape includes `mutation_allowed` and
  `requires_approval_for_mutation`, but the read-only service receipt currently reports
  mutation as disabled.  The implementation must make the smallest schema/receipt
  extension that truthfully represents approval-gated mutation without treating a
  policy or receipt as authority.

The requested plan base was supplied as the hosted `main` SHA/tree above. The local
clone did not contain that SHA as a readable Git object during planning (`git show
69de04fd...` failed), and the working checkout is dirty and at another commit. No
claim of local exact-base verification is made. Before implementation, refresh and
prove `main == origin/main`, branch from that exact base, and revalidate every finding.

## Implementation envelope after separate HITL approval

Implementation authority, if later granted for this exact plan, is limited to the
following responsibilities and their focused tests. Newly discovered paths or a
different authority model require an amended plan and a new approval.

### 1. One canonical service and one executor

Add a governed MCP `patch_apply` service in the existing MCP service layer. It accepts
exactly `proposal_path`, `approval_path`, and `verification_receipt_path`; rejects extra
properties and all authority-shaped alternatives. It resolves all three as regular,
non-symlink files beneath the already-admitted Builder-II artifact namespace, rejects
traversal and symlink escape, and binds exact persisted bytes.

The server supplies target identity and the Builder-II-selected output directory:

```text
<platform_artifact_root>/sessions/<session>/mcp/patch-apply/<unique-id>/
```

The caller cannot provide target repo/name, output directory, digests, diff contents,
Git arguments, shell/argv/environment, timeout, TTL, approver, or rollback controls.
The service calls `apply_hitl_patch` exactly once with the three controlled artifact
paths and the chosen output directory. MCP contains no `git apply`, `subprocess`, patch
parser/executor, approval construction, or rollback call.

### 2. Approval and policy truth

Validate the supplied approval through the canonical apply lane and preserve the
out-of-band human boundary. MCP must not call `create_hitl_patch_approval`, the
interactive approval command, or any model confirmation path.

Define the smallest truthful policy/service-receipt representation for
HITL-approval-gated mutation. `requires_approval_for_mutation` is a requirement, not
authority; the receipt must distinguish transport admission from canonical mutation
and must not claim `target_repo_writes = DISABLED` after a successful apply. Existing
read-only services retain their existing claims.

### 3. Canonical evidence projection and failure truth

After the canonical call returns, reload and validate the existing apply receipt,
postflight, rollback plan/bundle, and patch-ledger evidence. Return only bounded
references, digests, target identity, and truthful outcome/state projections. Do not
manufacture a parallel MCP apply receipt that claims MCP independently performed the
mutation.

Preserve the distinction between refusal before mutation, apply failure, and failure
after mutation while emitting recovery/evidence references where the canonical lane
produces them. Do not convert post-mutation evidence failure into `no mutation`.
Partial or failed evidence is not success and never yields an approval-ready result.

Do not automatically invoke `rollback_hitl_patch`; rollback remains a later, separately
approved governed seam.

### 4. Inventory, transport, and documentation

Remove retired/ambiguous MCP inventory and dispatch paths for `propose_patch`, generic
apply, rollback, combined proposal-and-apply, and `run_shell`. Ensure no import graph
from MCP reaches `governed_apply.py`, approval minting, subprocess, or generic shell.
Keep the operator CLI apply and rollback surfaces intact.

Update only the exact policy, receipt, service, command-surface, security, promotion,
and generated-truth documentation selected by call-site and truth-pin tracing. Do not
flip a promotion state from documentation or tests alone.

## Required adversarial qualification

Focused tests must prove both positive canonical delegation and fail-closed behavior for:

- approval/proposal/verification substitution, digest mismatch, expiry, target mismatch,
  dirty tree, HEAD drift, TOCTOU drift, and invalid command authority;
- traversal, absolute paths, symlink escape, non-regular files, controlled-artifact
  namespace violations, output-directory failure, ledger corruption, and evidence reload
  or persistence failure;
- `git apply` failure, post-mutation receipt/postflight/ledger failure, repeated
  invocation, and truthful pre-/post-mutation state reporting;
- retired tool names, extra/unknown arguments, target/output/shell/argv/environment/
  timeout/rollback inputs, and attempts to mint approval;
- spies proving MCP calls no `git`, `subprocess`, approval constructor/CLI, alternate
  patch executor, or rollback executor; and that canonical `apply_hitl_patch` is called
  exactly once on the admitted path.

The tests must inspect target HEAD/tree/index/status and artifact digests, not only MCP
response text. Every denial must preserve the target. A post-mutation failure must
retain the canonical lane's recovery truth.

## Verification and delivery gates after implementation approval

Use an isolated clean branch from the exact plan base. Run focused MCP/HITL/policy tests,
then documentation and matrix checks where affected, and finally the mandatory local
gate battery:

```bash
uv run pytest -q <focused HITL/MCP suites>
uv run ruff check builder_ii tests
uv run builder-platform audit-docs
uv run builder-platform matrix
bash scripts/ci.sh
```

The final receipt must bind the exact implementation SHA/tree, focused and full local
gate results, canonical apply/postflight/rollback/ledger evidence, tool inventory, and
pre/post target identity. Green tests do not self-certify approval or promotion. No
push or PR is authorized by this planning artifact.

## Rollback strategy

Before merge, revert only the approved 3C2 service, policy/receipt, transport, test, and
documentation changes on its feature branch. After merge, use a normal revert PR against
the exact merged tip. Never rewrite historical apply or recovery evidence. Rollback of
an applied target patch is not this source rollback strategy and remains separately
bound to rollback approval.

## Explicit state at plan completion

```text
3C1                         = CLOSED
3C2_PLANNING_AUTHORIZED     = YES
3C2_IMPLEMENTATION_AUTHORITY= NO
MCP_PATCH_APPLY             = NOT_YET_ADMITTED
MCP_APPROVAL_MINTING        = UNAUTHORIZED
MCP_ROLLBACK_EXECUTION      = UNAUTHORIZED
MCP_GENERIC_SHELL           = UNAUTHORIZED
SECOND_PATCH_EXECUTOR       = FORBIDDEN
```
