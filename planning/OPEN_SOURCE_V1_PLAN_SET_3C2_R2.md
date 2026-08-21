# Open-Source V1 Plan Set 3C2-R2 — Product-Path and Evidence-Binding Correction

STATUS: `PLANNED_ONLY_AWAITING_HITL_APPROVAL`

CORRECTION_BASE: `1cc037c7bf8d43112f51e7b1ec3cef78e99e8c6f`

CORRECTION_BASE_TREE: `eae020003216d3cf88dbb43aaec709e01aea9dae`

PARENT_3C2_R1_PLAN_SHA256: `521db80d32eadfda5bee2f81ab036f7b3459d8e1acaf1b0560a03eef4ae70917`

PARENT_3C2_PLAN_SHA256: `b103d9db4fdc68daae2b9d316ccc1c37187d120611f24d952d60cd880713453a`

## Boundary and purpose

This is a passive correction plan only. It grants no implementation, approval,
mutation, rollback, shell, Git, delivery, push, pull-request, merge, or promotion
authority. The published 3C2 and 3C2-R1 commits remain immutable review evidence;
this plan does not rewrite, amend, or reinterpret them.

3C2-R2 is warranted because independent hosted review of R1 found four remaining
integration and evidence defects:

1. The production `builder start` path still calls `GooseRuntimeHarness.close`
   without approved patch evidence. A legitimate MCP patch mutation therefore
   becomes unexplained drift at close even though the lower-level close primitive
   works when a test manually injects evidence.
2. Goose close derives its approved path whitelist from the temporary,
   non-digest-bound `<patch-apply-dir>/apply.patch`, rather than from canonical
   validated evidence such as `rollback_plan["rollback_patch_ref"]` or the exact
   validated proposal scope.
3. Outer MCP persistence failure returns `Path("")` for nonexistent receipt and
   event locations. The server serializes both as `"."`, falsely implying evidence
   locations where no outer receipt or event was appended.
4. R1 validates five canonical artifact schemas but does not completely cross-bind
   the proposal, approval, production verification receipt, reverse patch,
   pre-apply target state, apply receipt, postflight, rollback artifacts, and ledger
   to the exact invocation and persisted bytes.

The R2 correction must preserve the existing single-verb governance shape:

```text
artifact -> validate -> approve -> execute -> receipt/postflight -> delivery

already-created proposal + independent approval + production verification receipt
        -> MCP patch_apply transport
        -> exactly one canonical apply_hitl_patch call
        -> validated and completely cross-bound canonical evidence
        -> session-bound discovery by the real builder start close path
        -> valid close for exactly the approved mutation, or fail-closed drift
```

Planned is not executed, executed is not verified, verified is not promoted,
artifact is not authority, and model output is not approval. R2 does not move any
capability across a promotion boundary.

The following remain unreachable or forbidden: MCP approval minting, automatic
rollback, generic shell, caller-selected target/output, caller-supplied close-time
evidence injection as authority, a second patch executor, capability promotion,
push, PR creation, and merge.

## Current-code findings validated at the correction base

The correction base resolves locally to the pinned tree above, with parent
`83cf9cf137ea40d3884ed3cd0967b242c7532a6b`. The parent 3C2 plan digest was
recomputed from the locally preserved plan. The R1 plan was read from the exact
correction-base commit and its supplied digest is pinned above for implementation-
time revalidation.

The relevant implementation seams are:

- `builder_ii/cli/main.py` and `builder_ii/cli/goose_cli.py` call
  `harness.close(...digest...)` without a successful session patch outcome.
- `builder_ii/adapters/goose/goose_runtime_harness.py` accepts an optional opaque
  `approved_patch_evidence` value, validates five referenced artifacts, then parses
  sibling `apply.patch` to construct the set of approved target paths.
- `builder_ii/adapters/mcp/governed_services.py::_patch_apply` places each canonical
  result under the session-scoped MCP artifact namespace and returns its five
  canonical refs. That namespace and the persisted session MCP receipt/ledger are
  the source from which close can discover successful session-bound evidence.
