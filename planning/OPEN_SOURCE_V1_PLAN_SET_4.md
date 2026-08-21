# Open-Source V1 Plan Set 4 — STRATUM and Onboarding

STATUS: `PLANNED_ONLY_AWAITING_DIGEST_BOUND_HITL_APPROVAL`

PLAN_BASE: `507eda20f79d0eb434f68fa53a9a0423f547c8ff`
PLAN_BASE_TREE: `a1926492a4c52e4b311cd266f6f9b1e6880cd078`

## Boundary and purpose

Plan Set 3 is closed. This artifact defines the complete Plan Set 4 implementation
unit from the canonical open-source v1 completion plan. It does not authorize
implementation, capability promotion, Plan Set 5 model-performance work, Plan Set 6
Git/GitHub delivery mutation, or release work.

The Plan Set 4 governance distinction is:

> STRATUM projects admissible actions and real receipts without becoming approval,
> execution, orchestration, or promotion authority.

The target operator flow is one coherent surface over the existing governed run:

```text
PREPARE -> PLAN -> APPROVE -> EXECUTE -> VERIFY -> DELIVER/PROMOTE
```

STRATUM may invoke only the exact already-admitted last-mile command vectors named
below. It may never accept free-form argv, mint approval, infer a decision, bypass
command authority, or become a second orchestrator.

## Current-code findings at the frozen base

The current repository already provides strong foundations that Plan Set 4 must
reuse rather than replace:

- `builder_ii/tui/app.py` already exposes STRATUM, the run cockpit, artifact spine,
  signal rail, HITL projection, first-run guide, and a reusable fixed-argv
  `_run_governed_subprocess()` helper.
- STRATUM currently composes rather than directly invokes the relevant last-mile
  commands for package preparation, package validation, subagent assignment,
  patch approval, and patch refusal.
- HITL approval/refusal composition already refuses to manufacture approval inside
  STRATUM; the real CLI owns the digest prompt and decision artifact.
- `_show_composed_command()` currently uses undeclared optional `pyperclip`
  behavior and silently degrades when clipboard support is absent.
- `builder init` already runs a governed nine-decision onboarding pipeline and
  emits passive setup/overlay/rollback/intent artifacts without applying them.
- Existing readiness and authority components already exist for Goose compatibility,
  Deep Agents readiness, model/backend readiness, repository identity, command
  authority, and platform diagnostics. Plan Set 4 must compose those existing
  checks rather than introduce a second readiness subsystem.
- Plan Set 3's governed Goose/MCP runtime is complete and must not be rewritten by
  this work.
- Plan Set 6 owns commit, push, `gh` mutation, and pull-request execution. Plan Set
  4 may detect GitHub CLI readiness but may not execute GitHub delivery.

## Complete implementation envelope after separate digest-bound approval

### 1. Canonical STRATUM run projection

Project the existing canonical governed run into one typed/read-only STRATUM view
covering, at minimum:

- task and target;
- current lifecycle stage;
- next admissible action;
- active parent/child agents and obligation state;
- selected model routes and provider/backend identity;
- budgets and budget exhaustion state;
- pending/satisfied/denied approval state;
- verification plan/receipt state;
- delivery readiness/refusal state;
- evidence-chain health and corruption/refusal state.

Do not create a parallel STRATUM state store. Derive projection from the existing
run manifest, lifecycle events, obligation records, model/tool/HITL/verification
receipts, delivery handoff evidence, and state index.

The projection must distinguish absence, pending, denied, failed, executed,
verified, and promoted states. It may never synthesize a digest, approval,
verification result, or success state.

### 2. One lifecycle grammar

Make all operator-facing stage labels and "next action" logic use exactly:

```text
PREPARE -> PLAN -> APPROVE -> EXECUTE -> VERIFY -> DELIVER/PROMOTE
```

This is a projection grammar, not a new lifecycle engine. Existing canonical event
and receipt schemas remain authoritative.

Every projected next action must be either:

- an admitted exact action;
- a typed human-approval boundary;
- a precise remediation/refusal;
- or `NONE` when the run is complete or blocked without an admitted transition.

### 3. Exactly five fixed last-mile STRATUM invocations

Extend the existing fixed-argv subprocess helper into the one reusable STRATUM
invocation seam for exactly these already-admitted commands:

1. `builder-session prepare-package`
2. `builder-session validate-prepare-package`
3. `builder-deepagents assign-subagent`
4. `builder-hitl approve-patch`
5. `builder-hitl refuse-patch`

Requirements:

- argv is constructed from typed, bounded STRATUM selections and fixed executable
  entrypoints only;
