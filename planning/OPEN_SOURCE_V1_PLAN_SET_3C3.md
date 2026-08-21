# Open-Source V1 Plan Set 3C3 — HITL-Approved Rollback via MCP

STATUS: `PLANNED_ONLY_AWAITING_HITL_APPROVAL`

PLAN_BASE: `380767ffccdaa2d1c8b2479c1964c4b07f7e1bf1`
PLAN_BASE_TREE: `88f1ffb1b30740c17266aac071d2323308bed214`

## Boundary and purpose

This is a passive planning artifact only. It grants no implementation, approval,
mutation, rollback, shell, Git, delivery, push, pull-request, merge, or promotion
authority. Plan Set 3C2 is closed; 3C3 implementation is not authorized.

The planned capability is one narrow MCP rollback transport operation:

```text
rollback(rollback_plan_path, rollback_reverse_patch_path, rollback_approval_path)
```

The transport may consume an already-created canonical rollback plan/bundle and an
independently human-created, plan-bound rollback approval. It must delegate exactly
once to `rollback_hitl_patch(...)`, then project the canonical receipt, ledger, and
post-state evidence into the governed Goose/session evidence chain.

```text
existing canonical rollback plan/bundle
  + separate operator-created rollback approval
  + exact post-apply target state
        -> thin MCP rollback transport
        -> exactly one canonical rollback_hitl_patch(...)
        -> canonical rollback receipt / ledger / post-state
        -> bounded Goose/session evidence projection
```

The following are explicitly forbidden:

```text
MCP_ROLLBACK_APPROVAL_MINTING = FORBIDDEN
AUTOMATIC_ROLLBACK             = FORBIDDEN
SECOND_ROLLBACK_EXECUTOR       = FORBIDDEN
GENERIC_SHELL                  = FORBIDDEN
CALLER_SELECTED_TARGET         = FORBIDDEN
CALLER_SELECTED_OUTPUT         = FORBIDDEN
```

## Current-code findings

The inspected checkout establishes the following existing boundaries:

- `builder_ii/governance/hitl/hitl_patch_apply.py::rollback_hitl_patch` is the
  canonical rollback executor. It enforces command authority before the rollback
  lane, validates the rollback plan, binds the reverse-patch digest, checks the
  required pre-apply HEAD and post-apply worktree fingerprint, refuses drift before
  touching the target, applies the reverse patch, verifies restoration, and emits the
  canonical rollback receipt and `EVENT_PATCH_ROLLED_BACK` ledger record.
- `builder_ii/governance/hitl/hitl_rollback_approval.py` defines a distinct approval
  artifact bound to the exact rollback-plan and patch digests, with expiry checks.
  Its data constructor is not a human boundary; MCP must not call it or mint approval.
- `builder_ii/adapters/mcp/server.py` exposes the existing MCP inventory and dispatch
  but has no rollback service. The implementation must add the smallest service-layer
  seam without introducing a second executor or bypassing the canonical lane.
- Existing rollback and drift tests cover the canonical lane and should be reused as
  invariants rather than duplicated as a new rollback implementation.

The drafting checkout may be dirty or stale and is not implementation authority. Any
3C3 implementation MUST begin in a new isolated clean worktree rooted exactly at
commit `380767ffccdaa2d1c8b2479c1964c4b07f7e1bf1`, whose tree is
`88f1ffb1b30740c17266aac071d2323308bed214`. The implementation worktree must be
independently checked clean and exact-base before any implementation action. The
pinned hosted base and tree are planning bindings, not implementation authorization.

## Bounded implementation envelope after separate HITL approval

Only directly affected MCP service/transport code, focused tests, and exact
documentation/truth-registry entries may change. Discovery of a new authority surface,
executor, artifact vocabulary, promotion claim, or unrelated rollback defect requires
a new passive plan.

### 1. Thin rollback service

Add one governed MCP rollback service accepting only the already-persisted canonical
rollback plan, reverse patch, and separate rollback approval references. Reject extra
properties and authority-shaped alternatives. Resolve inputs only within the
Builder-II-controlled session/artifact namespace; reject traversal, absolute-path
escape, symlink escape, non-regular files, substitution, and caller-selected target or
output paths.

