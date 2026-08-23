# Plan Set 6 — Governed GitHub Delivery

## Current-base binding

This plan is bound to the refreshed hosted base:

```text
HOSTED_MAIN_SHA  = a8d926d557e357e21d54e925f1afc76f0bad4c12
HOSTED_MAIN_TREE = 3ffe2ed1443df231469860f8a58d4fff255a4767
REMOTE           = origin
CANONICAL_REPO  = https://github.com/ACB-CORE-Labs/builder-2
```

The base was refreshed from `origin/main` on 2026-08-23. The implementation
worktree is isolated from the user's dirty checkout and starts at this exact
commit. This artifact is a passive plan and is not authority to mutate Git,
GitHub, the target worktree, or capability-promotion state.

## Current-code findings

Plan Set 3D is already the passive predecessor and must remain the sole owner
of these concerns:

- `builder_ii.core.git_state.capture_git_state` emits and validates the
  canonical read-only `builder_ii.git_state_record`.
- `builder_ii.core.repository_identity.check_repository_identity` performs
  the canonical read-only remote identity preflight.
- `builder_ii.adapters.mcp.governed_services._delivery_prepare` reconstructs
  the durable patch/application/verification chain and returns a passive
  readiness handoff.
- The existing MCP `delivery` boundary returns
  `HUMAN_APPROVAL_REQUIRED`, performs no actions, and identifies the missing
  `PLAN_SET_6_GIT_MUTATION` authority. It must be updated only so that the
  stale “Set 6 does not exist” wording is no longer asserted after this plan is
  implemented; it must remain unable to mint approval or choose delivery
  parameters.
- `builder_ii.tui.projections.run_projection` is a read-only projection of
  canonical evidence and currently understands only the 3D passive delivery
  pair. It may project Set-6 artifacts and stages but must not mutate Git or
  GitHub or become approval authority.
- `builder_ii.governance.ledger.artifact_index_records` is the canonical kind
  registry/validator owner. New delivery kinds must be registered there and
  reconstructed through the existing artifact/event/state indexes.
- `builder_ii.cli.main` exposes the primary Typer command surface but has no
  normal-user `builder deliver [RUN]` command. The new surface must route to
  the canonical delivery owner rather than create a second executor.
- Plan Set 4's STRATUM lifecycle remains
  `PREPARE -> PLAN -> APPROVE -> EXECUTE -> VERIFY -> DELIVER/PROMOTE`; STRATUM
  remains a read-only evidence/operator projection.
- Plan Set 5 is merged and frozen. Model routing, Goose model routing, Deep
  Agents execution, MLX benchmarking, gateway policy, and physical
  methodology are outside this plan.

## Governing model and exact remaining seam

The missing capability is one delivery lineage with three independently
authorized effect boundaries:

```text
delivery_plan
  -> delivery_action_request(COMMIT)
  -> human delivery_approval
  -> delivery_receipt(COMMIT)
  -> exact-tip verification/CI receipt
  -> delivery_action_request(PUSH)
  -> separate human delivery_approval
  -> delivery_receipt(PUSH)
  -> hosted push readback
  -> delivery_action_request(PR_CREATE | PR_UPDATE)
  -> separate human delivery_approval
  -> delivery_receipt(PR_CREATE | PR_UPDATE)
```

`LOCAL COMMIT`, `PUSH`, `PR CREATION/UPDATE`, `REVIEW`, and `PROMOTION` remain
distinct. Artifacts are evidence, never authority. Only an explicit human
approval bound to the exact current action and an explicit operator execution
invocation can authorize an effect.

## Implementation categories

### 1. Canonical delivery artifacts and validators

Extend the existing artifact architecture with one typed family using an
action discriminator, rather than parallel commit/push/PR vocabularies:

- `builder_ii.delivery_plan`: static pre-commit intent, exact target identity,
  branch/base, pre-commit HEAD, expected path/diff/content/tree digests,
  commit message, remote, PR metadata, verification profile, denied scope,
  and `artifact_is_authority: false`.
- `builder_ii.delivery_action_request`: one action enum (`commit`, `push`,
  `pr_create`, `pr_update`) with the exact predecessor digests and live state
  bindings required for that effect.
- `builder_ii.delivery_approval`: explicit human approval for exactly one
  action request, with expiry and digest binding; it cannot be produced by a
  model, MCP, Goose, or STRATUM.
- `builder_ii.delivery_receipt`: action-discriminated executed result with
  exact inputs, output SHA/tree/remote/PR custody, bounded output, failure
  state, and actionable recovery guidance.

Use the existing canonical JSON/digest conventions, artifact-chain validator,
event ledger, state/artifact indexes, receipt reconstruction, and governance
standard. Every validator must independently recompute material digests and
reject missing, stale, substituted, out-of-namespace, symlinked, or
event-mismatched evidence. No `delivery_history.json` or second state store.

### 2. One canonical delivery executor

Add exactly one `DeliveryService`/`DeliveryExecutor` owner with narrow methods
for commit, push, and PR create/update. It consumes only validated action
requests and approvals. CLI, MCP, Goose, and STRATUM may project or invoke this
owner only through admitted interfaces; none may reimplement Git/GitHub logic.

Commit requirements:

- accept an exact planned dirty worktree when the delta is exactly planned;
- reject unexpected paths, changed diff/tree, wrong branch, direct `main`,
  wrong remote, changed HEAD, or staged-tree mismatch;
- stage only the planned scope and independently compare the staged tree
  before commit;
- use fixed Git argv with `shell=False`, no generic shell, no arbitrary argv,
  no `builder-hitl run-command`, and no amend on the happy path;
- record pre-state, index/worktree state, commit-message binding, resulting
  commit SHA/tree/parent/branch, and recoverable failure guidance.

