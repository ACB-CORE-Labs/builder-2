# Open-Source V1 Plan Set 3C2-R1 — Governed MCP Apply/Goose Close Correction

STATUS: `PLANNED_ONLY_AWAITING_HITL_APPROVAL`

CORRECTION_BASE: `83cf9cf137ea40d3884ed3cd0967b242c7532a6b`

CORRECTION_BASE_TREE: `930effb976ebfbf7afd96d126b5d1ae29a64f2b0`

PARENT_3C2_PLAN_SHA256: `b103d9db4fdc68daae2b9d316ccc1c37187d120611f24d952d60cd880713453a`

## Boundary and purpose

This is a passive correction plan only. It grants no implementation, approval,
mutation, rollback, shell, Git, delivery, merge, or promotion authority. The
published 3C2 candidate remains immutable review evidence; this plan does not
amend or reinterpret it.

3C2-R1 is required because hosted review found four blocking defects in the
published transport and its newly discovered canonical Goose product path:

1. `builder_ii/adapters/mcp/governed_services.py::_patch_apply` calls the real
   `approval_is_expired` without its required keyword-only `now` argument. The
   existing focused test avoided the defect by replacing the function with a
   signature-changing lambda, so a real approved invocation fails before the
   canonical executor.
2. MCP validates only `patch_apply_receipt.json`; postflight, rollback plan,
   rollback bundle, and patch-ledger evidence are only existence-checked or not
   projected. The adapter therefore does not provide validated canonical
   evidence as required by the 3C2 contract.
3. The `mutation_uncertain` projection does not cover the full post-mutation
   window. A successful canonical mutation followed by missing canonical
   evidence or failure while `run_service` persists the outer receipt/event can
   fall into generic MCP error handling without mutation truth or canonical
   references.
4. `recipes/governed-readonly.yaml` still instructs Goose that patch application
   and target mutation are out of scope, while
   `builder_ii/adapters/goose/goose_runtime_harness.py::close` unconditionally
   creates a no-mutation postflight. An approved MCP mutation would therefore
   make the canonical Goose close invalid.

The correction must preserve the original 3C2 shape:

```text
already-created proposal + independent approval + production verification receipt
        -> MCP patch_apply transport
        -> exactly one canonical apply_hitl_patch call
        -> validated canonical apply/postflight/rollback/ledger evidence
        -> governed Goose close accepts only exact session-bound approved mutation
```

The following remain unauthorized: MCP approval minting, automatic rollback,
generic shell or caller-supplied command authority, caller-selected target or
output, a second patch executor, capability promotion, push, PR creation, and
merge.

## Current-code findings validated at the correction base

The correction base and tree above were inspected locally. The parent 3C2 plan
exists at `planning/OPEN_SOURCE_V1_PLAN_SET_3C2.md` and hashes to the pinned
`PARENT_3C2_PLAN_SHA256`.

The relevant implementation boundaries are:

- `builder_ii/adapters/mcp/governed_services.py` contains the narrow
  `patch_apply` service, server-controlled target/output selection, canonical
  executor delegation, and outer service-receipt persistence.
- `builder_ii/governance/hitl/hitl_patch_apply.py` owns canonical apply,
  postflight, apply receipt, rollback plan/bundle, reverse-patch evidence, and
  patch-ledger emission. Its real approval-expiry API is
  `approval_is_expired(approval, *, now: int)`.
- `builder_ii/governance/hitl/hitl_patch_ledger.py` provides the canonical
  `validate_hitl_patch_ledger_record_file` validator. The canonical apply module
  provides `validate_patch_apply_receipt_file` and rollback-bundle validation;
  the applicable postflight and rollback-plan validators must be located and
  reused rather than replaced with MCP-specific schemas.
- `builder_ii/adapters/mcp/server.py` converts service exceptions into generic
  failed-service responses. R1 must carry a typed post-mutation recovery result
  through this boundary when outer evidence persistence fails.
- `builder_ii/adapters/goose/goose_runtime_harness.py` snapshots the target in
  `launch_governed` and `launch_readonly`, then `close`/`close_async` compares
  the complete target and always emits `builder_ii.no_mutation_postflight`.
- `recipes/governed-readonly.yaml` is the canonical governed Goose recipe. It
  currently describes a passive/read-only MCP inventory and explicitly denies
  patch application and target mutation.