The service supplies target identity and a Builder-II-controlled output directory,
calls `rollback_hitl_patch(...)` exactly once, and contains no `git apply`, subprocess,
patch parser, approval constructor, target selector, or alternate rollback executor.

### 2. Approval and state boundary

Require the separately created rollback approval and let the canonical executor
revalidate schema, plan/patch binding, expiry, command authority, and post-apply drift.
MCP must never mint, infer, or upgrade approval from a rollback plan, patch receipt,
model output, or caller confirmation.

The service must distinguish refusal before mutation, rollback execution failure,
post-mutation evidence failure, and verified restoration. Automatic retry and automatic
rollback are forbidden.

### 3. Canonical evidence projection

Reload and validate the canonical rollback receipt and ledger record after the executor
returns. Return bounded canonical references, digests, target identity, rollback state,
restoration/post-state facts, and truthful session/event evidence. Do not create a
parallel MCP rollback receipt that claims MCP performed the mutation. Do not report
success when receipt or ledger persistence is incomplete, and preserve recovery-bearing
failure evidence produced by the canonical lane.

### 4. Inventory, Goose projection, and documentation

Expose only the new rollback service in the MCP inventory, retain the operator rollback
CLI, and ensure the MCP import graph reaches only the canonical rollback executor. Add
the minimum Goose/session evidence projection needed for the governed operator workflow
to inspect, propose, approve, apply, verify, and close the rollback without leaving the
artifact → validate → approve → execute → receipt/postflight chain.

Do not implement Git status, delivery preparation, external GitHub mutation, Plan Set 4,
or capability promotion in 3C3. Do not keep hardening adjacent rollback internals
unless a demonstrated defect prevents the 3C3 exit claim.

## Required adversarial qualification after implementation approval

Focused tests must prove:

- exactly one delegation to `rollback_hitl_patch` on the admitted path;
- approval minting, automatic rollback, alternate executor, shell, target/output
  selection, traversal, absolute paths, symlink escape, extra arguments, and unknown
  tools are refused without target mutation;
- plan, reverse-patch, and approval substitution or digest mismatch; expired approval;
  command-authority refusal; missing rollback fields; HEAD/worktree drift; reverse-patch
  failure; and post-rollback restoration mismatch fail closed;
- the target HEAD/tree/index/status remains unchanged for every pre-mutation denial;
- canonical receipt and ledger references/digests are revalidated and accurately
  projected through the actual `GovernedMcpServer` response, including persistence or
  post-mutation uncertainty; and
- Goose/session evidence is bound to the current session and target, with no invented
  approval or success claim.

## Verification and delivery gates after implementation approval

Use an isolated clean branch from the refreshed exact base. Run focused rollback/MCP/
Goose tests, then affected lint/docs/matrix checks, and finally the mandatory local gate:

```bash
uv run pytest -q <focused rollback/MCP/Goose suites>
uv run ruff check builder_ii tests
uv run builder-platform audit-docs
uv run builder-platform matrix
bash scripts/ci.sh
```

The final receipt must bind the exact implementation SHA/tree, focused and full local
gate results, canonical rollback receipt/ledger evidence, service inventory, target
identity, and pre/post state. No push, PR, merge, or promotion is authorized by this
plan.

## Explicit state at plan completion

```text
3C2                         = CLOSED
3C3_PLANNING_AUTHORIZED     = YES
3C3_IMPLEMENTATION_AUTHORITY= NO
MCP_ROLLBACK                = NOT_YET_ADMITTED
MCP_ROLLBACK_APPROVAL_MINT = FORBIDDEN
AUTOMATIC_ROLLBACK          = FORBIDDEN
SECOND_ROLLBACK_EXECUTOR    = FORBIDDEN
GIT_STATUS_DELIVERY_SLICE   = AFTER_ROLLBACK
PLAN_SET_4                  = NOT_YET
CAPABILITY_PROMOTION        = NOT_AUTHORIZED
```
