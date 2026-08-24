# Unified operator workspace completion plan

Status: active successor implementation plan. This document records scope and
acceptance; it is not an approval artifact, execution receipt, capability
promotion, release decision, or self-hosting admission.

Date: 2026-08-24

Predecessor: `OPEN_SOURCE_V1_COMPLETION_PLAN.md`. The predecessor and its plan-set
evidence remain historical truth. This plan does not rewrite those results.

Live execution status, verification, discoveries, decisions, blockers, and
deferred opportunities are maintained separately in
`UNIFIED_OPERATOR_WORKSPACE_PROGRESS.md`. This plan defines the destination and
ordered acceptance contract; the progress ledger records what actually happened.

## Status vocabulary

Every work item and plan set uses exactly one of:

```text
NOT_STARTED
IN_PROGRESS
IMPLEMENTED_ON_BRANCH
FOCUSED_VERIFIED
LOCAL_CI_VERIFIED
PR_OPEN
MERGED
PROMOTED
BLOCKED
DEFERRED
```

These states are intentionally non-transitive. In particular, implemented is not
verified, verified is not merged, and merged is not promoted. The progress ledger
must name exact commands and evidence before advancing a verification state.

## Product contract

The normal developer experience is:

```text
builder init
builder start --task "..."
-> converse naturally in Goose
-> inspect and delegate without copying commands
-> review an exact proposed patch
-> approve or refuse through canonical HITL
-> apply, verify, recover, commit, push, and open a PR under distinct authority
-> resume without reconstructing context
```

The normal-user grammar is exactly:

```text
builder init
builder start --task "..."
builder resume [RUN]
builder inspect [RUN]
builder doctor
```

`builder status [RUN] --watch`, contextual action invocation, and specialist
commands remain stable expert and automation surfaces. They are not knowledge a
normal user must memorize.

The interface principle is:

> Calm by default; explicit at authority, ambiguity, corruption, escalation,
> recovery, and external-effect boundaries.

Cutover of the existing `builder start` waits for the complete golden-path gate.
Zellij is an optional enhanced workspace host with a complete plain-terminal
fallback. Builder-II self-hosting remains a separate future admission program.

## One canonical run

Extend the existing governed-run, WRP, workflow, model, MCP, HITL, patch,
rollback, verification, delivery, and state-index artifacts. Do not create a
parallel artifact vocabulary.

One run binds:

- run, target, exact Git state, task, configuration, profiles, policy, and tools;
- WRP topology, roles, models, budgets, concurrency, obligations, and stop rules;
- Goose binary/version/recipe/session/process/transcript lifecycle;
- Deep Agents candidates, checkpoints, parent/child results, and evidence;
- tool, approval, patch, rollback, verification, Git, delivery, recovery, and
  close receipts; and
- one monotonic hash-linked event chain.

A run may have several resumed process instances but one logical Goose session.
A fork creates a new builder run with parent lineage. In-place history editing is
forbidden; an edited history must fork and bind new transcript bytes.

## Subsystem ownership

```text
Goose             human conversation and session interaction
WRP               workload, topology, roles, routes, budgets, stop conditions
Deep Agents       admitted durable graph execution and context isolation
Builder-II        authority, services, effects, evidence, recovery, delivery
STRATUM Lens      compact run state and contextual attention/actions
STRATUM Inspect   forensic evidence and authority inspection
Zellij/plain host process arrangement only
```

No model, UI, recipe, role, skill, workspace, hook, adversary reviewer, runtime
adapter, or action descriptor originates approval.

## Plan Set 0 - authority and adoption baseline

1. Add this successor plan, the unified interaction contract, and the Goose
   capability adoption matrix.
2. Preserve current capability states. Documentation alone promotes nothing.
3. Probe exact installed/runtime versions and binary digests. Goose `1.47.0` is
   installed locally while current source admits `>=1.45.0,<1.47.0`; qualify it
   before widening, otherwise retain the range and print exact remediation.
4. Retain Deep Agents `<0.7.0` until a separate compatibility battery passes.
5. Establish core ownership of the existing validator-backed run projection and
   keep a one-release TUI compatibility facade.