- Existing 3C2 tests are in
  `tests/test_mcp_plan_set_3c2_patch_apply.py`; they currently contain only
  three tests and heavily replace admission validators. Existing canonical
  apply, rollback, MCP, and Goose tests must be extended with real-artifact and
  product-path coverage rather than making the same mocked substitutions.

No implementation is authorized by these findings. Any implementation must be
revalidated against the exact correction base and this plan's digest after a
separate HITL approval.

## Bounded implementation envelope after separate HITL approval

Newly discovered Goose recipe/close paths are in scope only for this bounded
correction. Any additional authority model, runtime surface, or unrelated
promotion change requires a new amended plan and approval.

### 1. Repair real approval admission

In the MCP service, use the real canonical expiry API with an explicit current
time, preserving the canonical function signature and time semantics. Add an
integration test that constructs or loads real persisted proposal, approval, and
production `builder_ii.verification_execution_receipt` artifacts and reaches the
actual pre-delegation admission path. The test must prove:

- valid, unexpired artifacts reach `apply_hitl_patch` exactly once;
- expired, substituted, unbound, target-mismatched, demo-verification, and
  invalid artifacts are denied before the executor;
- no test double changes the callable signature of a canonical validator.

Approval remains out-of-band. R1 must not mint, infer, or interactively request
approval, and must not alter the canonical operator approval implementation.

### 2. Validate and project the complete canonical evidence set

After `apply_hitl_patch` returns, reload the exact output artifacts and invoke
the existing canonical validators for:

- `patch_apply_receipt.json`;
- `postflight_record.json`;
- `rollback_plan.json`;
- `rollback_bundle.json`;
- `patch_ledger_record.json`.

Validate cross-bindings among target identity, proposal/approval/verification
refs, patch digest, target HEAD/tree, apply receipt, postflight, rollback plan,
rollback bundle, reverse-patch evidence, and ledger subject refs using the
canonical artifact contracts. Return bounded references and persisted-byte
digests to these canonical files. Do not invent a parallel MCP mutation receipt
vocabulary or treat filenames/existence as evidence.

If canonical evidence is absent, malformed, stale, mismatched, or cannot be
reloaded after the executor may have run, return a typed
`mutation_uncertain`/`APPLIED_OR_MAY_HAVE_BEEN_APPLIED` projection with every
discoverable canonical reference and no success result. Do not report “no
mutation,” and do not automatically invoke `rollback_hitl_patch`.

### 3. Preserve mutation truth through outer MCP persistence

Carry the canonical patch-apply result and its evidence references through
`run_service`, `_service_receipt`, event persistence, and `server.py` error
projection. If the canonical executor has successfully mutated or may have
mutated the target and outer policy/receipt/event persistence fails, return a
typed failed transport result that explicitly states mutation occurred or may
have occurred and retains canonical evidence references/digests. It must:

- never become an ordinary successful MCP result;
- never collapse into a generic no-mutation or pre-execution denial;
- never automatically roll back;
- keep rollback execution count at zero;
- remain distinguishable from refusal before mutation and apply failure before
  mutation.

The recovery path may use a bounded in-memory result or a Builder-II-controlled
failure artifact, but it must not manufacture canonical apply evidence. Any
outer receipt/event that is persisted must truthfully classify MCP as the
transport and the canonical HITL receipt as mutation authority/evidence.

### 4. Reconcile the governed Goose recipe and close semantics

Update only the canonical governed Goose recipe, harness, associated receipt/
postflight contracts, and directly affected tests/docs needed to express this
bounded rule:

- the recipe may expose the already-admitted `patch_apply` service as a
  HITL-approval-gated mutation seam, while retaining no shell, generic write,
  approval minting, rollback, Git, or alternate executor authority;
- Goose instructions must require proposal, pause for independent approval,
  production verification receipt, canonical apply, verification/evidence
  reload, and close inside the governed chain;
- `close` and `close_async` must accept only target changes proven by exact,
  session-bound canonical patch-apply evidence for this session and target;
- every unexplained target addition, deletion, or modification must still make
  close invalid;
- approved patch evidence must itself be validated, bound to the session and
  server target identity, and included in the close/postflight evidence;
- close must not execute rollback or silently bless arbitrary mutation.

The resulting close artifact must truthfully distinguish no mutation,
approved canonical mutation, and unexplained drift. The existing no-mutation
behavior remains valid for sessions without an approved patch evidence chain.

### 5. Preserve the original authority invariants

R1 must retain and directly test:

```text
MCP_APPROVAL_MINTING       = UNREACHABLE
MCP_AUTOMATIC_ROLLBACK     = UNREACHABLE
MCP_GENERIC_SHELL          = UNREACHABLE
SECOND_PATCH_EXECUTOR      = NONE
CALLER_SUPPLIED_TARGET     = REJECTED
CALLER_SUPPLIED_OUTPUT     = REJECTED
VERIFICATION_CLASS         = production execution receipt only
EXECUTOR_CALL_COUNT        = exactly one on valid admission
```

Spies must prove MCP/Goose transport code does not directly invoke `git apply`,
`subprocess.run`/`Popen` for patch execution, approval construction, or rollback.
The Goose harness's own process lifecycle/export subprocess is not a patch
executor and must remain separately bounded.

## Required R1 qualification

Focused and integration tests must prove, with real persisted artifacts where
the canonical lane is under test:

- valid approval -> MCP -> exactly one canonical `apply_hitl_patch` call;
- expiry API is called with the required `now` keyword and real approval
  expiry is enforced;
- demo receipt, expired approval, substituted approval, target mismatch, and
  production verification target mismatch fail before execution;
- canonical receipt, postflight, rollback plan, rollback bundle, and ledger
  are each validated and cross-bound before success is returned;
- missing/corrupt/mismatched canonical evidence after apply returns typed
  mutation uncertainty with discoverable evidence and no rollback call;
- outer MCP receipt/event persistence failure after successful mutation retains
  mutation uncertainty and canonical refs, with no normal success and no
  rollback;
- repeated invocation cannot reapply the same proposal or bypass target/HEAD
  drift protections;
- MCP inventory rejects retired tools, extra fields, generic shell, target,
  output, Git, argv, environment, timeout, rollback, and approval-minting
  inputs;
- Goose's governed recipe advertises the admitted patch seam without shell or
  alternate authority;
- positive end-to-end product path: an approved patch traverses governed
  Goose/MCP, canonical apply and evidence validation complete, and
  `close` returns a valid close/postflight bound to the approved patch evidence;
- negative Goose close lesions: unexplained file edit, deletion, addition,
  target/session evidence substitution, stale evidence, or missing evidence
  invalidates close;
- target tree/index/HEAD/status and canonical artifact digests are inspected,
  not merely response text.

## Verification and delivery gates after implementation approval

Use a new isolated clean worktree rooted at the exact correction base. Recompute
this plan's SHA-256 before source changes and require it to remain unchanged.
Run focused tests for MCP/HITL/Goose, then the affected documentation and matrix
checks, `git diff --check`, and the mandatory local gate battery:

```bash
uv run pytest -q \
  tests/test_mcp_plan_set_3c2_patch_apply.py \
  tests/test_hitl_patch_apply.py \
  tests/test_hitl_patch_rollback.py \
  tests/test_goose_runtime_harness.py
uv run ruff check builder_ii tests
uv run builder-platform audit-docs
uv run builder-platform matrix
bash scripts/ci.sh --receipt .builder/artifacts/plan-set-3c2-r1-gate-battery-receipt.json
```

The final qualification artifact must bind the R1 commit/tree, parent
`83cf9cf137ea40d3884ed3cd0967b242c7532a6b`, this plan digest, the parent 3C2
plan digest, stable pre/post HEAD, focused/full counts, gate receipt canonical
digest and file SHA-256, and the authority/close invariants above. No push,
PR, merge, or promotion is authorized by this plan.

## Rollback strategy

Source rollback is limited to a normal revert of the separately approved R1
correction commit on its feature branch. Never rewrite the published 3C2
candidate or its hosted review history. A target patch rollback remains the
separate `rollback_hitl_patch` approval/execution seam and is not part of MCP
apply or Goose close.

## Explicit state at plan completion

```text
3C2                         = PUBLISHED_FAILED_REVIEW_PENDING_CORRECTION
3C2_R1_PLANNING             = AUTHORIZED
3C2_R1_IMPLEMENTATION       = NOT_AUTHORIZED
MCP_PATCH_APPLY             = EXISTING_BUT_NOT_PR_READY
MCP_APPROVAL_MINTING        = UNAUTHORIZED
MCP_ROLLBACK_EXECUTION      = UNAUTHORIZED
MCP_GENERIC_SHELL           = UNAUTHORIZED
SECOND_PATCH_EXECUTOR       = FORBIDDEN
GOose_APPROVED_CLOSE        = NOT_YET_ADMITTED
```
