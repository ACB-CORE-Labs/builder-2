# Open-Source V1 Plan Set 3C1-R1 — Canonical Artifact Namespace and Runtime Integration Correction

Status: `PLANNED_ONLY_AWAITING_HITL_APPROVAL`

Correction base: `88453160be3c1ab07eecf8c42b24f03480aa7adc`

Correction-base tree: `3c079332cf73ea1cd39724f71148f0c093748320`

Parent Plan Set 3C1 base: `fc0fa3f7edfbe26a267527516a274f0de2ea4fe6`

Approved parent plan: `planning/OPEN_SOURCE_V1_PLAN_SET_3C1.md`

Approved parent plan SHA-256: `8c9b905d45822e7da6e5ecbaef672cc3632c04b7cff1492035881389176d2e03`

## Purpose and correction boundary

Correct the artifact-root invariant and qualification gaps discovered during independent hosted
review of the frozen Plan Set 3C1 candidate. The canonical patch binder and passive MCP
authority boundary remain sound. This correction makes that passive service usable through the
real `builder start -> governed Goose -> builder-mcp serve -> patch_proposal` product path while
preserving Builder-II's existing controlled artifact architecture.

This is a successor correction plan. It does not alter the approved parent plan bytes or reuse
their approval. It grants no implementation authority until a human approval artifact is bound
to this plan's exact digest and correction base.

The corrected governing law is:

```text
patch_proposal may write only Builder-II-owned control-plane artifacts beneath the
canonical governed artifact/session namespace. That namespace may be the built-in
<target>/.builder/artifacts location admitted by platform configuration policy.

patch_proposal may write no target source content, Git object/ref/config state, index
state, tracked worktree content, or arbitrary path outside that namespace.
```

An artifact beneath the target directory is not thereby target source authority. Placement is
admitted by canonical namespace custody, path resolution, and write confinement—not by a raw
requirement that the artifact root and target tree be disjoint.

## Exact candidate findings

At `88453160be3c1ab07eecf8c42b24f03480aa7adc`:

- `builder_ii.core.config_schema.CONFIG_FIELD_SPECS` defines
  `platform_artifact_root` with built-in default `.builder/artifacts` and describes it as the
  canonical root for passive Builder-II artifacts.
- `builder_ii.core.config_sources._validate_resolved_fields` explicitly admits an artifact root
  beneath `<target>/.builder/artifacts`; other inside-target locations require explicit path
  policy or are denied.
- `builder_ii.cli.mcp_cli.serve` defaults `builder_root` to `.builder` and binds `target_root` to
  `Path.cwd()`.
- `GooseRuntimeHarness.launch_governed` launches Goose with `cwd=target_root` and the governed
  recipe invokes only `builder-mcp serve`, without an external artifact-root override.
- `_patch_proposal` denies when `builder_root` is beneath `target_root`. The canonical product
  path therefore resolves `<target>/.builder` and denies every otherwise valid proposal.
- That one-directional containment test also does not establish the parent plan's stronger
  disjoint-tree claim when a target is nested beneath the builder root.
- The 3C1 target fingerprint hashes regular-file bytes only; it does not bind Git HEAD/tree,
  index, porcelain status, file modes, or symlink targets.
- Qualification covers corrupt prior ledger and proposal-writer failure but does not cover
  failures after proposal persistence while writing the MCP service receipt or event.
- `SPRINT_LOG.md` retains pre-commit wording after the candidate was committed and pushed.
  `recipes/governed-readonly.yaml` still describes only read-only stub tools and treats every
  file-writing task as forbidden, although passive proposal artifact creation is now admitted.

## Preserved 3C1 architecture

The correction must preserve these candidate properties without redesign:

1. `create_bound_hitl_patch_proposal()` computes SHA-256 from exact UTF-8 diff bytes and binds
   exact verification-receipt bytes.
2. MCP accepts exactly `unified_diff`, `description`, `reason`, `target_head_sha`, and
   `verification_receipt_path`; the caller supplies no digest, target, scope, output, approval,
   execution, shell, or environment authority.
3. Target identity comes only from the admitted server target profile and resolved target root.
4. The canonical proposal is persisted, reloaded, and validated before the service projects
   `HUMAN_APPROVAL_REQUIRED`.
5. `HUMAN_APPROVAL_REQUIRED` remains a passive result projection; the ordinary MCP receipt uses
   its existing status vocabulary.
6. The retired MCP apply adapter, gated `propose_patch` alias, `run_shell` inventory, environment
   reactivation path, and second executor remain absent and unreachable.