Exit: focused projection tests, source truth, and docs audit pass with no matrix
promotion.

## Plan Set 1 - run registry and frontend-neutral RunView

1. Converge governed runs, Goose sessions, Deep Agents, MCP, HITL, verification,
   and delivery around one durable run registry under the admitted artifact root.
2. `RunView` is the only frontend read model. It exposes identity, goal,
   canonical stage, activity, attention, next actions, agents, models, budgets,
   changes, approvals, verification, delivery, evidence health, failures, and
   recovery.
3. Artifact presence never implies verification. Foreign, expired, corrupt, or
   drifted evidence blocks dependent actions.
4. Replace environment-oriented `builder status` with run status; move environment
   health into `builder doctor`.
5. Support deterministic `builder status [RUN]`, `--watch`, and `--json` without
   repeatedly scanning the entire artifact tree.

Exit: complete/fail/interrupt/resume/cancel/corrupt/orphan/close scenarios yield
identical truth through every frontend.

## Plan Set 2 - STRATUM Lens, Inspect, and visual validation

1. Wide Lens shows `goal / now / needs you / next / proof`; Goose retains at least
   70 percent of terminal width.
2. Narrow Lens collapses to one non-color-only line and opens as an overlay.
3. At most five global chords, seven visible actions, two permanent panes, and no
   mouse dependency.
4. Reposition the current app as `builder inspect [RUN]`; keep `builder stratum`
   as a one-release alias.
5. Add fixed-size Textual Pilot fixtures, deterministic SVG/image captures, real
   PTY interaction, resize/focus/suspend/return tests, and supervised dogfood.
   Visual captures are UX evidence, never governance evidence.

Exit: required `80x24`, `100x30`, `120x40`, and `160x50` layouts are usable; a
local event is visible within 500 ms and projection computation p95 is below 100
ms on the primary M1.

## Plan Set 3 - contextual governed actions

Generalize the existing five typed STRATUM commands. Every action binds one current
command-authority record, typed run inputs, exact artifact refs/digests, an
interaction mode, consequences, cancellation policy, expected output kinds, and
owning validators.

Interaction modes are `inline_query`, `background_stream`, `floating_tty`, and
`refuse`. Closed adapters own executable and argv construction. No descriptor or
frontend supplies shell, environment, cwd, timeout, arbitrary flags, or output
paths.

Initial intents cover continue, inspect, independent review, diff, verification,
approve/refuse, apply, pause/cancel/recover, rollback, delivery, and close/handoff.
Tier 3 decisions run in the owning CLI TTY. No success appears before canonical
output reload and validation.

Exit: zero raw-shell reachability, UI-originated approvals, or premature success
claims; specialist CLIs remain compatible.

## Plan Set 4 - Goose session and context mastery

1. Bind start/resume/interrupt/cancel/diagnostics/export/recovery/close to the run.
2. Record exact Goose binary SHA-256, version, capability probe, recipe digest,
   logical session, process instances, and transcript refs.
3. Export canonical JSON transcripts at checkpoint/close; bind derivative Markdown.
4. Derive max-turn and repetition bounds from WRP.
5. Preserve target, run, obligations, approval state, budget, uncertainty, and next
   action across context compaction.
6. Provide builder-owned progressive `guidance_catalog`, `guidance_read`,
   `role_catalog`, and `role_activate` services projected from canonical profiles.
7. Keep developer/shell builtins, native Goose subagents, hooks as governance,
   adversary output as authority, ACP nesting, and in-place history editing out of
   the canonical path.

Exit: resume duplicates no settled effect; forks/edits cannot retain prior
execution custody; Goose gains no native mutation or approval authority.

## Plan Set 5 - real Deep Agents engineering delegation

Add `delegation_start` as a thin builder MCP service. Goose supplies only the
current run, task, intent, bounded scope, and optional role family. Builder-II and
WRP derive obligations, profiles, model routes, tools, budgets, concurrency,
checkpoints, and HITL conditions.

Qualify `repo_mapper`, `failure_triager`, `code_reviewer`, `patch_planner`,
`verification_planner`, and `handoff_scribe` using governed map/search/read/status
tools. No target writes, shell, Git, direct provider access, or Goose internals.

