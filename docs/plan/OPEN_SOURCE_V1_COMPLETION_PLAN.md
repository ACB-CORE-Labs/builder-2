# Builder-II open-source v1 completion plan

Status: passive execution-plan artifact. Planned is not executed. This document
does not authorize implementation, verification, promotion, commit, push, pull
request creation, publication, or deletion. Execution must halt until a human
approval artifact binds the exact digest of this file and names the approved plan
set and path scope.

Date: 2026-08-13

Canonical repository: `https://github.com/ACB-CORE-Labs/builder-2`

Observed planning baseline:

- repository root: `/Users/kaizenpro/Projects/acbcore-labs/builder-2`
- branch: `main`
- `HEAD`: `2dabf2d25b599c85b5a047fb843a73c629679418`
- `origin/main`: `2dabf2d25b599c85b5a047fb843a73c629679418`
- configured `origin`: `https://github.com/ACB-CORE-Labs/builder-2.git`
- pre-existing untracked review input: `builder-II_lead_engineer_brief.md`

The untracked lead-engineer brief is input evidence, not implementation authority,
and must be preserved unless the operator explicitly approves its disposition.

## Governance boundary

Builder-II is a governed control plane. This plan preserves these distinctions:

- planned is not executed;
- executed is not verified;
- verified is not promoted;
- an artifact is not authority;
- model, Goose, Deep Agents, MCP, WRP, and STRATUM output is not approval.

The repeating platform grammar is:

> artifact -> validate -> approve -> execute -> receipt

Every plan set is a separate reviewable change set. Each set requires its own
digest-bound human approval after the preceding set is complete and reconciled.
No approval for one set authorizes a later set. Capability promotion remains a
separate, non-delegable decision after the eight promotion gates and executable
evidence are complete.

Until the first approval is supplied, the following remain disabled:

- source and documentation edits other than this passive plan artifact;
- deletion, movement, or rewriting of existing documentation;
- branch creation, commit, push, pull request, merge, tag, or release;
- model, Goose, Deep Agents, MCP, tool, or shell execution as a product runtime;
- target-repository mutation;
- truth-matrix or promotion-state changes;
- dependency changes and external installation;
- live GitHub mutation.

## Completion contract

Builder-II v1 is complete when an engineer can:

- install it on Apple Silicon with one documented command and complete a
  reproducible Linux installation and smoke test;
- run `builder init`, then use `builder stratum` or
  `builder start --task "..."`;
- complete one continuous governed session without copying routine commands
  between interfaces;
- use upstream Deep Agents for durable planning, bounded subagents, context
  offloading, interruption, persistence, and resume;
- use Goose as the conversational operator runtime while Builder-II remains the
  only authority and governed-tool source;
- route all model invocations through the model gateway and all external
  capabilities through the governed tool/MCP seam;
- review and approve an exact patch, apply it, run verification, and receive
  digest-bound evidence;
- create a local commit and, after distinct human approvals, push and open a
  GitHub pull request;
- resume an interrupted or crashed run without manufacturing execution or
  verification claims;
- inspect who planned, approved, executed, verified, and promoted every material
  action; and
- receive a specific refusal with zero side effects when policy, evidence, budget,
  environment, or authority is insufficient.

Completion does not require every capability-matrix row to become operationally
verified. Deliberately passive, forbidden, deferred, or human-only capabilities
must remain honestly unpromoted.

## Public architecture

### One canonical governed run

Extend the existing WRP run manifests, obligation envelopes, workflow ledger,
model receipts, HITL chain, patch and rollback artifacts, verification evidence,
and state index into one lifecycle. Do not introduce a parallel artifact
vocabulary.

The canonical run binds:

- session, target repository, base revision, task, profile, policy, and
  configuration digests;
- WRP decomposition, role assignments, model routes, budgets, and concurrency;
- runtime adapter and version;
- declared tool inventory and approval requirements;
- parent and child obligations plus context projections;
- model, tool, HITL, patch, rollback, verification, Git, delivery, and close
  receipts; and
