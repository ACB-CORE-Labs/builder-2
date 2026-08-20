# Open-Source V1 Plan Set 3B3 — HITL-Gated Verification Execution via MCP

Status: `PLANNED_ONLY_AWAITING_HITL_APPROVAL`

Plan base: `d53861567fb86b5e2f2672544481bb03353b5bfd`

## Purpose

Expose Builder-II's existing HITL-approved verification runner through the governed MCP
service and receipt spine established by Plan Sets 3B1–3B2. MCP transports a pre-existing
approval; it does not create, reinterpret, broaden, or substitute for verification authority.

The admitted surface is intentionally singular:

```text
verification_execute(plan_path, approval_path)
```

The result is a projection of the canonical verification execution receipt and evidence. It is
not an approval, capability grant, command envelope, or new authority object.

## Current-code findings

The implementation must extend the existing shape rather than create a parallel lane:

- `builder_ii.lifecycle.candidate.verification_execution_plan` owns the passive, digest-bound
  plan contract. The 3B2 MCP `verification_plan` service must remain passive and unchanged in
  authority.
- `builder_ii.lifecycle.candidate.verification_execution_approval` owns approval schema and
  exact plan/profile/step binding. `builder-verify approve-plan` remains the human-controlled
  approval producer; MCP must not expose approval creation.
- `builder_ii.lifecycle.candidate.verification_execution_runner.run_approved_verification`
  already revalidates plan and approval, enforces command authority, selects fixed command
  profiles, independently captures Git state, checks the approved HEAD before execution,
  enforces clean-state requirements for target-code profiles, runs with `shell=False`, and
  writes the canonical receipt and postflight record.
- `builder_ii.adapters.mcp.governed_services` already provides controlled artifact-root path
  resolution, pre-write event-ledger replay, typed denied/failed outcomes, service receipts,
  and event records. The server is transport only.
- Approval `expires_at` is currently schema-checked only as a non-empty string; the canonical
  execution path does not yet enforce expiration.
- The verification execution ledger explicitly refuses to replay execution while reconstructing
  evidence, but there is no current single-use approval-consumption check preventing a second
  live invocation with the same approval. Replay resistance therefore must be added to the
  canonical execution authority path and shared by direct-service and MCP callers—not inferred
  from MCP session history alone.

## Governing invariants

1. `verification_plan` remains `planned_only`, approval-required, non-authoritative, and unable
   to observe Git state or start execution.
2. MCP accepts only already-existing plan and approval artifacts beneath the server-controlled
   Builder-II artifact root.
3. Canonical plan and approval validators remain the sole semantic validators.
4. The approval binds the exact plan digest, target, artifact root, verification profile,
   command profiles, steps, actor/reason, expiry, and execution-risk acknowledgment required by
   the existing contract.
5. Expiration and single-use consumption are enforced before any verification subprocess.
6. `run_approved_verification` remains the sole executor and independently observes execution-
   time Git/repository state.
7. Only code-defined structured profiles in `SUPPORTED_COMMAND_PROFILES` are executable; no MCP
   argument may supply argv, shell text, environment overrides, timeouts, ignore globs, or paths
   outside the approved artifacts.
8. Direct-service and MCP transport calls reach the same service function and produce
   semantically equivalent runner evidence.
9. A corrupt MCP event chain or corrupt verification-consumption ledger fails closed before
   execution and before misleading success evidence is appended.
10. Plan Sets 3B1 and 3B2 retain their existing authority and behavior.

## Implementation plan

### 1. Canonical approval-time and consumption enforcement

Files:

- `builder_ii/lifecycle/candidate/verification_execution_approval.py`
- `builder_ii/lifecycle/candidate/verification_execution_runner.py`
- `builder_ii/governance/ledger/verification_execution_ledger.py` or a narrowly factored
  canonical approval-consumption helper colocated with the existing verification ledger