Default active workers are two, hard experimental maximum four, with one large
local model runtime at a time. Interrupt/resume is tested before a model call,
during a child, after partial completion, before synthesis, at HITL, during result
collection, and after transport failure.

Exit: real read-only engineering roles produce useful, reconstructable evidence;
resume repeats no settled effect and invents no child result.

## Plan Set 6 - model quality and routing mastery

Create a role-specific quality spine distinct from runtime performance. Freeze and
digest fixtures, expected facts, accepted commands, and support/refutation/
inconclusive conditions before collection.

Qualify local roles separately for mapping, localization, planning, coding, review,
verification, tool reliability, refusal, compression, and handoff. Authority and
governance-critical facts require zero violations. Tool schemas require at least
99 percent validity; forbidden tools/arguments remain zero. Models qualify by role,
never one aggregate score.

Routing is local-first: small qualified specialist, primary local coder, explicit
heavy local candidate, then separately approved cloud fallback. Runtime telemetry
may propose a versioned WRP policy change but never applies it.

Exit: at least one local route qualifies for every default role; cloud fallback is
separately demonstrated and off by default.

## Plan Set 7 - terminal workspace and five-command experience

Implement `TerminalWorkspaceBackend` with `zellij` and `plain` implementations.
Zellij uses a generated layout and no plugin. Plain mode uses foreground Goose,
the same-TTY Lens/overlay, and temporary canonical TTY handoffs. Pane/layout state
is never canonical evidence, and closing a pane never closes a run.

`builder start --task` performs target/config admission, run creation, WRP
derivation, governed recipe/MCP admission, workspace selection, Goose launch, and
Lens attach. It generates and persists the WRP route artifacts currently demanded
from the user. `--workspace auto|zellij|plain` is an expert option; `auto` never
installs software.

Exit: zero routine command copying or separate terminal applications; a new user
needs no specialist command names, while an expert reaches raw evidence in one
gesture.

## Plan Set 8 - integrated patch, recovery, and GitHub delivery

Wire existing services for inspection, delegation, proposal, diff, HITL, apply,
verification, rollback, commit, push, PR, and close. Do not reimplement executors.

Patch apply and rollback consume their distinct exact approvals. Local commit,
push, and PR creation/update remain distinct decisions. Push requires settled-tip
local CI. Refuse main commits, force push, history rewrite, remote mismatch,
unexpected dirty paths, stale trees, and missing evidence. Use `gh`; GitHub Actions
and hosted checks are not verification gates.

Exit scenarios include read-only assessment, multi-agent triage, refusal, approved
apply, resume, model escalation, failed verification/replan, rollback, Goose/MCP
crash recovery, commit/push/PR, corrupt evidence, and budget exhaustion.

## Plan Set 9 - cutover and exact-tip closure

Only after Plan Sets 0-8 pass, atomically replace the default `builder start`, move
the explicit artifact-heavy launcher behind its specialist surface, publish the
five-command quickstart, and update matrix rows only through the eight promotion
gates.

Every implementation PR uses an exact clean base, focused tests, owning validators,
docs/matrix checks, a settled commit, receipt-backed `bash scripts/ci.sh`, clean
tree verification, push, PR, and hosted readback. Physical measurements follow the
stricter commit-first exact-tip custody sequence.

## Program acceptance

| Measure | Required result |
| --- | ---: |
| Routine command copying | 0 |
| Separate terminal applications | 0 |
| Default permanent panes | <=2 |
| Global default key chords | <=5 |
| Visible actions | <=7 |
| Full evidence reveal | one gesture |
| Effects without validated receipts | 0 |
| UI/model-originated approvals | 0 |
| Terminal states without recovery/diagnosis | 0 |
| Resume duplicates | 0 |
| Mouse dependency or color-only state | none |
| Unsupported runtime starts | 0 |
| Default concurrent large models | 1 |
| Local CI before push/PR | required |

No plan-set implementation, merge, tag, release, publication, promotion, or
self-hosting admission is implied by this document alone.