- `run_service` catches outer receipt/event persistence failures after patch apply,
  preserves canonical mutation refs in a typed recovery result, and returns
  `Path("")` placeholders for evidence that was not persisted.
- `builder_ii/adapters/mcp/server.py::_tools_call` blindly stringifies those paths
  into transport metadata and does not explicitly report `evidence_appended` for
  the normal result tuple.
- `_patch_evidence_errors` validates apply receipt, postflight, rollback plan,
  rollback bundle, and patch ledger schemas and checks several downstream refs,
  but it does not bind every controlled input/ref and persisted byte sequence to
  the same invocation.
- Canonical `apply_hitl_patch` writes the forward patch artifact separately and
  binds its SHA-256 through `rollback_plan["rollback_patch_ref"]`; the temporary
  `apply.patch` used by `git apply` is not the close-time authority surface.

No implementation is authorized by these findings. Before any separately approved
implementation, revalidate the exact base/tree, both parent plan digests, branch,
worktree cleanliness, call sites, validators, schemas, and hosted branch state.

## Bounded implementation envelope after separate HITL approval

Only the files and directly affected tests/docs necessary for the four corrections
below are in scope. Discovery of a new authority surface, executor, artifact
vocabulary, promotion claim, or unrelated defect requires a new passive plan and
approval.

### 1. Wire the real product path to session-bound patch evidence

Make the canonical `builder start` close path automatically discover the validated
successful `patch_apply` outcome belonging to the current Goose/MCP session,
server-controlled target identity, launch receipt, and artifact namespace. Do not
make an agent, model, recipe, or arbitrary caller responsible for passing an opaque
evidence object that can select which mutation close blesses.

The discovery mechanism must:

- read only canonical persisted MCP session receipts/ledger entries and referenced
  canonical patch artifacts below the exact session namespace;
- accept only a succeeded `patch_apply` result whose outer evidence was durably
  appended and whose complete canonical evidence chain revalidates;
- bind the patch result to the current session ID, target name/repo, launch/close
  lifecycle, and exact canonical artifact bytes;
- reject missing, failed, denied, mutation-uncertain, stale, cross-session,
  cross-target, duplicate/ambiguous, substituted, or unpersisted outcomes;
- allow no-mutation sessions to retain the existing valid no-mutation close;
- keep unexplained additions, deletions, modifications, index/HEAD changes, and
  worktree drift invalid;
- execute no patch, rollback, Git mutation, or approval action during close.

If retaining `approved_patch_evidence` as an internal compatibility primitive is
necessary, it must not be the production authority path and must not permit caller-
selected evidence to override canonical session discovery.

Add a real `builder start` integration test that performs the governed path through
MCP and proves approved apply followed by close is valid. A direct harness unit test
with manually supplied evidence is insufficient.

### 2. Derive approved paths only from digest-bound canonical evidence

Remove `apply.patch` from close-time authority and whitelist derivation. Approved
paths must be reconstructed from a canonically validated, digest-bound source,
preferably the persisted forward patch referenced by
`rollback_plan["rollback_patch_ref"]`, or the exact validated proposal scope/diff if
that contract is proven complete and byte-bound.

The selected source must be reloaded from its canonical path, checked for regular-
file/no-symlink confinement, SHA-256 matched against the validated referring
artifact, and cross-bound to the patch digest, proposal, target, pre-apply state,
apply receipt, rollback bundle, and ledger. Parsing must fail closed on malformed,
escaping, ambiguous, rename/copy, binary, or otherwise unsupported path forms.

Changing only the unbound temporary `apply.patch` after canonical apply must have no
effect on approved close scope. Changing the bound forward patch or its proposal
scope must invalidate close; it must never silently widen the whitelist.

### 3. Make outer-persistence metadata truthful

Represent absent outer receipt/event evidence as absence, not a filesystem path.
Use an explicit typed return/result shape or nullable paths so the actual MCP server
response reports, for receipt and event failures after mutation:

```text
status            = failed
mutation_state    = APPLIED_OR_MAY_HAVE_BEEN_APPLIED
evidence_appended = false
receipt_path      = absent/null
event_path        = absent/null
rollback_executed = false
```

