# Open-Source V1 Plan Set 3D — Git Status and Delivery Handoff via MCP

STATUS: `PLANNED_ONLY_AWAITING_DIGEST_BOUND_HITL_APPROVAL`

PLAN_BASE: `b328b31a3039c14eba237cf192fbce3edf25c77a`
PLAN_BASE_TREE: `893283893b1a3b9b48cd918f3d5abb4155dafdff`

## Boundary and purpose

This is one passive planning artifact for the remaining Plan Set 3 MCP slice. It
does not reopen 3C3, mint approval, promote a capability, commit, push, invoke
`gh`, create or update a pull request, force-push, execute generic shell, or
perform any other delivery mutation. `3C3` is closed; Plan Set 6 remains the
separate authority boundary for governed GitHub delivery.

The planned surface closes the remaining Plan Set 3 inventory gap by allowing
Goose to inspect exact repository state, assemble a bounded delivery-readiness
handoff, and receive a truthful refusal at the delivery boundary:

```text
git_status()
    -> canonical read-only Git-state artifact
    -> repository identity preflight

delivery_prepare(...)
    -> bind target/status/identity/verification/patch evidence
    -> passive delivery-readiness handoff

delivery(...)
    -> HUMAN_APPROVAL_REQUIRED / DELIVERY_EXECUTION_NOT_ADMITTED
    -> no commit, push, gh, PR, force-push, or shell
```

The governing grammar remains:

```text
artifact -> validate -> approve -> execute -> receipt/postflight -> delivery
```

3D implements only the artifact, validation, and passive handoff portions. It
does not create a Plan-6 delivery plan, delivery approval vocabulary, executor,
or delivery receipt.

## Current-code findings

The inspected repository establishes the following reusable foundations:

- `builder_ii.core.git_state` defines `builder_ii.git_state_record`, including
  branch, exact `commit_sha`, clean/dirty state, modified paths, untracked
  paths, and fail-closed validation. Its governance fields pin source writes,
  shell, runtime, model execution, and artifact authority off.
- `builder_ii.lifecycle.setup.operator_lane` already captures the target branch,
  HEAD, porcelain-derived changed paths, and canonical Git-state artifact in an
  evidence directory. 3D must reuse this capture logic or extract a shared
  read-only service rather than create a second Git subsystem.
- `builder_ii.core.repository_identity` performs the read-only canonical-remote
  preflight against `origin` and records mismatch/error without granting action
  authority. Delivery preparation must bind this evidence and fail closed on
  missing or non-canonical identity.
- `builder_ii.adapters.mcp.server` and `governed_call` currently expose the MCP
  transport and governed evidence ceremony for the existing inventory. The new
  status and preparation tools must use the same thin transport/service shape;
  they must not broaden the generic executor or add a shell path.
- `docs/plan/OPEN_SOURCE_V1_COMPLETION_PLAN.md` assigns local commit, external
  push, pull-request creation, review, and delivery receipts to Plan Set 6.
  That assignment is an explicit 3D non-goal, not an omission to repair here.

The plan base and tree above are hosted-base bindings supplied for this plan.
Implementation, if separately approved, must begin from a fresh clean isolated
worktree independently checked against those exact coordinates.

## Bounded implementation envelope after separate HITL approval

The approval must bind this file's exact SHA-256 and authorize the complete
remaining local 3D unit through focused tests, exact-tip local CI, and a
PR-ready passive handoff. It does not authorize Plan Set 6 GitHub mutation or
capability promotion. Only the directly affected MCP service/transport,
canonical read-only evidence composition, focused tests, and required docs or
truth-registry entries may change.

### 1. Canonical read-only Git status

Add a thin MCP `git_status` service with a closed input schema. It supplies the
Builder-II-selected target and output/session namespace; callers cannot select
an arbitrary repository, output path, command, environment, timeout, or shell
argv. Capture branch, exact HEAD, clean/dirty state, modified paths, untracked
paths, and repository identity using the existing canonical primitives.

The service must validate the resulting `builder_ii.git_state_record` before
projection, preserve truthful dirty state, and make no source, index, remote,
credential, or memory mutation. It must not silently normalize away untracked,
renamed, ignored, or malformed status evidence.

### 2. Passive delivery preparation

Add a thin MCP `delivery_prepare` service accepting only references to already
persisted evidence in the controlled session/artifact namespace. The bounded
handoff must bind, at minimum:

- canonical repository identity and match/error result;
- target name, branch, exact HEAD, clean/dirty state, and changed-path lists;
- the exact tree/diff or patch evidence available from an already completed
  verification/patch lane, without inventing missing evidence;
- verification receipt/plan references and their canonical digests;
- the missing Plan-6 authority and next admissible human action.

Preparation is a proposal/result artifact, not authority. It must refuse
missing, stale, substituted, traversal-escaping, absolute, symlinked, or
non-regular evidence references before any delivery effect. It must not create a
commit message authority, approval artifact, delivery receipt, PR metadata
authority, or inferred readiness claim. A dirty tree, remote mismatch, missing
verification evidence, or target drift produces a bounded not-ready result.

### 3. Delivery boundary refusal

Expose a `delivery` MCP surface only as an explicitly refused boundary if the
inventory contract requires a callable name. It must return typed
`HUMAN_APPROVAL_REQUIRED` / `DELIVERY_EXECUTION_NOT_ADMITTED` output and explain
that Plan Set 6 must separately authorize local commit, push, and pull-request
operations. It may reference the passive preparation artifact but may not
interpret it as approval.

The import and call graph must make the following unreachable from 3D:

```text
git commit       = unreachable
git push         = unreachable
gh               = unreachable
PR create/update = unreachable
force-push       = unreachable
generic shell    = unreachable
approval minting = unreachable
```

Do not add a second executor, `delivery_plan`, commit/push/PR approval types,
delivery receipt, `gh` adapter, or rollback strategy for published history.
Those are Plan Set 6 concerns.

### 4. Evidence and Goose projection

Project the canonical status, identity, preparation, refusal, policy, and event
references through the existing governed MCP/session evidence chain. Every
returned digest must be computed by the canonical artifact serializer/validator
used by the underlying service. Do not emit a parallel receipt claiming that
MCP performed delivery. Do not report delivery readiness or success when the
canonical evidence is absent, invalid, stale, or cannot be persisted.

## Required adversarial qualification after implementation approval

Focused tests must prove:

- `git_status` returns a schema-valid canonical record for clean and dirty
  repositories, including modified and untracked paths, and performs no writes;
- repository identity matches only the canonical remote and fails closed for a
  missing, mismatched, malformed, or inaccessible remote;
- preparation binds exact evidence digests and rejects substitution, stale
  HEAD/tree state, missing verification, dirty/unexpected paths, traversal,
  absolute paths, symlink escape, non-regular files, extra authority-shaped
  arguments, and caller-selected targets/outputs;
- preparation never mints approval and never reaches commit, push, `gh`, shell,
  subprocess delivery, or any Plan-6 executor;
- `delivery` returns the typed approval-required refusal, with no mutation and
  no success/readiness inflation;
- the actual `GovernedMcpServer` inventory and dispatch project canonical
  evidence, ledger/event state, digests, target identity, and refusal state;
  and
- denial paths leave the target worktree, index, HEAD, remote, and session
  authority state unchanged.

## Verification and delivery gates after implementation approval

Run focused tests during implementation, then the exact-tip local qualification
on the final implementation SHA/tree:

```bash
uv run pytest -q tests/test_git_state.py tests/test_repository_identity.py tests/test_mcp_server.py tests/test_mcp_cli.py tests/test_operator_lane.py
uv run ruff check builder_ii tests
uv run builder-platform audit-docs
uv run builder-platform matrix
bash scripts/ci.sh
```

The final evidence bundle must identify the exact implementation SHA/tree,
focused and full local gate results, MCP inventory, canonical status and
identity references, preparation/refusal evidence, and the explicit Plan Set 6
handoff. No push, pull-request creation/update, merge, or promotion is
authorized by this plan.

## Explicit state at plan completion

```text
3C3                         = CLOSED
MORE_3C3_HARDENING          = STOP
3D_PASSIVE_PLANNING         = AUTHORIZED
3D_IMPLEMENTATION           = AWAITING_DIGEST_BOUND_PLAN_APPROVAL
MCP_GIT_STATUS              = NOT_YET_ADMITTED
MCP_DELIVERY_PREPARE        = NOT_YET_ADMITTED
MCP_DELIVERY_EXECUTION      = HUMAN_APPROVAL_REQUIRED
PLAN_SET_6_GIT_MUTATION     = NOT_AUTHORIZED
CAPABILITY_PROMOTION        = NOT_AUTHORIZED
```