Push requirements:

- require a successful exact-tip verification/CI receipt before an action
  request can be approved;
- bind exact local commit/tree, verification digest, stable HEAD, branch,
  remote identity, and expected remote-branch state;
- reject drift, remote movement, wrong SHA/remote, `main`, force-push, and
  force-with-lease; use fixed Git argv with `shell=False`;
- read back the remote branch and record exact hosted SHA and bounded output.

PR requirements:

- require a validated push receipt and exact hosted head readback;
- bind repository, head/base branches and revisions, operation, PR metadata,
  and existing PR identity for updates;
- use fixed `gh` argv with `shell=False`, without login, credential
  persistence, arbitrary flags, or secret recording;
- CREATE refuses when an applicable PR exists; UPDATE refuses when the bound
  PR is absent or custody changed unexpectedly;
- read back and record PR number, URL, state, head/base SHA, metadata, and
  failure/recovery guidance;
- do not add merge, review, promotion, tag, publication, or release authority.

### 3. Operator command and projections

Add the promised `builder deliver [RUN]` guided surface. It loads the exact run
and canonical evidence, displays the current stage, materializes or locates
the next action request, consumes only the current explicit approval, executes
only that effect, and stops at the next boundary. The convenience command must
preserve three separate decisions: commit, push, and PR.

Update STRATUM/run projection and command-authority documentation to show
delivery plan/action/approval/receipt kinds, current stage, commit and
verification state, push state, PR state, evidence health, and next admissible
human action. STRATUM remains read-only and its existing five-command authority
surface is not widened for convenience.

Update the MCP delivery truth to remove only the stale “Set 6 is absent” claim.
MCP may consume a pre-existing validated action/approval only if that is
strictly required by the canonical command path; it must never solicit or mint
approval, choose repository/remote/branch/metadata, or become a second
executor. The normal CLI path is the preferred closure dependency.

### 4. Recovery and denied scope

Before push, corrections require a newly planned and approved corrective
commit; any retained amend path requires a new exact request and approval.
After push, recovery is a corrective commit or separately approved revert.
Published history is never silently reset or rewritten. Failed effects produce
failure receipts only, never manufactured success evidence.

The following remain explicitly denied or unreachable:

```text
PLAN_SET_7, Linux release parity, wheels/packages, tags, publication, release,
PR merge automation, force-push, force-with-lease, history rewrite,
generic shell, arbitrary Git/GH argv, auto-login, credential persistence,
model execution, Deep Agents/Goose delivery choice, STRATUM approval authority,
CORE-specific global delivery architecture, and DeepHaven work.
```

## Human and authority boundaries

The plan-digest approval authorizes implementation of this frozen Set-6 design
on the exact isolated base. It does not authorize this system to self-govern
its own development PR; the repository bootstrap rule remains in force.

Within the product behavior, commit, push, and PR each require a separate
human approval artifact bound to the exact action request. Approval does not
authorize a later action. Review, merge, promotion, publication, and release
remain external boundaries. No model output, MCP response, Goose handoff,
STRATUM projection, or artifact alone is approval.

## Deterministic qualification

Before any live GitHub mutation, qualify with temporary repositories, local and
bare remotes, and mocked `gh` responses. The focused suite must cover:

- canonical digest sensitivity, stale/substituted plan rejection, wrong-action
  and expired-approval rejection, and `artifact_is_authority == false`;
- exact planned dirty commit success, unexpected-path/diff/tree/branch/HEAD/
  remote/direct-main/staged-tree refusal, exact resulting SHA/tree/parent, and
  no partial success receipt;
- missing, stale, or drifted exact-tip verification blocking push;
- exact feature push success; remote movement, wrong remote/SHA, main,
  force/force-with-lease, and credential-persistence denial;
- mocked exact CREATE and UPDATE success, existing-PR CREATE refusal, missing
  or custody-changed UPDATE refusal, metadata/head/base substitution refusal,
  arbitrary `gh` flag unreachability, and exact hosted result binding;
- actionable recovery on every failure, no silent reset, no history rewrite,
  `shell=False`, no generic shell/run-command path, and no model/Goose/Deep
  Agents/MCP/STRATUM authority leakage.

Verification must include focused tests, artifact/authority/docs truth checks,
the deterministic end-to-end qualification, and finally `bash scripts/ci.sh`
on the exact settled implementation tip. The local CI receipt is the final
verification evidence; GitHub-hosted workflows are neither created nor used.

## Live rehearsal boundary

After deterministic qualification passes, prepare one separately approved,
bounded rehearsal against an operator-designated disposable repository/branch.
It must exercise plan, human commit approval, local commit, exact-tip
verification, human push approval, real push, hosted readback, human PR
approval, real PR create/update, and validated receipts. No merge is needed.
The Set-6 implementation must not self-authorize its own development delivery
PR; normal operator-controlled review/delivery remains the bootstrap path.

## Exit contract

Set 6 is complete only when the delivery plan, commit receipt, exact-tip gate,
separate push receipt/readback, separate PR receipt/readback, refusal controls,
recovery guidance, artifact chain, truthful STRATUM projection, command
authority, docs truth, deterministic qualification, bounded live rehearsal,
final local CI, and clean worktree are all evidenced. Capability promotion is
not implied. Plan Set 7 must not begin.

## Exact denied claims at plan time

```text
DELIVERY_PLAN             = PLANNED_ONLY
COMMIT/PUSH/PR_MUTATION   = NOT_AUTHORIZED_PENDING_PLAN_APPROVAL
CAPABILITY_PROMOTION      = NOT_AUTHORIZED
LIVE_GITHUB_REHEARSAL     = NOT_AUTHORIZED
SELF_HOSTING              = NOT_AUTHORIZED
```