- ordered hash-linked lifecycle events that support interruption and resume.

Use one runtime-adapter interface for `prepare`, `start`, `resume`, `interrupt`,
`cancel`, `inspect`, and `close`. An adapter implements lifecycle behavior; it does
not gain authority.

### Subsystem ownership

- **Builder-II:** authority, artifacts, policy, budgets, tool admission, HITL,
  verification, rollback, ledgers, delivery receipts, and promotion.
- **WRP:** workload decomposition, role and model selection, budgets, and
  orchestration policy. WRP plans; it does not independently execute.
- **Deep Agents:** durable planning and bounded subagent execution through the
  official `create_deep_agent` API and upstream model, tool, middleware, subagent,
  persistence, and backend extension points.
- **Goose:** conversational operator runtime and session shell. Goose capabilities
  remain beneath Builder-II governance.
- **MCP:** deny-by-default gateway for Goose and Deep Agents tools. Internal callers
  may call the same governed service directly but must receive identical policy
  decisions and receipts.
- **STRATUM:** projection and cockpit for the canonical run. It may invoke admitted
  fixed argument vectors but may not mint approval, bypass command authority, or
  become another orchestrator.

### Stable normal-user command surface

- `builder init`
- `builder start --task ...`
- `builder resume [RUN]`
- `builder status [RUN]`
- `builder verify [RUN]`
- `builder deliver [RUN]`
- `builder doctor`
- `builder stratum`

Specialist commands such as `builder-wrp`, `builder-deepagents`, `builder-hitl`, and
`builder-platform` remain inspectable expert and administrative surfaces. Replace
the legacy `builder start` behavior with the canonical governed launch. If a
compatibility surface is necessary, retain it for no more than one release under an
explicit legacy name with a deprecation warning.

## Plan Set 0: reset repository and platform truth

Governance distinction strengthened: documented policy and promotion prose must
not contradict configured repository identity or executable evidence.

### 0.1 Canonical forge and delivery policy

1. Declare `github.com/ACB-CORE-Labs/builder-2` the sole canonical upstream.
2. Authorize `gh` for repository and pull-request operations and remove Forgejo and
   `tea` requirements from current policy.
3. Preserve `bash scripts/ci.sh` as the authoritative pre-push verification gate.
4. Add a repository-identity preflight that verifies the configured canonical
   remote before push or pull-request creation while allowing downstream forks to
   declare their own canonical repository.

### 0.2 Matrix and current-state truth

1. Reconcile the typed completion matrix, command-authority registry, roadmap,
   known limitations, operator docs, and lead-engineer review input.
2. Split the current Deep Agents claim into structural/protocol-fake evidence and
   native-runtime evidence.
3. Correct blockers that are stale because another verified lane already provides
   the missing evidence.
4. Classify every non-operationally-verified row as intentionally passive,
   implemented but missing evidence, or genuinely missing user value.
5. Generate overview and limitation prose from the typed matrix where practical.
6. Characterize the two skipped tests and either make them deterministic or pin
   their exact platform condition.

### 0.3 Documentation authority and cleanup

After approval, `docs/plan/OPEN_SOURCE_V1_COMPLETION_PLAN.md` becomes the sole
current implementation plan. The typed matrix and executable evidence remain the
release source of truth. Git history is the archive for obsolete plans; obsolete
documents are removed from the working tree so they cannot be mistaken for current
instructions.

The following still-normative material must move out of `docs/plan/` and be edited
into current architecture contracts, with every source, fixture, test, and index
reference updated atomically:

- `docs/plan/CORE_WORKBENCH_BOUNDARY.md` ->
  `docs/architecture/CORE_WORKBENCH_BOUNDARY.md`
- `docs/plan/MCP_POLICY_ARTIFACT_RFC.md` ->
  `docs/architecture/MCP_POLICY_CONTRACT.md`
- `docs/plan/MCP_TOOL_INVENTORY_RFC.md` ->
  `docs/architecture/MCP_TOOL_INVENTORY_CONTRACT.md`