7. Operator-side HITL approval, apply, postflight, and rollback code remains untouched and
   unavailable through MCP. Plan Set 3C2 remains unauthorized.

## Corrected governing invariants

1. **One canonical artifact root.** MCP uses the platform's resolved
   `platform_artifact_root`; it does not invent a 3C1-only external root or silently substitute
   a parallel artifact vocabulary. The built-in `<target>/.builder/artifacts` topology is valid.
2. **Trusted resolution.** The canonical artifact root is derived from trusted Builder-II
   configuration/launch state, normalized once, and bound into the MCP server. A tool caller
   cannot select or override it. Invalid configuration fails before server launch or proposal
   persistence.
3. **Namespace confinement.** Proposal, MCP policy, service receipt, and event paths are chosen
   by Builder-II beneath the resolved artifact/session namespace. Resolution must reject
   traversal, symlink escape, aliasing through symlinked ancestors, and any computed path that
   is not a strict descendant of the admitted namespace.
4. **Overlap semantics.** If the artifact namespace is inside the target, it must be the
   canonical `<target>/.builder/artifacts` namespace or another location explicitly admitted by
   existing path policy. If the target lies inside the artifact root, or the roots otherwise
   overlap in a way that makes the generated session path enter target source space, launch or
   service admission fails closed. Neither ancestor direction is assumed safe without applying
   the canonical namespace policy.
5. **Artifact writes are not source writes.** Qualification classifies and snapshots the
   admitted Builder-II artifact namespace separately. Expected artifact additions may occur
   there; no change may occur to tracked source, `.git`, index, refs, configuration, file modes,
   symlink metadata, or any non-artifact worktree path.
6. **Canonical product path works.** A real or faithful unmocked launch-path test proves that
   the static governed recipe starts `builder-mcp serve` in the target cwd with the same trusted
   artifact-root binding used by normal configuration and that `patch_proposal` succeeds through
   MCP at the built-in default location.
7. **Fail-closed evidence publication.** MCP does not return an approval-ready response until
   the proposal, service receipt, and event evidence have all been durably written and
   revalidated. A failure at any stage returns a typed failed/denied response without
   `HUMAN_APPROVAL_REQUIRED`. A persisted proposal left by a later failure is explicitly
   orphaned/failed evidence and must not be discoverable as a successful call.
8. **Transport remains thin.** Artifact-root admission and proposal creation use canonical
   configuration, path-policy, artifact, and governed-service code. Goose, its recipe, and MCP
   transport do not duplicate digest, scope, proposal, or executor logic.
9. **No promotion by correction.** Passing correction tests does not promote patch application,
   approval minting, shell, rollback, delivery, Goose authority, or any truth-matrix capability.

## Exact implementation path scope

Implementation authority, if later granted for this exact plan, is limited to the paths below.
Any required source path outside this list requires a re-digested successor plan and approval.

### 1. Canonical MCP artifact-root resolution and confinement

Expected files:

- `builder_ii/core/config.py`
- `builder_ii/core/config_sources.py` and `builder_ii/core/config_schema.py` only if a narrowly
  shared resolver/admission helper is required; do not change the existing default or broaden
  inside-target policy
- `builder_ii/cli/mcp_cli.py`
- `builder_ii/adapters/mcp/server.py`
- `builder_ii/adapters/mcp/governed_services.py`
- Focused configuration, CLI, server, and MCP-service tests

Required change:

- Make `builder-mcp serve` consume the canonical resolved `platform_artifact_root` for its
  session/evidence root. Preserve an explicit operator override only if it passes the same
  trusted namespace policy; do not add a caller-visible MCP tool argument.
- Replace the raw `_within(builder_root, target_root)` refusal with one canonical admission and
  confinement rule that handles disjoint roots, the admitted `<target>/.builder/artifacts`
  namespace, both ancestor directions, equality, traversal, and symlink-resolved overlap.
- Require all generated proposal/service-receipt/event paths and controlled receipt reads to be
  beneath the admitted artifact root. No generic filesystem write/read primitive is added.

### 2. Canonical governed Goose/MCP integration

Expected files:

- `builder_ii/adapters/goose/goose_runtime_harness.py`
- `builder_ii/adapters/goose/goose_compatibility.py` only if the trusted launch binding changes
  the exact admitted extension shape
- `builder_ii/cli/goose_cli.py` and/or the canonical `builder start` owner found by call-site
  tracing
- `recipes/governed-readonly.yaml`
- Focused Goose recipe, compatibility, harness, CLI, and end-to-end MCP tests

Required change:

- Carry the already resolved canonical artifact-root identity into `builder-mcp serve` through
  trusted launch configuration while keeping target identity bound to the Goose cwd/profile.
- Keep the recipe generic and static where practical; if an environment binding is used, it
  must be produced by the admitted launcher, not model/tool input, and must be revalidated by
  the MCP process.
- Prove the actual default product topology, including target cwd and `.builder/artifacts`, can
  create a passive proposal and its evidence without enabling file editing or patch execution.

### 3. Strong target/source-state and failure-sequence qualification

Expected files:

- `tests/test_mcp_plan_set_3c1_patch_proposal.py`
- New narrowly named integration test file if needed for the full Goose/MCP path
- Existing reusable Git/worktree fingerprint test helpers only if direct tracing shows they are
  canonical and can be reused without weakening their owners

Required change:

- Replace the regular-file-only fingerprint with a Git-initialized target fixture and a
  deterministic snapshot that binds at least HEAD, HEAD tree, index tree, porcelain v2 status,
  tracked/untracked path set outside the admitted artifact namespace, file type/mode, regular
  file bytes, and symlink targets/metadata. Snapshot `.git` state sufficiently to detect ref,
  index, config, and object mutation caused by the call.
- Compare source/Git state before and after every success, denial, corrupt-input, overlap, and
  artifact-write-failure case. Separately enumerate the exact admitted artifact additions.
- Inject failures at proposal write, proposal reload/validation, service-receipt write,
  service-receipt reload/validation if present, and event append/ledger validation. Assert no
  successful/approval-ready response and no successful event/receipt for an incomplete call.
- Spy directly on approval construction, apply/rollback entrypoints, `subprocess.run`,
  `subprocess.Popen`, `os.system`, and any Git mutation boundary. Every 3C1 case records zero
  dangerous calls.

### 4. Documentation truth repair

Files:

- `SPRINT_LOG.md`
- `recipes/governed-readonly.yaml`
- `docs/GOOSE_RUNTIME.md`
- MCP/operator inventory or command-authority documentation and generator only if truth-pin
  tracing proves the correction changes generated claims

Required change:

- Make the sprint entry historical: distinguish pre-commit qualification from the frozen local
  candidate and push-only hosted publication. Do not claim independent approval, PR readiness,
  merge, or promotion.
- Describe `patch_proposal` as an allowed passive planning action that writes only governed
  Builder-II artifact evidence. Continue to prohibit target source editing, approval creation,
  apply, rollback, shell, Git mutation, and generic file writes.
- Preserve the governed recipe's single-extension compatibility contract and inventory-first
  language. Do not relabel the whole MCP surface as mutating merely because it persists passive
  artifacts.

## Rejected surfaces and denied boundaries

The correction adds no MCP argument for artifact root, output path, target, digest, scope,
approval, apply, rollback, Git, shell, command, argv, environment, cwd, timeout, network,
credentials, model, Goose, or Deep Agents. It adds no arbitrary read/write service and no
combined propose-and-approve/apply operation.

This plan does not authorize approval minting, patch application, `git apply`, rollback
execution, generic shell/file-write tools, target source or Git mutation, 3C2 implementation,
capability promotion, truth-matrix promotion, dependency changes, commit, push, PR, merge, tag,
release, or any production/external-system action.

## Adversarial qualification matrix

| Obligation | Positive proof | Failure/lesion proof | Bound assertion |
|---|---|---|---|
| Default product path | Governed launcher plus static recipe reaches `builder-mcp serve` in target cwd and `patch_proposal` succeeds under canonical `.builder/artifacts` | Missing, invalid, caller-overridden, or changed-after-admission artifact identity fails before proposal success | One canonical config-derived artifact root; no second root |
| Namespace confinement | All four evidence classes land beneath the exact admitted session namespace | Traversal, symlink ancestor/leaf, equality, reversed nesting, and generated-path escape fail closed | No read/write outside canonical artifact namespace |
| Built-in inside-target policy | `<target>/.builder/artifacts` succeeds and only expected evidence changes there | Any inside-target location outside canonical policy is denied absent existing explicit opt-in | Artifact custody is distinct from source authority |
| Target binding | Proposal target equals trusted target cwd/profile | Caller target/artifact/output aliases are rejected | Tool caller cannot redirect either target or artifacts |
| Full no-source-mutation | Success preserves HEAD/tree/index/status, `.git`, modes, symlinks, and all non-artifact worktree content | Every denial and injected evidence failure preserves the same state | Artifact-only additions are enumerated separately |
| Post-persistence failure | Complete proposal, receipt, event chain revalidates before success is returned | Proposal reload, receipt write/validation, event write/ledger validation failures never expose approval readiness | Orphan evidence is not successful evidence |
| Passive boundary | Exact digest/scope/receipt binding and `HUMAN_APPROVAL_REQUIRED` remain intact | Approval, apply, rollback, shell, subprocess, and legacy names remain absent/unreachable | Dangerous-boundary spies have zero calls |
| Documentation truth | Recipe and sprint text match hosted candidate and passive artifact semantics | Truth audit rejects stale stub-only/pre-commit claims | No promotion or 3C2 implication |

