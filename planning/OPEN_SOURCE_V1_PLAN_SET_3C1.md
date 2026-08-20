# Open-Source V1 Plan Set 3C1 — Passive Exact Patch Proposal via MCP

Status: `PLANNED_ONLY_AWAITING_HITL_APPROVAL`

Plan base: `fc0fa3f7edfbe26a267527516a274f0de2ea4fe6`

Plan-base tree: `f736c557aee2ca94d47c9f74fcbcc677affd4c72`

## Purpose

Expose one passive MCP service that binds exact patch material to Builder-II's existing HITL
patch-proposal artifact and then stops for a separately created human approval. The service
strengthens `artifact -> validate -> approve -> execute -> receipt`: MCP may create and report
the proposal artifact, but the artifact is not authority, the reported decision is not approval,
and Plan Set 3C1 has no patch, rollback, shell, Git, or target-repository execution path.

The only newly admitted MCP capability is equivalent to:

```text
patch_proposal(
    unified_diff,
    description,
    reason,
    target_head_sha,
    verification_receipt_path
)
    ->
{
    proposal_ref,
    proposal_digest,
    patch_digest,
    target,
    exact_scope,
    decision: "HUMAN_APPROVAL_REQUIRED"
}
```

The ordinary MCP call remains `succeeded` when the passive proposal and its evidence are
validly persisted. `HUMAN_APPROVAL_REQUIRED` is a domain result/state projection, not an MCP
receipt status, an approval artifact, a capability grant, or a parallel state machine.

## Current-code findings at the exact base

The implementation must extend the existing Builder-II artifact shape, not add a second patch
proposal vocabulary or executor:

- `builder_ii.governance.hitl.hitl_patch_proposal.create_hitl_patch_proposal` constructs the
  canonical proposal but currently accepts both `patch_digest` and `unified_diff`. It therefore
  does not itself enforce that the digest binds the supplied diff.
- `builder_ii.cli.hitl_patch_cli` currently provides the stronger proposal-binding semantics:
  `builder-hitl propose-patch` reads the diff as UTF-8, computes SHA-256 from those exact UTF-8
  bytes, hashes the exact verification-receipt bytes, and only then invokes the constructor.
  Those semantics must be factored into one canonical passive proposal function shared by CLI
  and MCP. MCP must not duplicate them or invoke the weaker constructor directly.
- `builder_ii.adapters.mcp.governed_services` owns the deny-by-default service inventory,
  controlled artifact-root resolution, pre-write MCP-ledger replay, chosen session artifact
  locations, service receipts, and event records. The current admitted service inventory ends
  at `verification_execute`.
- `builder_ii.adapters.mcp.governed_call.GATED_TOOL_SPECS` nevertheless still advertises legacy
  MCP tools named `propose_patch` and `run_shell`. In `builder_ii.adapters.mcp.server`, the legacy
  `propose_patch` branch calls `run_gated_patch_apply`, which can reach the canonical mutating
  apply lane when its enablement and approval conditions are met. `run_shell` is refused but is
  still advertised. Adding the passive proposal service without removing these MCP inventory
  and dispatch paths would violate the 3C1 inventory lesion and could leave a second executor.
- `builder_ii.adapters.mcp.governed_apply` imports and calls `apply_hitl_patch`. It is historical
  MCP apply machinery and is outside the admitted 3C1 graph; no 3C1 service, transport branch,
  import, or tool inventory may reach it.
- The existing operator CLI lane remains distinct: `builder-hitl approve-patch`,
  `builder-hitl apply-patch`, and rollback machinery are not removed from the operator surface,
  but none is callable through MCP in 3C1.

## Governing invariants

1. MCP receives the exact patch material; canonical Builder-II code computes
   `sha256(unified_diff.encode("utf-8"))`. The caller cannot supply, select, or override the
   authoritative patch digest.