Retain every real, discoverable canonical patch evidence ref and persisted-byte
digest inside the typed `mutation_uncertain` result. Do not fabricate an outer
receipt/event, do not serialize empty paths as `"."`, do not claim normal success,
and do not collapse post-mutation uncertainty into a pre-execution denial or generic
no-mutation error. If only one of receipt/event was durably appended, report each
field's actual state precisely and do not overstate the pair as complete evidence.

Exercise both receipt-persistence and event-persistence lesions through the actual
`GovernedMcpServer` response, not only the `run_service` tuple.

### 4. Complete invocation-wide evidence cross-binding

Extend canonical validation/cross-binding without creating a parallel MCP artifact
schema. Before returning success and again before Goose close accepts mutation,
prove one exact invocation binds:

- the persisted proposal bytes/digest, exact target identity, exact scope/diff,
  patch digest, and pre-apply HEAD/tree/index/worktree state;
- the independent approval bytes/digest, approved proposal digest, patch digest,
  validity window, and consumption semantics;
- the production verification execution receipt bytes/digest, target repo,
  executed/valid state, and proposal/approval/patch binding required by its contract;
- the persisted forward patch referenced by `rollback_patch_ref`, including its
  exact SHA-256 and path confinement;
- the apply receipt, postflight, rollback plan, rollback bundle, and patch ledger,
  including every applicable path plus persisted-file SHA-256 reference;
- the post-apply target state and every ledger subject ref relevant to the canonical
  mutation chain;
- the session MCP service receipt/result that close consumes.

Successful projection must fail closed if proposal, approval, verification receipt,
forward patch, pre-state, or any downstream canonical artifact is substituted,
rewritten, stale, cross-target, cross-session, path-mismatched, digest-mismatched, or
not the exact persisted bytes consumed by this call. Validation after mutation that
cannot establish the complete chain must return `mutation_uncertain`, preserve real
canonical refs, append outer failure evidence when possible, and never roll back
automatically.

Use existing canonical validators and artifact writers. If a canonical schema lacks
a field needed to express a required binding, change that canonical contract and all
its writer/validator/consumer/tests together; do not patch the gap with response text,
filename trust, or an MCP-only sidecar.

### 5. Preserve the authority invariants

R2 must retain and directly test:

```text
MCP_APPROVAL_MINTING       = UNREACHABLE
MCP_AUTOMATIC_ROLLBACK     = UNREACHABLE
MCP_GENERIC_SHELL          = UNREACHABLE
SECOND_PATCH_EXECUTOR      = NONE
CALLER_SUPPLIED_TARGET     = REJECTED
CALLER_SUPPLIED_OUTPUT     = REJECTED
VERIFICATION_CLASS         = production execution receipt only
EXECUTOR_CALL_COUNT        = exactly one on valid admission
CLOSE_MUTATION_AUTHORITY   = canonical session evidence only
```

Spies must continue to prove that MCP/Goose transport and close code do not directly
invoke `git apply`, `subprocess.run`/`Popen` for patch execution, approval creation,
or rollback. Goose lifecycle/export subprocess use remains separately bounded and
is not a patch executor.

## Required R2 lesions and qualification

Focused and integration tests must include real persisted artifacts wherever the
canonical lane is under test and prove at least:

```text
builder start -> real session-bound patch evidence -> valid close
builder start -> mutation with no valid evidence -> invalid close

tamper apply.patch only
    -> MUST NOT widen approved close scope

tamper bound rollback patch / proposal scope
    -> close invalid

outer MCP receipt failure after mutation
    -> mutation_uncertain
    -> evidence_appended=false
    -> no fake receipt/event paths

outer event failure after mutation
    -> same truth

proposal/approval/verification ref substitution after apply
    -> no successful canonical projection
```

Also prove:

- no-mutation `builder start` still closes validly;
- approved mutation plus any additional unexplained edit/add/delete/HEAD/index drift
  closes invalidly;
- cross-session, cross-target, stale, duplicate, missing, denied, failed,
  mutation-uncertain, and outer-unpersisted patch outcomes are not close authority;
- bound forward-patch digest/path/symlink substitution and malformed/escaping paths
  fail closed;