- `docs/plan/ORCHESTRATION_OBLIGATIONS_RFC.md` ->
  `docs/architecture/ORCHESTRATION_OBLIGATIONS_CONTRACT.md`
- `docs/plan/SEMANTIC_STRUCTURAL_SEARCH.md` ->
  `docs/architecture/SEMANTIC_STRUCTURAL_SEARCH.md`
- `docs/plan/VERIFICATION_ISOLATION_RFC.md` ->
  `docs/architecture/VERIFICATION_ISOLATION.md`
- `docs/plan/WRP_MSDA_PREFLIGHT_POLICY.md` ->
  `docs/architecture/WRP_MSDA_PREFLIGHT_POLICY.md`

The following obsolete, shipped, superseded, or deferred plan documents must be
deleted after any still-valid constraints are reconciled into current contracts:

- `docs/plan/ARTIFACT_MEMORY_RFC.md`
- `docs/plan/B1_4A_VALIDATION_NOTE.md`
- `docs/plan/B8_B9_GOVERNED_EXECUTION_PLAN.md`
- `docs/plan/DEEPAGENTS_MODEL_INVOCATION_LANE.md`
- `docs/plan/DEEPAGENTS_WORK_ARTIFACTS_RFC.md`
- `docs/plan/GOOSE_DEEPAGENTS_MCP_SEAM.md`
- `docs/plan/GOOSE_G4_WRITE_SHELL_PROMOTION.md`
- `docs/plan/GOOSE_IN_LOOP_GOVERNED_RUNTIME.md`
- `docs/plan/MASTERPIECE_PLAN.md`
- `docs/plan/PASSIVE_EXECUTION_CANDIDATE_MANIFEST_RFC.md`
- `docs/plan/PASSIVE_HITL_PROMOTION_BRIDGE_RFC.md`
- `docs/plan/PERFORMANCE_AND_EFFICIENCY_AMENDMENT.md`
- `docs/plan/PR_203_DEEPAGENTS_FORGE_EXECUTION_PLAN.md`
- `docs/plan/RECONCILIATION_NOTE.md`
- `docs/plan/RUST_VALIDATION_SPIKE.md`
- `docs/plan/STRATUM_ORCHESTRATION_COCKPIT.md`
- `docs/plan/WRP_P2_REMAINDER_WIRES.md`
- `docs/plan/WRP_R_HEAD_RESEARCH_TRACK.md`
- `docs/plan/WRP_S1_BINDING_DESIGN.md`
- `docs/plan/WRP_VLLM_RESEARCH_PROFILE.md`

Remove or replace these current-looking superseded overview and strategy documents
after all inbound references are migrated:

- `docs/ROADMAP.md`
- `docs/BRIEF_ALPHA.md`
- `docs/BRIEF_BETA.md`
- `docs/BUILDER_II_COMPLETION_TRUTH_REPORT.md`
- `docs/MAXIMIZING_PROFICIENCY.md`
- `docs/PLATFORM_SNAPSHOT.md`
- `docs/WRP_ABSOLUTE_MASTERY_SYNTHESIS.md`
- `docs/WRP_MASTERY_AGENT_DISPATCH.md`
- `docs/WRP_MASTERY_GAP_MATRIX.md`
- `docs/WRP_MASTERY_PROGRESS.md`

Do not delete generated truth, evidence, promotion, operator, or audit documents
merely because they are old. In particular, `docs/KNOWN_LIMITATIONS.md`,
`docs/PLATFORM_COMPLETION_AUDIT.md`, `docs/CAPABILITY_PROMOTION.md`,
`docs/COMMAND_AUTHORITY.md`, `docs/audits/`, and `planning/evidence/` remain until
their typed generators and evidence consumers are deliberately migrated.

Plan Set 0 must update `docs/README.md`, root `README.md`, profile-pack sources,
fixtures, link checks, tests, and generated docs in the same change. No broken link,
stale path, or duplicate current plan may remain.

