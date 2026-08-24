# Known Limitations

What builder-II will NOT do for you today. Generated from the completion truth matrix
(`builder_ii/core/platform_completion_audit.py`) by `builder-platform known-limitations`; a pinned
test fails CI if this document drifts from the matrix. Regenerate with:

```bash
uv run builder-platform known-limitations --output docs/KNOWN_LIMITATIONS.md
```

For the full per-capability view (including what IS verified), see
[`docs/PLATFORM_COMPLETION_AUDIT.md`](PLATFORM_COMPLETION_AUDIT.md); for what feedback the beta
wants, see [`docs/BETA_CHARTER.md`](BETA_CHARTER.md).

## Verification-lane target scope (read this one first)

The HITL-approved verification lane (`builder-verify run-approved`) and every surface built on
it target **trusted local Python-with-pytest repositories only**.

- The bounded runner constrains **what gets invoked** — fixed argv, `shell=False`,
  env-allowlisted subprocess, digest-bound approval, range-checked timeout. It never constrains
  **what invoked code can do**: running pytest over a repository executes that repository's code
  (including transitive `conftest.py` and plugin code) on your host with your user privileges.
- It is **not a sandbox**, and no builder-II surface may describe it as one. Target-code-executing
  profiles require a schema-enforced execution-risk acknowledgment on the approval artifact
  before the runner will spawn anything.
- Container/VM isolation is post-beta ladder work. Until then: do not point verification lanes at
  repositories you would not run on your machine yourself.

The same trust boundary applies to the governed demo loop's target repositories: the demo mutates
only a disposable detached worktree, but preflight and repo scanning still read the repository you
designate.

## Standing non-authority boundaries (by design, not by gap)

These are not missing features; they are refusals the governance model depends on:

- No ambient Git authority: commit, push, and pull-request delivery exist only in separately
  approved, digest-bound lanes; direct-main, force-push, and history rewrite remain forbidden.
- No autonomous writes: every mutation lane requires an explicit digest-bound operator approval.
- No hidden memory or vector stores; artifact memory is explicit, validated, and replayable.
- Model output is never approval; a valid artifact is never authority; subagent output is never
  truth.
- Receipts are digest-chained evidence for review, not cryptographic proof — builder-II makes no
  signature claims.

## How to read `OPERATIONALLY_VERIFIED`

`OPERATIONALLY_VERIFIED` is a per-capability state, never a platform-wide clearance. Each
verified row carries a sharper `assurance_state` (e.g. `MUTATION_WITH_ROLLBACK_VERIFIED`,
`DEMO_ONLY_VERIFIED`, `PASSIVE_ARTIFACT_VERIFIED`) that is authoritative for risk
interpretation — a live provider call, a temporary demo loop, and a passive artifact renderer
are not equivalent just because they share the legacy completion label.

## Not operational today (from the matrix)

19 of 53 matrix capabilities are operationally verified; the 34 below are not. Each entry lists the matrix state and its recorded blockers verbatim.

- **generic platform identity** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - Truth-state enforcement was static before R0.
  - Some legacy setup helpers still carry CORE-compatible environment names.
- **agent profiles** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - Profiles record read, plan, and proposal authority only.
  - No runtime agent construction, approval, or receipt path exists.
- **verification profiles** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - Profiles propose checks and reject completed-evidence claims.
  - HITL-approved runner and receipt binding are missing.
- **profile packs** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - Lifecycle remains passive.
  - Runtime materialization is intentionally not promoted by R0.
- **config schema** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - R1.1 adds a versioned passive schema with generic BUILDER_* names, legacy CORE_* aliases, target roots, artifact roots, Goose paths, deepagents mode, and disabled capability defaults.
  - Digest-bound builder-setup apply/rollback exist for declared setup paths; ambient runtime authority and migration tooling remain unpromoted.
- **config source precedence** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - R1.1 records precedence as CLI overrides, process environment, .env, builder config file, target/profile defaults, then built-in defaults.
  - Resolution artifacts are consumed by builder-setup apply and operator-lane composition; ambient runtime gate interception remains partial.
- **non-interactive setup/apply/validate** — `MERGED_BUT_NOT_OPERATIONAL` (assurance `BLOCKED_BY_EVIDENCE`)
  - R1.4 disables legacy builder setup writes and redirects operators to the governed builder-setup artifact chain.
  - R1.3A adds digest-bound governed setup apply and setup receipts for declared setup targets only; R1.3B adds digest-bound setup rollback for changed paths covered by setup snapshots.
  - Interactive onboarding, setup wizard UX, and operational runtime promotion remain missing.
- **Goose config overlay/rollback** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - Legacy merge-style Goose config application remains intentionally unimplemented.
  - R1.2 can describe Goose config overlay keys, recipe path registration, secrets-preservation policy, and rollback snapshot requirements passively.
  - R1.3A apply can write declared setup paths only when represented as supported create/replace/mkdir/no-op changes; R1.3B setup rollback can undo eligible setup-created paths. Merge-style Goose config overlay and generic rollback remain unimplemented.
- **HITL decision envelope** — `ARTIFACT_ONLY` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - Digest-bound decision-support artifact + validator exist: criteria with acceptable_range and observed value, assumptions, constraints, alternatives, consequences of approve/reject/escalate, and accountable ownership.
  - Decision support only -- grants_authority / artifact_is_authority / is_approval are false and the validator rejects any true; the operator still approves through the digest-bound HITL lane.
  - Composer wiring to surface the envelope at the STRATUM decision point, and an operational loop that assembles it from real evaluation, are not yet built -- so this stays ARTIFACT_ONLY, never operationally verified.