- no shell, no free-form command strings, no caller-selected executable, env,
  timeout, cwd, output path, or extra flags;
- command authority is checked before invocation and remains enforced by the
  underlying CLI;
- STRATUM does not duplicate the command's mutation or receipt logic;
- cancellation and non-zero return codes are preserved truthfully;
- no command is reported successful until its canonical output/receipt is loaded
  and validated.

Goose launch remains the Plan Set 3 governed path and is not counted among these
five Plan Set 4 last-mile actions.

### 4. HITL terminal handoff for approve/refuse

For `approve-patch` and `refuse-patch`:

- suspend STRATUM;
- hand the real terminal to the canonical CLI;
- let the CLI render the exact digest, collect the operator response, and mint the
  canonical decision/receipt;
- STRATUM must not collect a digest prefix, confirmation, approval text, or refusal
  reason on behalf of the CLI;
- after return, STRATUM reloads and validates the resulting canonical receipt or
  decision artifact.

Escape, Ctrl-C, EOF, refusal, expired/stale proposal, digest mismatch, and CLI
non-zero exit must return to STRATUM as truthful cancellation/denial/failure, not
as success.

### 5. Result and receipt reconciliation

Every direct last-mile invocation returns to the cockpit with a typed
non-authoritative invocation outcome containing:

- exact admitted command identity;
- actual process return code;
- cancellation/interruption state;
- bounded stderr/refusal summary when available;
- canonical output/receipt reference and digest when one exists;
- validation result;
- updated lifecycle projection.

STRATUM must not create a parallel execution receipt claiming it performed the
underlying action. It may record only a projection/invocation-observation artifact
if the existing evidence grammar requires one.

### 6. Textual clipboard, no undeclared pyperclip behavior

Remove undeclared `pyperclip` behavior from STRATUM.

Use Textual's supported clipboard API when available. If clipboard support is not
available, show the composed command visibly and provide an explicit fallback
message. Clipboard success/failure must never affect authority or command outcome.

### 7. Non-authoritative operator presets

Add exactly these v1 presets:

#### `solo-fast`

- local-first model/resource preference;
- default two-worker concurrency;
- economical routing;
- standing-grant suggestions only for confirmation points already eligible under
  the existing ratification policy.

#### `solo-strict`

- one-worker concurrency;
- confirmation at every eligible human boundary;
- no standing-grant suggestion or automatic ratification path.

#### `team`

- bounded delegation;
- explicit model and budget configuration;
- no hidden widening of concurrency or provider authority.

Presets configure friction, routing preferences, and resource defaults only.
They may not:

- mint or satisfy approval;
- change command-authority tiers;
- enable forbidden tools;
- bypass budgets;
- select an undeclared provider;
- promote a capability;
- weaken target-profile boundaries.

Preset selection must be inspectable in onboarding/run artifacts and must remain a
configuration input, not authority.

### 8. `builder init` readiness synthesis

Extend `builder init` so the completed onboarding report also checks and reports:

- Goose binary/version compatibility;
- native Deep Agents readiness;
- selected local model/backend readiness;
- GitHub CLI (`gh`) presence/readiness without invoking mutation;
- canonical repository identity.

Reuse existing readiness/doctor/preflight implementations where available.

For every failed or unavailable check, print exact remediation. `builder init`
must not silently install Goose, Deep Agents, GitHub CLI, models, Python packages,
or any other external software.

The init flow remains passive with respect to setup application and external
mutation: it may detect and explain; it may not auto-apply setup, start a runtime,
pull a model, log into GitHub, or mutate a remote.

### 9. STRATUM/onboarding integration

A newly initialized user must be able to:

1. run `builder init`;
2. see readiness/remediation truth;
3. choose one of the three presets;
4. launch STRATUM or the primary CLI;
5. prepare and validate a package;
6. assign a bounded subagent;
7. inspect the canonical run and next admissible action;
8. hand the terminal to the real patch approval/refusal CLI;
9. reload the resulting decision evidence;
10. verify through the existing governed verification path;
11. reach the existing Plan Set 3 delivery handoff boundary.

The flow ends at Plan Set 6 authority. No local commit, push, `gh` mutation, or PR
creation is introduced here.

## Required adversarial qualification

Focused and integration tests must prove at least:

### Projection truth

- every lifecycle grammar stage derives from real canonical evidence;
- missing evidence never becomes success;
- corrupt/foreign/stale event or receipt chains surface as blocked/corrupt;
- next-action projection never invents an unauthorized transition;
- exact target/profile/session identity is preserved.

### Fixed invocation seam