### Plan Set 0 exit gate

- GitHub policy, configured remote identity, command authority, and operator docs
  agree.
- The matrix and operator documentation agree on every promoted capability.
- Every non-operational row has an explicit truthful classification.
- No completed capability depends on a contradictory or stale blocker.
- `docs/plan/` contains only this current plan.
- Architecture contracts are outside the plan namespace.
- All migrated references validate and documentation truth enforcement passes.
- No capability is promoted from documentation alone.

## Plan Set 1: consolidate the governed-run spine

Governance distinction strengthened: all lifecycle claims derive from one ordered
evidence chain, and resume cannot manufacture missing work.

1. Make the existing run manifest, obligation envelope, workflow ledger, model
   receipts, HITL chain, verification evidence, and state index one lifecycle.
2. Introduce the runtime-adapter seam and migrate WRP's existing real model and
   subagent loop behind it.
3. Give every event a monotonic per-run sequence and previous-event digest;
   eliminate isolated sequence-zero close events.
4. Centralize cancellation, budget exhaustion, interruption, resume, and close.
5. Bind resume to the last verified checkpoint and artifact digests; refuse
   corrupted, foreign, expired, or policy-incompatible checkpoints.
6. Preserve current validators and sealed-artifact semantics. Refactor only what is
   necessary to expose the seam; do not undertake a general registry or schema
   rewrite.

Exit gate: a deterministic synthetic adapter can complete, interrupt, resume, fail,
cancel, and close a multi-step run while preserving one valid evidence chain and
emitting no claims for unexecuted steps.

## Plan Set 2: native Deep Agents integration

Governance distinction strengthened: upstream executor state remains subordinate to
Builder-II authority, obligations, budgets, and receipts.

1. Add a version-bounded `deepagents` optional dependency. Keep a lightweight
   governance-only base; include the extra in the recommended installation.
2. Replace custom expected exports with official `create_deep_agent` integration.
3. Inject only:
   - a model adapter backed by `ModelExecutionGateway`;
   - Builder-governed tools with no direct shell, filesystem mutation, Git mutation,
     or provider bypass;
   - WRP-generated subagent definitions with inherited obligation envelopes;
   - a digest-bound persistence/checkpoint backend; and
   - middleware for budgets, admission, receipts, interrupts, cancellation, and
     event recording.
4. Use upstream subagent and context facilities for bounded delegation and
   offloading while keeping repository writes behind Builder-II.
5. Retain `protocol_fake` only as a deterministic structural test double. Never use
   it as native-runtime evidence.
6. Default to two active workers on a 16GB M1, cap configurable concurrency at four,
   and prohibit simultaneous loading of multiple large local models.

Exit gate: a native scenario delegates at least two bounded obligations, performs
governed model and tool calls, pauses for HITL, resumes from persisted state, and
closes with a valid parent/child evidence chain.

## Plan Set 3: governed Goose operator runtime

Governance distinction strengthened: conversational convenience never becomes a
second authority system or bypass path.

1. Probe the installed Goose version and enforce a tested compatibility range;
   begin with the reviewed `1.45.0` target and verify it again at execution time.
2. Make the governed recipe the only primary Goose launch path. Remove empty-builtin
   and legacy launch behavior from `builder start`.
3. Launch Goose with Builder-II's MCP server as the sole tool extension. Validate
   launch, discovery, invocation, transcript export, interruption, and close.
4. Expand MCP stubs into thin adapters over existing governed services for:
   - repository inspection and search;
   - package preparation and validation;
   - delegation and run status;
   - verification planning and approved execution;
   - patch proposal, approval-required response, apply, postflight, and rollback;
   - Git status, delivery preparation, and approval-required delivery.
5. A mutating tool returns typed approval-required output or consumes an already
   valid approval artifact. It never solicits, infers, or mints approval.
6. MCP and internal callers use the same service and receipt implementation.
7. Replace full-repository close snapshots with scoped target, base, tree, and
   changed-path digests.