- Focused verification approval/runner/ledger tests

Changes:

- Parse `generated_at` and `expires_at` as timezone-aware timestamps in the canonical approval
  contract, reject malformed or non-forward intervals, and add an execution-time expiration
  check that accepts an injected/current UTC observation for deterministic tests.
- Introduce a digest-bound, append-only consumption record keyed by approval ID/digest and exact
  plan digest. Validate the existing chain before execution, reserve/record consumption before
  spawning, and refuse a reused or tampered approval.
- Define crash semantics explicitly: after a valid approval is claimed for execution, it remains
  consumed even if the runner times out, fails, or detects postflight mutation. Retrying requires
  a fresh human approval artifact. This prevents ambiguous double execution.
- Keep these checks inside the canonical runner authority boundary so CLI/direct-service/MCP
  execution cannot disagree.
- Preserve ordinary blocked-before-execution receipts for validation, scope, expiry, drift, and
  authorization failures when a safe configured output location is available. Never mark a
  denied attempt as executed.

### 2. Governed execution service

Files:

- `builder_ii/adapters/mcp/governed_services.py`
- Focused direct-service tests

Changes:

- Admit `verification_execute` in the governed service inventory.
- Resolve `plan_path` and `approval_path` with the existing controlled-path mechanism beneath
  the server-controlled Builder-II artifact root; refuse traversal, symlinks that escape the
  root, missing files, directories, and non-JSON inputs.
- Replay and validate both the MCP event chain and the canonical approval-consumption chain
  before execution.
- Load the exact artifacts, call canonical validators, and require target identity to match the
  server's configured `target_root` and `target_name` before invoking the runner.
- Derive the requested structured profile only from the exact plan/approval intersection. If the
  current contract permits multiple approved executable steps, either execute them through an
  existing canonical multi-step entrypoint or fail closed until the request can name one
  already-approved profile without broadening authority. Do not invent an implicit ordering or
  new batch executor in MCP.
- Derive receipt/postflight output paths under the approved plan's artifact root; accept no
  caller-supplied output, argv, command, environment, timeout, or scope override.
- Invoke `run_approved_verification` directly and return a bounded projection containing status,
  canonical receipt/postflight references and digests, executed/skipped profile evidence, and
  independently observed Git state.
- Persist the ordinary MCP service receipt and event record around that canonical result. A
  blocked runner outcome must remain blocked/denied rather than being projected as success.

### 3. MCP inventory and transport

Files:

- `builder_ii/adapters/mcp/governed_call.py`
- `builder_ii/adapters/mcp/server.py` only if transport classification needs a narrow adjustment
- `builder_ii/core/mcp_policy.py` only if the existing policy schema cannot truthfully represent
  this approved bounded-execution service
- MCP CLI/help documentation where the existing inventory is documented

Changes:

- Advertise only `verification_execute(plan_path, approval_path)` with a closed JSON schema
  (`additionalProperties: false`).
- Route it through `run_service`, never through the generic gated patch/shell path and never
  through a new subprocess implementation.
- Update service policy/receipt governance fields so they truthfully describe bounded,
  approval-gated verification subprocess execution while keeping arbitrary shell, network,
  credentials, source writes, Git mutation, patching, models, Goose, Deep Agents, and delivery
  disabled. Do not reuse a receipt that falsely says all subprocess execution is disabled.
- Preserve typed denied/failed transport outcomes and fail closed if service evidence cannot be
  appended because the MCP ledger is corrupt.

### 4. Adversarial qualification and authority-regression pins

Primary test file:

- `tests/test_mcp_plan_set_3b3_verification_execution.py`

Supporting focused tests may be added beside existing approval, runner, ledger, policy, server,
and CLI tests when the invariant belongs below MCP.

Required positive proof:

- Create a plan through the existing passive path.
- Create approval independently through the existing human-controlled approval contract/surface
  (never through MCP).