2. The proposal target name and repository come exclusively from the configured MCP server
   `target_name` and resolved `target_root`. `target_repo` is not an MCP argument.
3. The exact bytes of the verification receipt are SHA-256-bound after the path is resolved
   beneath the existing server-controlled Builder-II artifact root. Traversal, an external
   absolute path, a directory, or a symlink is refused.
4. Builder-II chooses the proposal path beneath the configured session/artifact root. MCP
   accepts no output path.
5. `exact_scope` is a deterministic projection derived from the canonical bound proposal and
   parsed diff. It is evidence describing the patch's exact declared reach, not a new authority
   object, caller assertion, or independently editable artifact.
6. The passive proposal is validated after construction and after persistence. Its reference
   and digest bind the exact stored artifact bytes/payload according to the canonical artifact
   contract before MCP advertises success.
7. A successful proposal call writes Builder-II artifact evidence only: proposal, policy,
   service receipt, and event record beneath the controlled Builder-II artifact/session root.
   It performs zero writes beneath the target repository.
8. The MCP service receipt retains `status: succeeded`; its governance continues to declare
   target-repository writes, shell, network, credentials, models, and bounded subprocess
   execution disabled for `patch_proposal`.
9. No 3C1 import/call graph reaches approval creation, patch/rollback execution, subprocess,
   generic filesystem writes, Git mutation, or the legacy governed MCP apply adapter.
10. The 3C1 MCP inventory contains the one passive `patch_proposal` capability and contains no
    `approve_patch`, `apply_patch`, `rollback`, combined propose-and-approve/apply tool, generic
    write tool, or shell/command tool. The legacy gated `propose_patch` apply alias and
    advertised `run_shell` tool are removed from MCP discovery and dispatch.
11. The operator CLI approval/apply/rollback lane remains separately human-controlled and
    unchanged in authority. The existence or success of a 3C1 proposal never makes apply
    callable through MCP.

## Exact implementation path scope

Implementation authority, if later granted for this exact plan, is limited to the following
paths and responsibilities. Any newly discovered need outside this list requires an amended,
re-digested plan and new HITL approval.

### 1. Canonical passive proposal binding

Files:

- `builder_ii/governance/hitl/hitl_patch_proposal.py`
- `builder_ii/cli/hitl_patch_cli.py`
- Focused canonical proposal and CLI tests, principally
  `tests/test_hitl_patch_proposal.py` and `tests/test_hitl_patch_cli.py`

Changes:

- Add one canonical passive proposal function that accepts patch material, description, reason,
  canonical target identity, target HEAD, and controlled verification-receipt bytes/path.
- Inside that function, encode the supplied diff exactly once as UTF-8 and derive the patch
  digest. Digest the exact verification-receipt bytes. Construct and validate the existing
  `builder_ii.hitl_patch_proposal`; do not create a second artifact kind.
- Make both `builder-hitl propose-patch` and MCP delegate to this function. Remove digest
  computation from the CLI adapter once shared behavior exists. Retain the lower-level
  constructor only where historical/internal callers require it, and prevent the new MCP path
  from calling it directly.
- Define and enforce a conservative UTF-8 byte ceiling for `unified_diff`, consistent with the
  MCP policy input ceiling and Apple Silicon resource constraints. Reject oversize input before
  artifact writes.
- Derive `exact_scope` from the parsed unified diff using existing canonical parsing if one is
  already present. If no safe parser exists, the implementation must use a narrowly factored,
  deterministic parser that rejects malformed diff structure and forbidden path forms; it must
  not infer broader semantic authority than the bound path/header/hunk evidence supports.

### 2. Passive governed MCP service and evidence

Files:

- `builder_ii/adapters/mcp/governed_services.py`
- Focused direct-service tests

Changes:

- Admit exactly one new service named `patch_proposal`.
- Require exactly the five arguments in the public signature and reject every extra property.
- Take target identity only from `run_service`'s trusted `target_root` / `target_name` inputs.
- Resolve `verification_receipt_path` with `_controlled_path` (or its canonical successor) and
  require an existing non-symlink regular artifact file beneath `builder_root`. Read and digest
  its exact bytes; do not accept arbitrary filesystem reads.
- Replay the MCP event ledger before the proposal write. Choose a collision-safe output
  directory beneath `builder_root/sessions/<session_id>/mcp/patch-proposal/`; accept no output
  location from the caller.
- Delegate once to the shared canonical passive proposal function, validate the returned
  artifact, persist it through the canonical writer, reload/revalidate the stored artifact, and
  return only the bounded result projection specified above.
- Derive `proposal_ref`, `proposal_digest`, `patch_digest`, `target`, and `exact_scope` from the
  stored canonical proposal. Hard-code/project `decision: HUMAN_APPROVAL_REQUIRED` only after
  all proposal and persistence checks succeed.
- Use the existing MCP service receipt/event mechanism with ordinary `succeeded`, `denied`, and
  `failed` outcomes. Do not add `approval_required` to the MCP receipt status vocabulary.
- If the proposal artifact write or later evidence write fails, do not return or persist a
  result that advertises the proposal as valid or approval-ready. Any orphaned partial artifact
  is failed evidence, not a successful proposal, and qualification must pin its handling.

### 3. Inventory and transport lesion

Files:

- `builder_ii/adapters/mcp/governed_call.py`
- `builder_ii/adapters/mcp/server.py`
- `builder_ii/adapters/mcp/governed_apply.py` only to retire/remove it if repository-wide import
  tracing proves it has no non-legacy consumer; otherwise leave the module intact but make it
  unreachable from MCP and document the retained operator/internal compatibility reason
- MCP CLI/help and inventory documentation selected by exact call-site/doc-pin tracing
- Focused server, inventory, policy, and authority-regression tests

Changes:

- Add a closed JSON schema for `patch_proposal` with `additionalProperties: false`, required
  exact arguments, UTF-8/size constraints represented truthfully where the schema supports it,
  and no authority-shaped inputs.
- Remove legacy gated `propose_patch` and `run_shell` from MCP discovery. Remove the server's
  `propose_patch -> run_gated_patch_apply` branch and any MCP dispatch route to the legacy
  governed apply adapter. Unknown calls using the retired names fail inventory admission.
- Route `patch_proposal` only through `run_service`; the server remains transport-only.
- Preserve the ordinary operator CLI patch lane. Do not rename a mutating apply tool into the
  passive service or leave both behaviors under confusing aliases.
- Update policy/receipt validation only as narrowly required to represent passive artifact
  evidence writes while keeping all target mutation and execution fields disabled.

### 4. Truth, security, and operator documentation

Files selected after tracing current generated and hand-authored pins, expected to include:

- `SECURITY.md`
- MCP/operator command-surface and tool-inventory documentation
- `docs/HITL_PATCH_PROPOSAL.md`
- `docs/COMMAND_AUTHORITY.md` and its source/generator if current generated truth requires it
- `docs/CAPABILITY_PROMOTION.md` and platform truth-matrix sources only if executable evidence
  earns a narrowly stated state change
- `SPRINT_LOG.md` only for an evidence-backed completion entry

Changes:

- Document proposal -> separate human approval -> explicit operator apply, with MCP stopping at
  `HUMAN_APPROVAL_REQUIRED` in 3C1.
- Remove stale claims that MCP advertises or can dispatch a patch apply or generic shell tool.
- State that `exact_scope` and proposal artifacts are evidence, not authority.
- Preserve explicit non-authorizations for autonomous/unattended apply, rollback, shell,
  arbitrary write, Git mutation, delivery, model execution, Goose runtime activation, and Deep
  Agents runtime activation.
- Do not flip a promotion or truth-matrix claim from documentation or green unit tests alone.

## Rejected argument and authority surface

The service accepts no caller field named or semantically equivalent to:

- `patch_digest`, `proposal_digest`, `proposal_ref`, `exact_scope`, or `decision`;
- `target_repo`, `target_root`, `target_name`, or any target override;
- `output`, `output_path`, `output_dir`, artifact root, session root, or receipt output path;
- arbitrary read path, diff path, patch path, approval path, rollback path, or apply path;
- `approval`, `approved`, approver identity, approval TTL, approval digest, or confirmation;
- `apply`, `rollback`, `execute`, `mutate`, generic write, Git, commit, push, or delivery input;
- `argv`, `cmd`, `command`, `shell`, environment, working-directory override, timeout, network,
  credentials, model, Goose, or Deep Agents input.

The implementation must reject extra properties before canonical proposal construction or any
artifact write. Similar spelling or nested smuggling does not become admissible merely because
the JSON schema did not name it.

## Adversarial qualification matrix

The primary qualification should live in
`tests/test_mcp_plan_set_3c1_patch_proposal.py`, with lower-level invariants tested beside their
canonical owners. Tests must spy on dangerous boundaries directly; returned strings alone are
not proof.

| Obligation | Positive proof | Lesion / refusal proof | Dangerous-boundary assertion |
|---|---|---|---|
| Digest integrity | Exact UTF-8 diff bytes produce the stored proposal digest; changing one byte changes `patch_digest` | Supplying `patch_digest`, alternate encoding material, malformed diff, or digest override is denied | Shared canonical function called once; MCP never calls the raw constructor with a caller digest |
| Target binding | Proposal target equals configured `target_root` / `target_name` | `target_repo`, target alias/override, or mismatched configured identity is denied | No caller target reaches proposal construction |
| Receipt binding | Exact controlled receipt bytes produce `verification_receipt_file_sha256` | Missing/corrupt receipt, traversal, outside absolute path, directory, symlink escape, or read failure is denied | No arbitrary `Path.read_*` target outside controlled resolver |
| Artifact placement | Proposal/ref/receipts are under the server session artifact root | Caller output/artifact/session paths and artifact-write failure cannot advertise approval readiness | Zero writes outside the controlled Builder-II evidence root |
| No approval mint | Success ends at `HUMAN_APPROVAL_REQUIRED` | Approval fields and propose-and-approve names are denied/unadvertised | Spies on `create_hitl_patch_approval` and approval CLI entrypoint record zero calls |
| No execution | Success and every denial leave the target unchanged | Apply, rollback, approval/apply paths, command/shell/argv/environment/timeout inputs are denied | Spies on `apply_hitl_patch`, `rollback_hitl_patch`, `run_gated_patch_apply`, `subprocess.run`, `subprocess.Popen`, and `os.system` record zero calls |
| No target mutation | Valid proposal and every denial preserve exact target state | Malformed input, corrupt evidence, oversized diff, ledger corruption, and artifact failures still preserve it | Pre/post byte manifest, Git HEAD/tree/index/status, symlink metadata, and worktree fingerprint are identical |
| No second executor | CLI and MCP produce semantically equivalent canonical proposal bindings | Monkeypatching the raw constructor or legacy apply adapter cannot create an alternate successful MCP path | MCP delegates only to the shared passive proposal function through `run_service` |
| Fail-closed evidence | Valid artifact, result, service receipt, policy ref, and event chain all revalidate | Corrupt MCP ledger, persisted proposal corruption, service-receipt/event corruption, or write failure never yields an approval-ready success | Result is emitted only after canonical persisted bytes and evidence checks pass |
| Inventory lesion | `tools/list` exposes `patch_proposal` with its closed schema | `approve_patch`, `apply_patch`, `rollback`, legacy gated `propose_patch`, combined tools, write tools, and `run_shell` are absent and denied on call | Transport has no branch/import reaching governed apply, approval, subprocess, or generic shell |

Additional required cases:

- Empty, non-string, non-UTF-8-representable/invalidly transported, malformed, and oversized diff.
- One-byte changes in diff content, newline form, and receipt bytes each change the appropriate
  bound digest without normalization.
- Malformed target HEAD, absent description/reason, extra/nested properties, and wrong argument
  type.
- Diff paths containing absolute paths, traversal, ambiguous rename/copy forms, binary/combined
  diff forms not explicitly supported by the canonical scope parser, or scope inconsistent with
  the proposal are refused rather than approximated.
- Corrupt prior MCP event chain before any proposal write.
- Proposal write succeeds but reload/validation fails; service receipt/event write fails; no
  response advertises `HUMAN_APPROVAL_REQUIRED` as a valid proposal outcome.
- Existing Plan Set 3B1 repository/read/preparation services and 3B2/3B3 verification services
  retain their pinned behavior. Their inventories gain no mutation, approval, or shell inputs.
- Existing operator `builder-hitl propose-patch` continues to bind exact diff and receipt bytes
  through the shared canonical function; `approve-patch`, `apply-patch`, and rollback remain
  out-of-band operator commands, not MCP tools.

## Verification commands for the later implementation

Run focused gates incrementally on a clean feature branch created from the exact plan base, then
the mandatory local gate battery on the exact candidate tip before any push or pull request:

```bash
uv run pytest -q \
  tests/test_hitl_patch_proposal.py \
  tests/test_hitl_patch_cli.py \
  tests/test_mcp_policy.py \
  tests/test_mcp_server.py \
  tests/test_mcp_plan_set_3b1_hardening.py \
  tests/test_mcp_plan_set_3b2_status_verification.py \
  tests/test_mcp_plan_set_3b3_verification_execution.py \
  tests/test_mcp_plan_set_3c1_patch_proposal.py
uv run ruff check builder_ii tests
uv run builder-platform audit-docs
uv run builder-platform matrix
bash scripts/ci.sh
```

The final evidence bundle must record exact commit and tree SHAs, stable pre/post gate HEAD,
clean implementation worktree, focused and full-suite counts, every blocking-gate outcome,
canonical evidence digests, the exact post-3C1 MCP tool inventory, and pre/post target identity
evidence from both success and denial qualification. Green tests do not self-certify promotion.

## Rollback strategy

Before merge, rollback is deletion/reversion of only the approved 3C1 service inventory,
canonical proposal factoring, MCP transport retirement, tests, and documentation on the feature
branch. After merge, use a normal revert pull request against the exact 3C1 merge; do not rewrite
history or alter historical proposal/service receipts.

Rollback must restore the pre-3C1 passive behavior without weakening proposal digest validation,
re-enabling an MCP apply/shell path, or presenting stale tool discovery. If shared CLI factoring
must be reverted, restore the CLI's original internal digest computation atomically so no caller
can supply an authoritative digest during rollback.

## Explicit denied boundaries

This plan does not authorize source implementation, approval creation, patch or rollback
execution, subprocess or shell execution, target-repository writes, arbitrary filesystem reads
or writes, Git mutation, branch/commit/push/PR/merge/tag/release, dependency changes, network or
credential access, models, Goose, Deep Agents, delivery, truth-matrix promotion, or capability
promotion.

Plan Set 3C1 authorizes no `apply-patch` capability through MCP. Plan Set 3C2 remains a separate
future approval unit that may only consume an existing separately created approval and exact
proposal through the existing canonical apply authority, postflight, and rollback evidence.
Nothing in this plan pre-approves, schedules, or partially implements 3C2.

## Final HITL stop

This artifact is passive planning evidence only. Implementation must halt until a human supplies
a repository-recognized HITL approval bound to this exact plan digest, exact base, explicit path
scope, denied boundaries, qualification obligations, and rollback strategy. The implementation
agent must re-inspect the then-current hosted `main`; any base drift or required scope expansion
invalidates direct execution of this plan and requires reconciliation before work begins.