- **recipe generator/wizard** — `ARTIFACT_ONLY` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - Recipe assets and projections exist.
  - Generator/wizard, preview, apply receipt, rollback path, and compatibility checks are missing.
- **skill generator/installer/validator** — `MERGED_BUT_NOT_OPERATIONAL` (assurance `BLOCKED_BY_EVIDENCE`)
  - Legacy skill copying is disabled from builder setup in R1.4.
  - R1.2 adds passive skill install-plan entries with source/destination digests and conflict notes.
  - Operational install/copy and target-scoped approval are missing; R1.3B setup rollback does not promote generic skill rollback.
- **target profile wizard** — `NOT_STARTED` (assurance `BLOCKED_BY_EVIDENCE`)
  - Guided target profile creation/editing, dry-run preview, source precedence binding, and setup receipt are missing.
- **agent profile wizard** — `NOT_STARTED` (assurance `BLOCKED_BY_EVIDENCE`)
  - Guided agent profile creation/editing with authority preview and disabled runtime defaults is missing.
- **verification profile wizard** — `NOT_STARTED` (assurance `BLOCKED_BY_EVIDENCE`)
  - Guided verification profile creation/editing, command allowlist preview, target compatibility check, and no-execution proof are missing.
- **deepagents/researcher setup wizard** — `NOT_STARTED` (assurance `BLOCKED_BY_EVIDENCE`)
  - Optional dependency readiness exists.
  - Setup wizard for researcher/deepagents capability selection, denied defaults, receipts, and no-runtime proof is missing.
- **setup receipt + rollback artifact** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - Generic records exist.
  - R1.2 adds setup rollback snapshot planning with plan/overlay digests, prior existence markers, content digests, redacted previews, and future rollback operations.
  - R1.3A adds setup apply receipts with changed/skipped/denied paths and before/after digests; R1.3B adds setup rollback receipts for digest-bound rollback execution. Ledger event and replay binding are missing.
- **tool registry** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - Registry and version probes exist.
  - Invocation envelope and effect classification are missing.
  - Version checks remain operator-managed tooling.
- **MCP invocation** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - MCP inventory, policy, call envelopes and receipts exist.
  - Live MCP server execution remains unpromoted; deterministic stub invocation is handled by low-risk tool gateway.
- **passive orchestration assignment** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - Assignment binds artifacts by digest and starts no agents.
  - Runtime assignment execution must wait for B1/B5.
- **workflow/event ledger** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - Ledger records workflow events including verification, model call, read/content-read, and tool stub lanes when session_id is supplied.
  - Full replay policy for all runtime event kinds and memory mutation events remains partial.
- **replay/audit** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - Replay validates passive event order and artifact links only.
  - Replay policy for nondeterministic execution receipts is missing.
- **readonly founder demo** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - Demo writes passive artifacts and status.
  - It does not run verification or inspect live content beyond artifacts.
- **orchestration founder demo wrapper** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - Wrapper is a passive workflow/event demonstration.
  - Operator golden path for real governed read/verify loops is missing.
- **HITL promotion bridge** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - Approval boundary is for candidate design only.
  - No execution authority exists.
- **execution candidate manifests** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - Manifest validates intent, rollback requirements, verification requirements, and command previews.
  - Executor is missing.
- **Goose setup** — `MERGED_BUT_NOT_OPERATIONAL` (assurance `BLOCKED_BY_EVIDENCE`)
  - R1.4 converts builder setup into a fail-closed redirect and removes legacy setup writes from the setup path.
  - Goose runtime promotion, recipe execution, and governed runtime receipts remain missing.
- **Goose command proposals** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - Proposal records require approval and executed=false.
  - Execution envelope and receipt are missing.
- **deepagents policy/readiness** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - Policy/readiness may inspect import metadata.
  - Runtime harness is operational.
- **deepagents passive work artifacts** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - Work artifacts deny model/tool/shell/Goose/deepagents/MCP/network/writes.
  - Runtime harness is operational.
- **notes/handoff artifacts** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - Handoffs summarize and reference evidence.
  - They do not mutate a memory store or prove execution.
- **artifact memory** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - Artifact memory is explicit, content-addressed, and reviewable only.
  - No hidden memory, vector store, autonomous writes, or runtime authority are promoted.
  - Remains PASSIVE_FOUNDATION by design; docs and UX do not imply operational memory mutation.
- **platform doctor/status/audit** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - R0 adds source-derived truth status.
  - R1.6 adds canonical R1 closure report and golden path proof commands.
  - Legacy builder doctor/status remain operator-managed environment helpers.
  - This row is a passive truth projection; operational lanes retain their own scoped assurance states.
- **release proof/quality gates** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - The v1 bundle schema binds exact source, lock, distributions, supported-host proofs, CI, sabotage, benchmark, docs, and custody evidence.
  - Release evidence is lane-specific: a generic PASS record cannot substitute for exact-tip CI, supported-host identity, exact wheel bytes, current benchmark/docs truth, rehearsal custody, or a valid canonical chain report.
  - Whole-bundle payload custody covers every copied distribution, source archive, evidence artifact, constituent log/report, and artifact index; duplicate wheel/sdist types and unindexed extra bytes are refused.
  - The bundle remains evidence rather than promotion, tag, release, or publication authority.
  - The historical V0 passive manifest remains validation-compatible but is not current release authority.
  - This row remains unpromoted until exact-candidate macOS and Linux proof is reviewed and ratified.
- **docs truth enforcement** — `PASSIVE_FOUNDATION` (assurance `PASSIVE_ARTIFACT_VERIFIED`)
  - R0 adds docs truth scanning against the matrix.
  - No runtime authority is promoted by docs enforcement.