8. Do not promote Goose-native subagents as a second v1 orchestrator.

Exit gate: an operator can converse in Goose, delegate through native Deep Agents,
inspect the repository, propose a patch, pause for approval, apply, verify, and
close without leaving the governed evidence chain.

## Plan Set 4: STRATUM and onboarding

Governance distinction strengthened: the cockpit projects admissible actions and
real receipts without becoming an approval or execution authority.

1. Project the canonical run with task, stage, next admissible action, active
   agents, models, budgets, approvals, verification, delivery, and evidence health.
2. Use one state grammar:
   `PREPARE -> PLAN -> APPROVE -> EXECUTE -> VERIFY -> DELIVER/PROMOTE`.
3. Invoke the five already-admitted last-mile commands through the existing
   fixed-argument subprocess helper: prepare package, validate package, assign
   subagent, approve patch, and refuse patch.
4. For approve/refuse, suspend STRATUM and hand the terminal to the real CLI prompt.
   STRATUM must not collect a digest or mint decision evidence.
5. Return to the cockpit with the resulting receipt loaded and validated; preserve
   return codes, cancellation, stderr, and refusal reasons.
6. Replace undeclared `pyperclip` behavior with Textual clipboard support and a
   visible fallback.
7. Add non-authoritative presets:
   - `solo-fast`: local-first, two workers, economical routing, standing grants
     offered only for eligible digest confirmations;
   - `solo-strict`: one worker, confirmation each time, no standing grants;
   - `team`: bounded delegation with explicit model and budget configuration.
8. Presets may configure friction and resources but may not grant approval, enable
   forbidden tools, or promote capabilities.
9. Make `builder init` detect Goose, Deep Agents, local model readiness, GitHub CLI,
   and repository identity, and print exact remediation without silently installing
   external software.

Exit gate: a new user can initialize, select a preset, start work, approve an exact
patch, verify, and reach delivery using only the primary CLI or STRATUM surfaces.

## Plan Set 5: model routing and runtime performance

Governance distinction strengthened: performance and failover cannot weaken model
policy, provider disclosure, budgets, or receipt truth.

1. Make WRP the sole role, model, and budget planner; Deep Agents executes those
   decisions.
2. Route local and cloud models through one gateway. Cloud use remains explicit
   opt-in with provider, cost ceiling, and secret-source disclosure.
3. Add streaming, cooperative cancellation, warm-server reuse, bounded retry, and
   model-health failover without silently selecting a more permissive provider.
4. Pre-register acceptance thresholds:
   - default local model footprint: 2GB-7GB;
   - control-plane RSS excluding model runtimes: below 1GB;
   - idle STRATUM target: at most 250MB;
   - warm governance/orchestration TTFT overhead: at most 20 percent over direct
     gateway time;
   - non-model policy/tool dispatch p95: below 150ms;
   - no default workflow loads two large model runtimes simultaneously.
5. Publish cold and warm TTFT, throughput, memory peak, delegation overhead,
   interruption/resume latency, and governed-tool latency.

Exit gate: the M1 benchmark suite meets the registered thresholds without weakening
receipts, policy, admission, or verification.

## Plan Set 6: governed GitHub delivery

Governance distinction strengthened: local commit, external push, pull-request
creation, review, and promotion remain separate authorized events.

1. Introduce a delivery plan binding repository identity, branch, base revision,
   exact tree and diff digest, commit message, remote, and proposed pull-request
   metadata.
2. Permit local commit only after approval of that exact plan; record commit SHA and
   tree.
3. Require distinct non-delegable approvals for push and pull-request creation or
   update.
4. Refuse direct commits to `main`, force-push, destructive history rewrite,
   mismatched remotes, unexpected dirty paths, changed tree digests, or missing
   exact-tip local CI evidence.
5. Use `gh` for GitHub operations and capture command, repository, branch, URL,
   external result, and failure in delivery receipts.
6. Provide recoverable correction guidance: before push, amend only through a newly
   approved plan; after push, use a corrective commit or approved revert, never a
   silent reset of published history.