- proposal, approval, verification receipt, apply receipt, postflight, rollback plan,
  rollback bundle, forward patch, and ledger substitutions each prevent success;
- pre-HEAD/tree/index/worktree and post-state claims are checked against canonical
  evidence and the real target, not merely response text;
- receipt-only, event-only, and neither-appended partial persistence metadata reports
  exactly what exists;
- repeated invocation cannot reapply an already consumed approval or bypass target
  drift protections;
- inventory rejects generic shell, Git, argv, environment, timeout, target, output,
  rollback, approval-minting, and arbitrary close-evidence inputs;
- rollback execution count remains zero in every R2 path.

## Verification and delivery gates after implementation approval

Use a new isolated clean worktree rooted exactly at the correction base. Preserve
the existing published commits and unrelated dirty state. Recompute both parent plan
digests and this plan's SHA-256 before source changes; require all three plan files to
remain unchanged during implementation.

Run the smallest relevant tests while iterating, then the complete affected lanes,
documentation/matrix truth checks, diff checks, and mandatory local-only CI battery:

```bash
uv run pytest -q \
  tests/test_mcp_plan_set_3c2_patch_apply.py \
  tests/test_hitl_patch_apply.py \
  tests/test_hitl_patch_rollback.py \
  tests/test_goose_runtime_harness.py \
  tests/test_cli.py
uv run ruff check builder_ii tests
uv run builder-platform audit-docs
uv run builder-platform matrix
git diff --check
bash scripts/ci.sh --receipt .builder/artifacts/plan-set-3c2-r2-gate-battery-receipt.json
```

If the actual `builder start` product-path tests live elsewhere at implementation
time, include those exact modules too; do not treat the illustrative list above as a
substitute for test discovery. Do not create, enable, await, or cite GitHub Actions.

The final qualification artifact must bind the R2 commit/tree and parent
`1cc037c7bf8d43112f51e7b1ec3cef78e99e8c6f`, this plan digest, both parent plan
digests, stable pre/post HEAD and target state, focused/full test counts, local gate
receipt canonical digest and file SHA-256, the actual product-path result, every
required lesion, and the authority invariants above. No push, PR, merge, or promotion
is authorized by this plan.

## Rollback strategy

Source rollback is limited to a normal revert of the separately approved R2
correction commit on its feature branch. Never rewrite or delete the published 3C2
or 3C2-R1 commits or hosted review history. Target patch rollback remains the
separate governed `rollback_hitl_patch` approval/execution seam and is not part of
MCP apply, product-path discovery, or Goose close.

## Explicit state at plan completion

```text
3C2_CORE_ARCHITECTURE              = SOUND
3C2_INITIAL_HOSTED_REVIEW          = FAILED_CORRECTED_BY_R1
3C2_R1_HOSTED_REVIEW               = FAIL_CORRECTION_REQUIRED

R1_APPROVAL_EXPIRY_FIX             = PASS
R1_CANONICAL_ARTIFACT_VALIDATION   = SUBSTANTIALLY_PASS
R1_MUTATION_UNCERTAIN_CORE         = PASS
R1_GOOSE_CLOSE_PRIMITIVE           = PASS
R1_CANONICAL_PRODUCT_PATH          = FAIL
R1_APPROVED_SCOPE_BINDING          = FAIL
R1_OUTER_PERSISTENCE_METADATA      = FAIL
R1_COMPLETE_CROSS_BINDING          = INCOMPLETE

3C2_PR_READINESS                   = NO
3C2_MERGE_READINESS                = NO
3C2_R2_PLANNING                    = COMPLETE_PLANNED_ONLY
3C2_R2_IMPLEMENTATION              = NOT_AUTHORIZED
3C2_R2_PUSH                        = NOT_AUTHORIZED
3C2_R2_PR                          = NOT_AUTHORIZED
3C2_R2_MERGE                       = NOT_AUTHORIZED

MCP_APPROVAL_MINTING               = UNREACHABLE
MCP_AUTOMATIC_ROLLBACK             = UNREACHABLE
MCP_GENERIC_SHELL                  = UNREACHABLE
SECOND_PATCH_EXECUTOR              = NONE
```