- only the five named commands are reachable;
- arbitrary executable/argv/env/cwd/shell/timeout/output injection is unreachable;
- command-authority denial prevents subprocess invocation;
- actual non-zero return codes are preserved;
- cancellation/interrupt returns to STRATUM without fabricated success;
- receipt persistence or validation failure is surfaced fail-closed.

### HITL

- STRATUM cannot mint patch approval/refusal;
- digest entry occurs only in the real CLI terminal handoff;
- wrong/stale/substituted proposal evidence is refused;
- successful approve/refuse reloads the exact canonical decision/receipt;
- escape/Ctrl-C/EOF leaves no false approval event.

### Clipboard

- Textual clipboard path works when available;
- unsupported clipboard produces visible fallback;
- no `pyperclip` import remains in the STRATUM runtime path.

### Presets

- all three presets are schema/registry validated;
- presets change only admitted configuration defaults;
- no preset grants authority, changes promotion state, or enables forbidden tools;
- concurrency/resource limits remain bounded.

### Onboarding readiness

- each detector can independently pass/fail/unavailable;
- remediation text is exact and stable;
- no detector installs or mutates external software;
- repository identity mismatch is visible;
- missing `gh`, Goose, Deep Agents, or local backend does not fabricate readiness.

### End-to-end Plan Set 4 path

Run a canonical scenario through the real primary surfaces:

```text
builder init
-> select preset
-> STRATUM
-> prepare package
-> validate package
-> assign bounded subagent
-> inspect HITL proposal
-> terminal handoff to approve/refuse
-> reload canonical receipt
-> verify
-> delivery handoff
-> PLAN_SET_6_DELIVERY_AUTHORITY_REQUIRED
```

The scenario must remain inside one valid governed evidence chain.

## Verification gates

During implementation:

```bash
uv run pytest -q <focused Plan Set 4 suites>
uv run ruff check builder_ii tests
uv run builder-platform audit-docs
uv run builder-platform matrix
```

Before publication, run exact-tip receipt-backed:

```bash
bash scripts/ci.sh
```

Also run the native Goose and Deep Agents contract scenarios when their readiness
or projection surfaces are touched.

The final candidate must record:

- exact implementation SHA and tree;
- focused test results;
- full local CI result and receipt digest;
- STRATUM command inventory;
- lifecycle projection/state-grammar evidence;
- preset definitions and authority invariants;
- onboarding readiness evidence;
- end-to-end primary-surface scenario;
- clean worktree and exact hosted tip.

## Allowed implementation scope

After separate digest-bound approval, changes are limited to the directly affected:

- STRATUM/TUI application, projections, widgets, and tests;
- shared fixed-argument invocation helper if extraction is required;
- onboarding/init readiness composition and tests;
- preset schema/configuration and tests;
- narrowly necessary docs/matrix/operator-surface updates.

Do not rewrite Plan Set 3 runtime/MCP authority, WRP orchestration, model gateway,
HITL canonical executors, or verification executors except for a minimal shared
read-only/helper extraction demonstrably required to avoid duplicate logic.

## Explicit denied boundaries

```text
STRATUM_APPROVAL_MINTING        = UNREACHABLE
STRATUM_GENERIC_SHELL           = UNREACHABLE
STRATUM_FREEFORM_ARGV           = UNREACHABLE
STRATUM_SECOND_ORCHESTRATOR     = NONE
STRATUM_SECOND_EXECUTOR         = NONE

PLAN_SET_6_LOCAL_COMMIT         = NOT_AUTHORIZED
PLAN_SET_6_PUSH                 = NOT_AUTHORIZED
PLAN_SET_6_GH_MUTATION          = NOT_AUTHORIZED
PLAN_SET_6_PR_MUTATION          = NOT_AUTHORIZED

CAPABILITY_PROMOTION            = NOT_AUTHORIZED
EXTERNAL_AUTO_INSTALL           = NOT_AUTHORIZED
```

## Exit gate

Plan Set 4 closes only when a new user can initialize, select a preset, use the
primary CLI or STRATUM to project the canonical run, invoke the five admitted
last-mile commands through one fixed-argument seam, complete real HITL terminal
handoff, verify, and reach the Plan Set 6 delivery boundary without copying routine
commands between interfaces or leaving the governed evidence chain.

At closure:

```text
PLAN_SET_3                    = CLOSED
PLAN_SET_4                    = CLOSED
MORE_PLAN_SET_4_HARDENING     = STOP

PLAN_SET_5                    = NOT_AUTHORIZED
PLAN_SET_6_PRODUCT_DELIVERY   = NOT_AUTHORIZED
CAPABILITY_PROMOTION          = NOT_AUTHORIZED
```