Additional required cases:

- A target with tracked files, untracked files, executable mode, symlink, staged change, and
  unstaged change retains identical state across a successful proposal except for admitted
  ignored artifact evidence.
- A target nested beneath the proposed artifact root and an artifact root equal to the target
  are denied before writes.
- A symlinked `.builder`, `artifacts`, session, receipt, proposal, receipt-output, or events
  component cannot redirect I/O.
- One-byte diff and verification-receipt changes still alter only their authoritative digests;
  no normalization or caller override is introduced by the correction.
- `BUILDER_MCP_GOVERNED_APPLY` and similarly named environment values cannot reactivate retired
  routes or influence artifact-root admission.
- The exact MCP inventory still contains passive `patch_proposal` and contains no
  `propose_patch`, `run_shell`, `approve_patch`, `apply_patch`, rollback, generic write, or
  combined mutation tool.

## Verification commands for later implementation

Run the smallest owner tests during implementation, then the complete correction selection and
mandatory local CI on the exact clean candidate commit:

```bash
uv run pytest -q \
  tests/test_config_schema.py \
  tests/test_config_sources.py \
  tests/test_goose_compatibility.py \
  tests/test_goose_runtime_harness.py \
  tests/test_mcp_server.py \
  tests/test_mcp_plan_set_3b1_hardening.py \
  tests/test_mcp_plan_set_3b2_status_verification.py \
  tests/test_mcp_plan_set_3b3_verification_execution.py \
  tests/test_mcp_plan_set_3c1_patch_proposal.py \
  <new-canonical-product-path-test-if-created>
uv run ruff check builder_ii tests
uv run builder-platform audit-docs
uv run builder-platform matrix
git diff --check
bash scripts/ci.sh
```

Before implementation, replace any placeholder test filename with the actual in-scope path and
record it in the approved execution receipt. The final qualification artifact must bind the
correction plan digest, candidate commit/tree and parent, stable pre/post-gate HEAD, clean
worktree, focused/full counts, all blocking outcomes, unchanged capability matrix, exact MCP
inventory, full pre/post target-source state, enumerated artifact-only changes, and evidence
digests. Green tests do not self-certify promotion.

Required exit invariants:

```text
MCP_PATCH_PROPOSAL = PASSIVE_ONLY
MCP_CANONICAL_PRODUCT_PATH = OPERATIONAL
MCP_ARTIFACT_WRITES = CANONICAL_NAMESPACE_ONLY
TARGET_SOURCE_AND_GIT_MUTATION = NONE
MCP_PATCH_APPLICATION = UNREACHABLE
MCP_APPROVAL_MINTING = UNREACHABLE
MCP_GENERIC_SHELL = UNREACHABLE
SECOND_PATCH_EXECUTOR = NONE
3C2_AUTHORIZED = NO
```

## Rollback strategy

Before merge, rollback is a normal revert/deletion of only the approved 3C1-R1 correction
changes on its feature branch, returning exactly to candidate `88453160…`; do not edit or erase
the parent 3C1 plan or its evidence. After merge, use a normal revert pull request against the
exact correction commit; do not rewrite history or mutate historical proposal/MCP receipts.

Rollback must keep the retired MCP apply/shell path retired and the canonical proposal binder's
internally computed digests intact. If the runtime integration correction must be reverted,
truth documentation must again state that `patch_proposal` is unavailable through the canonical
Goose path rather than falsely claiming operation.

## Final HITL stop

This artifact is passive planning evidence only. Stop after validating and digesting it. Do not
modify source, tests, recipe, or sprint documentation; do not commit, push, open a PR, merge,
mint an implementation approval, or begin Plan Set 3C2.

Implementation may begin only after a human supplies a repository-recognized approval bound to
this exact plan digest, correction base, implementation path scope, denied boundaries,
qualification matrix, and rollback strategy. Re-inspect hosted state at that time; base drift or
required scope expansion requires reconciliation and, where material, a re-digested successor
plan.