7. Test with temporary repositories and mocked GitHub responses. Live GitHub
   mutation requires a separately approved release rehearsal.

Exit gate: the end-to-end scenario prepares and commits locally, halts before
external effects, then pushes and opens a GitHub pull request only under separate
operator approvals, producing a validated delivery receipt.

## Plan Set 7: release proof and open-source v1

Governance distinction strengthened: release and promotion claims bind to the exact
candidate source and executable evidence, not a passing development snapshot.

1. Keep Apple Silicon as the primary performance target. Add reproducible Linux
   install, unit, integration, and CLI smoke coverage. State that the supported
   v1 environments are macOS Apple Silicon and Linux; Windows and WSL2 are
   unsupported for v1 and are not release-parity targets.
2. Run `bash scripts/ci.sh` on the exact release commit. GitHub is used only for
   source hosting and PR mutation; no hosted workflow or status-check evidence is
   required.
3. Build installable wheels and document the recommended `uv tool install` path,
   including the Deep Agents extra.
4. Ship concise docs for the five-minute start, CLI and STRATUM, Goose and Deep
   Agents architecture, HITL, local/cloud models and budgets, recovery/resume,
   GitHub delivery, and extension contracts.
5. Add successful-loop and sabotage scenarios covering denied tools and writes,
   forged or stale approval, budget exhaustion, Deep Agents crash/resume,
   Goose/MCP disconnect, verification failure, patch drift, remote mismatch,
   forbidden push, rollback, and corrective delivery.
6. Generate a release-proof bundle from the exact tag candidate: source digest,
   dependency lock, local CI, Linux smoke, matrix, docs audit, benchmark report,
   supported runtime versions, known limitations, and demo evidence.
7. Promote rows only after all eight gates and executable evidence. Tag and publish
   only after a human promotion decision.

Exit gate: fresh macOS and Linux installations both complete the documented golden
path, and the release-proof bundle validates from the exact proposed tag.

## Verification and delivery discipline

For every plan set:

1. Re-read the implementation and trace imports and callers before changing a
   load-bearing module.
2. Confirm repository, branch, base revision, worktrees, and existing changes.
3. Name every file change and the invariant it protects before commit.
4. Run the smallest pinned verification lane during development.
5. Run matrix and documentation audits when authority, promotion, or documentation
   changes.
6. Run native Deep Agents and Goose contract scenarios for their adapter changes.
7. Run `bash scripts/ci.sh` on the final commit.
8. Inspect the final state, diff, generated artifacts, and untracked paths.
9. Promote no capability from prose alone.
10. Commit on a feature branch, use GitHub review, and merge only after clean
    exact-tip local CI.

## Explicit non-goals

- full Windows parity;
- Kubernetes or a hosted multi-tenant control plane;
- a broad authority-registry or schema rewrite;
- a second Goose-native orchestration system;
- hidden memory or opaque approval inference;
- autonomous human-approval minting or capability promotion;
- default simultaneous loading of multiple large local models;
- live external mutation without the required distinct approval.

## First approval unit

The first executable unit is **Plan Set 0 only**. Its allowed scope is:

- canonical GitHub governance and repository-identity preflight;
- typed matrix and current-state reconciliation;
- exact documentation moves and deletions listed in section 0.3;
- reference, fixture, generator, and test updates required by those moves;
- skipped-test characterization;
- focused tests, docs audit, platform matrix/status, and final local CI;
- feature-branch commit and local handoff after verification.

The first approval unit does **not** authorize Plan Sets 1-7, dependency changes,
native runtime activation, live GitHub mutation, push, pull-request creation, merge,
tagging, release publication, or capability promotion.

## HITL stop

Stop after creating and validating this passive plan. A human approval artifact must
bind this file's exact SHA-256 digest, identify Plan Set 0, enumerate the allowed
paths or path classes above, preserve the denied boundaries, and carry an expiry.
Only then may implementation begin.