- Execute through direct service and through MCP in isolated equivalent fixtures.
- Prove both paths invoke the canonical runner and emit semantically equivalent execution
  receipt/postflight evidence plus valid MCP service receipts and event chains.
- Prove the runner's observed HEAD/clean state—not 3B2 caller metadata alone—controls admission.

Required lesions, all before subprocess execution where applicable:

- Missing/malformed plan or approval.
- Wrong plan digest, target repository/profile, verification profile, or approved step/profile.
- Malformed or expired approval.
- Reused approval, tampered consumption record, or corrupt consumption chain.
- Execution-time HEAD drift or dirty target state.
- Escaped artifact paths, absolute paths outside the root, traversal, and escaping symlinks.
- Unsupported or unauthorized verification lane.
- Extra arguments and attempted argv, shell, environment, timeout, output-path, mutation, or Git
  authority smuggling.
- Corrupt MCP ledger before execution and corruption of generated service receipt/event refs.
- Runner receipt/postflight corruption and non-success runner outcomes.
- Tool inventory contains no approval-minting or combined approve-and-run tool.
- Existing 3B1 repository/read/preparation services and 3B2 status/passive-plan services retain
  their pinned behavior and authority exclusions.

Tests must patch/spy on the canonical runner or subprocess boundary in denial cases to prove no
execution occurred, not merely assert an error string.

### 5. Truth, security, and operator documentation

Files selected after tracing the current pins, expected to include:

- `SECURITY.md`
- MCP/operator documentation and command-surface inventory
- `docs/CAPABILITY_PROMOTION.md` and platform truth-matrix sources only if current evidence earns
  the corresponding narrow state change
- `SPRINT_LOG.md` only for an evidence-backed completion entry

Changes:

- Document that the bounded verification runner is not a sandbox and target-code profiles run
  trusted repository code with operator privileges under the existing risk acknowledgment.
- State that approval creation remains outside MCP and that approval artifacts are exact,
  expiring, single-use inputs to the canonical runner—not general authority tokens.
- Preserve explicit non-authorizations for arbitrary shell, mutation, delivery, models, Goose,
  and Deep Agents.
- Do not flip a promotion claim from tests or documentation alone; bind any change to the final
  canonical evidence bundle and local gate receipt.

## Verification commands

Run focused gates incrementally, then the mandatory local gate battery on the exact candidate
tip before any push or PR:

```bash
uv run pytest -q \
  tests/test_verification_execution_approval.py \
  tests/test_verification_execution_approval_authority.py \
  tests/test_verification_execution_runner.py \
  tests/test_verification_execution_ledger.py \
  tests/test_mcp_policy.py \
  tests/test_mcp_server.py \
  tests/test_mcp_plan_set_3b1_hardening.py \
  tests/test_mcp_plan_set_3b2_status_verification.py \
  tests/test_mcp_plan_set_3b3_verification_execution.py
uv run ruff check builder_ii tests
uv run builder-platform audit-docs
uv run builder-platform matrix
bash scripts/ci.sh
```

The final qualification must record the exact commit SHA, stable pre/post gate HEAD, clean
worktree, focused and full-suite counts, blocking-gate results, and canonical evidence digest.

## Rollback

Before merge, rollback is deletion/reversion of the 3B3-only inventory, service, canonical
consumption enforcement, tests, and documentation on the feature branch. After merge, use a
normal revert PR. Never weaken approval validation, erase consumption evidence, or rewrite
historical receipts to simulate rollback.

## Explicit non-authorizations

This plan does not authorize implementation, verification execution, approval creation, source
mutation outside the eventual approved change set, Git delivery, or promotion. It grants no MCP
approval minting, arbitrary shell, source write, patch, Git mutation, model, Goose, Deep Agents,
network, credential, or delivery authority.

Implementation must halt until a human supplies an approval artifact or equally explicit
repository-recognized authorization bound to this exact plan and scope.
