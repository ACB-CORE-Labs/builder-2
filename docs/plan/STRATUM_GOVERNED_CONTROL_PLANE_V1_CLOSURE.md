# STRATUM Governed Control Plane V1 — Closure Contract

Status: **ACTIVE CLOSURE PLAN — NOT A PROMOTION CLAIM**  
Repository: `ACB-CORE-Labs/builder-2`  
Closure branch: `feat/stratum-governed-control-plane-v1-closure`  
Frozen predecessor branch: `claude/system-capabilities-ux-jda2t1`  
Frozen predecessor head: `d51e398ac0aaf703b0e54ea344e273fa432a96c4`  
Baseline `main` observed for this closure: `2dabf2d25b599c85b5a047fb843a73c629679418`

This document is the governing implementation contract for completing the STRATUM operator-surface work that began under ADR-0009. It deliberately separates **implemented**, **reachable**, **verified**, and **promoted**. Nothing in this plan, by itself, promotes a capability or changes the completion matrix.

## 1. Mission

Make STRATUM the real operator control plane for builder-II while preserving builder-II's governance laws:

- the operator can state work in STRATUM and dispatch a governed runtime;
- Goose receives only a mechanically verified governed tool surface;
- repository reads are deterministic, bounded, path-jailed, and receipted;
- run lifecycle and governed effects are visible in the existing session cockpit;
- standing grants relocate confirmation friction without removing evidence;
- human approval remains human;
- source mutations cross the existing HITL apply boundary only after exact approval and verification;
- every successful effect is reconstructible from artifacts, digests, receipts, and hash-chained events;
- failures are represented as failures rather than optimistic UI state.

The target is not "more automation." The target is a stronger control plane whose convenience comes from composition and traceability rather than bypass.

## 2. Non-negotiable semantic laws

### 2.1 Authority

1. **STRATUM is a control plane, not an authority origin.** It may collect intent, project registry truth, consume a valid grant, request a human decision, and invoke a named governed command. It may not invent permission.
2. **The executing boundary re-evaluates command authority.** A TUI check is an early refusal; it never substitutes for the command's own gate.
3. **Dispatch authorization is not effect approval.** A grant that permits "start this governed work now" never satisfies an internal candidate approval, patch approval, promotion decision, rollback decision, or other effect-specific authority.
4. **Human approval minting is permanently nondelegable.** Any point whose prompt *is* the human decision remains outside `GRANTABLE_KINDS`.
5. **Process control is separately governed.** Starting already-governed work may be delegable; stopping a live wrapper remains prompt-only.

### 2.2 Evidence

6. **Mandatory evidence is constitutive of governed execution.** If the required dispatch authorization, ratification record, lifecycle start event, receipt, or other mandatory evidence cannot be persisted and validated, the operation does not silently continue as governed.
7. **Auto-ratification replaces only the pause.** Manual and auto-ratified paths emit equivalent governed artifacts and references, differing only in the decision mode and actor/grant attribution.
8. **Model output is not evidence.** Raw model/Goose output may be retained in a bounded log clearly marked as non-authoritative. It is never used as proof that an effect occurred or passed verification.
9. **Receipts record; they do not self-prove.** Completion requires the relevant policy, input, authorization, postflight, verification, and chain state.

### 2.3 Runtime

10. **A command named `run-governed` may not degrade.** If the installed Goose CLI cannot simultaneously accept the task, load the governed recipe, and disable unauthorized builtins, the wrapper refuses before spawning.
11. **Stop signals the governed wrapper.** STRATUM does not reach around the wrapper to kill Goose directly.
12. **A live process handle is control state, not historical truth.** Historical truth comes from validated on-disk evidence.

### 2.4 Identity and data

13. **Run-bound artifacts are collision-proof.** Manifests, dispatch plans, authorizations, proposals, logs, receipts, and session identities may not rely on overwrite-prone stable names or second-resolution timestamps.
14. **Digest identity and filesystem location are distinct.** A governed reference binds both.
15. **Target root and builder/artifact root are explicit.** `cwd`, `settings.project_root`, `settings.target_repo`, and `.builder` are never treated as interchangeable assumptions.
16. **Read-only means bounded I/O as well as bounded output.** A 64 KiB read cap must not first read a 10 GiB file into memory.

### 2.5 Truth discipline

17. **Implemented != reachable != verified != promoted.** State changes occur only through the existing promotion discipline.
18. **No "main also fails" acceptance standard.** Final closure requires the complete blocking battery to pass on the closure head. Baseline debt is classified and repaired; it is not normalized.
19. **Operator-facing truth is symmetric.** Docs, CLI help, TUI labels, authority records, matrix notes, and runtime behavior must agree.

## 3. Canonical architecture to converge on

The closure must reduce parallel interpretations rather than add more one-off UI logic.

| Component | Owns | Must not own |
|---|---|---|
| `RunContext` | run/session IDs, target root, artifact root, manifest/recipe/task refs | authority, spawning |
| governed invocation resolver | Goose capability detection, exact fixed argv, child environment policy | silent fallback |
| dispatch planner | exact task/manifest/argv/environment/authority subject | approval |
| dispatch authorization | manual/grant/approval-artifact satisfaction bound to one exact plan | internal effect approval |
| session ledger | atomic append, predecessor binding, replay, recovery | authority |
| run supervisor | spawn, lifecycle observation, stop, reap | governance decisions |
| repo read sandbox | bounded deterministic reads under one jail | shell/network/write |
| HITL proposal bridge | passive, source-bound proposal creation | application |
| STRATUM projections | render registry/disk truth | target mutation or fabricated completion |

### 3.1 Intended runtime lifecycle

```text
DISPATCH_PLANNED
  -> DISPATCH_AUTHORIZED
  -> RUN_START_REQUESTED
  -> RUN_STARTED
  -> [RUN_STOP_REQUESTED]
  -> RUN_EXITED
  -> POSTFLIGHT_VERIFIED
  -> LEDGER_REPLAY_VERIFIED
  -> RUN_CLOSED
```

Failure terminals include:

```text
DISPATCH_REFUSED
EVIDENCE_PERSISTENCE_FAILED
SPAWN_FAILED
STARTUP_HANDSHAKE_FAILED
RUNTIME_FAILED
MUTATION_DETECTED
POSTFLIGHT_FAILED
LEDGER_REPLAY_FAILED
STOPPED
```

A process exit alone never projects `RUN_CLOSED`.

### 3.2 Intended evidence graph

```text
manifest
  -> dispatch_plan
  -> dispatch_authorization
       -> ratification_event
       -> standing_grant_ref | manual_actor | approval_artifact_ref
  -> run_intent
  -> launch_receipt
  -> session events
       -> MCP policy snapshots
       -> envelopes
       -> receipts
       -> refusal/proposal refs
  -> postflight
  -> ledger_replay_report
  -> close_receipt
```

`builder-govern trace` and STRATUM inspection should eventually be able to traverse the governing references without relying on prose inference.

## 4. Branch and review discipline

The predecessor branch is frozen at `d51e398a...`; all closure work happens on `feat/stratum-governed-control-plane-v1-closure`.

Rules:

- do not rewrite the frozen predecessor branch;
- no force-push on the closure branch after review begins;
- every effect-bearing commit carries its tests and truth/documentation updates;
- every commit must leave capability states no stronger than the evidence supports;
- the draft PR remains draft until the full closure definition is satisfied;
- no matrix row flips merely because implementation code exists;
- the final reviewed head SHA is reverified before merge.

## 5. Closure phases

### Phase 0 — Reproduce, classify, and restore a trustworthy baseline

Purpose: establish measured repository truth before adding more capability.

Deliverables:

- this closure contract;
- `docs/audits/STRATUM_CONTROL_PLANE_BASELINE_2026-08.md`;
- `scripts/verify_stratum_control_plane.sh` as a high-signal focused lane;
- the focused lane called from the canonical blocking `scripts/ci.sh`;
- parity tests pinning that it remains blocking;
- a draft PR so PR-triggered CI can provide independent evidence when available.

No later capability phase is considered closed until the full gate battery is green. When tests cannot be executed in the current environment, the audit records them as **PENDING OPERATOR EXECUTION**, never as passed.

### Phase 1 — Governed invocation contract

Create one capability resolver that refuses unless the Goose CLI can prove all required properties for the selected mode: task delivery, governed recipe loading, and unauthorized builtin removal. Materialize a run-bound recipe/extension command using explicit interpreter/module/root/session data. Build a child environment without mutating the parent process environment.

Key proof: every unsupported CLI shape refuses before spawn.

### Phase 2 — Repository read sandbox hardening

Consolidate path resolution and read bounds behind one sandbox. V1 policy: do not traverse symlinks. Bound bytes *read*, bytes returned, files scanned, matches, and traversal. Denials remain governed receipts/events.

Key proof: traversal, symlink, reserved-directory, special-file, giant-file, and scan-amplification adversarial cases cannot escape bounds or touch source.

### Phase 3 — Atomic/durable session evidence

Retain one append authority, add atomic same-directory writes and a validated tail checkpoint, and recover only through a full valid replay. Evidence persistence failures become represented failures rather than warnings.

Key proof: concurrent writers cannot fork the chain; crash injection cannot make a partial sidecar look committed.

### Phase 4 — Collision-proof run context and artifact identity

Introduce explicit run context and content-/run-addressed manifests, dispatch records, proposals, logs, and receipts. Bind proposal origin and source preimage. Remove stable overwrite paths and timestamp-only session identity.

Key proof: concurrent runs/proposals cannot overwrite or alias one another.

### Phase 5 — Unified dispatch authorization for CLI and STRATUM

Move ratification/dispatch semantics into one non-TUI application service. Both direct CLI and STRATUM consume the same dispatch plan and one-shot authorization model. Launch receipts bind the decision/grant chain.

Key proof: manual and grant-covered runs emit the same governed evidence graph except for the decision-mode/actor fields.

### Phase 6 — Governed run supervision

Move background process ownership into a dedicated supervisor using fixed argv and explicit environment/cwd. Require a startup handshake before STRATUM claims a run is live. Completion is projected only from close/postflight/replay evidence.

Key proof: spawn failures, child failures, missing handshake, and evidence-close failures cannot appear as successful runs.

### Phase 7 — Cockpit Start / Resume / Stop

Complete the omitted orchestration-cockpit Stage 2. Deepagents Start/Resume go through their existing approved candidate lanes; Stop is separately authority-gated, never grantable, and signals only a wrapper this console owns.

Key proof: tampered/expired/mismatched approvals and non-live stops refuse before effect.

### Phase 8 — Affordance-driven execution

Make `project_action_affordance` control behavior rather than decorate prose. Complete direct governed invocation for prepare-package and assign-subagent. Keep HITL approval/refusal nondelegable; collect refusal rationale explicitly.

Key proof: a structural action matrix prevents registry/UI mode drift.

### Phase 9 — Source-bound in-loop proposal bridge

Make each `propose_patch` artifact unique, content-addressed, bound to origin session/run, normalized target path, canonical diff, and target preimage digest. The denial event digest-binds the proposal artifact.

Key proof: source drift invalidates application rather than silently applying an approval to changed bytes.

### Phase 10 — Full HITL apply + rollback proof

Drive the real temporary-repository scenario through proposal -> real human approval artifact -> real verification receipt -> governed apply -> receipt/rollback bundle -> rollback -> exact preimage restoration. Preserve negative lanes for every missing/tampered/stale prerequisite.

Implementation proof does not itself promote G4.

### Phase 11 — Product truth and mechanical polish

Reconcile docs, CLI/TUI language, authority records, known limitations, and matrix notes. Remove stale "observe-only"/"compose-only" claims. Measure ledger append behavior, event-loop blocking, log bounds, repeated process/help invocations, and resource leaks.

### Phase 12 — Release-candidate evidence and independent review

Run the complete battery, focused lane, deterministic fake-Goose runtime scenarios, Textual Pilot/semantic-driver flows, and a real-Goose verify-by-experiment where available. Require separate safety, evidence, product, and simplification reviews before promotion/merge.

## 6. Permanent structural pins to add through the closure

The finished program should structurally prevent these regressions:

1. no raw Goose adapter launch from `builder_ii/tui`;
2. no direct TUI file writes;
3. no `shell=True` in governed dispatch;
4. no parent-environment mutation by run commands;
5. no spawn without validated dispatch authorization;
6. no auto-ratified spawn without a persisted grant reference;
7. no manual spawn without a persisted decision record;
8. no human-approval point with a grantable kind;
9. no process-control point with a grantable kind;
10. no stable overwrite path for a run-bound artifact;
11. no proposal denial event without a digest-bound proposal reference;
12. no repository read that traverses a symlink under the V1 sandbox policy;
13. no bounded read that first performs unbounded I/O;
14. no successful tool result without a valid receipt and event;
15. no cockpit completion without close/postflight/replay evidence;
16. no material CLI/TUI dispatch evidence divergence;
17. no capability-row flip without promotion evidence;
18. no operator-facing claim stronger than the registry/matrix truth.

## 7. Verification discipline

For each implementation phase, the intended local sequence is:

```bash
# phase-focused tests
bash scripts/verify_stratum_control_plane.sh

# truth surfaces
uv run builder-platform audit-docs
uv run builder-platform matrix

# complete blocking battery
bash scripts/ci.sh --receipt .builder/artifacts/gate-battery-receipt.json
```

The focused lane is deliberately additive. It gives a fast, named failure surface for the STRATUM control-plane invariants; it never replaces the full suite.

TUI semantic proof uses Textual Pilot / `scripts/semantic_tui_driver.py`. PTY evidence is reserved for terminal-boundary behavior such as boot, suspend/resume, and the interactive HITL digest prompt. Visual scraping is not semantic proof.

## 8. Definition of Done

The V1 closure is complete only when all are true:

### Functional

- STRATUM accepts and dispatches a governed Goose task;
- the run becomes live in the cockpit from recorded lifecycle evidence;
- read/list/grep work under the hardened sandbox;
- deepagents Start/Resume and prompt-only Stop work from the cockpit;
- prepare-package and assign-subagent use their governed direct paths;
- a proposed patch appears as an exact reviewable gate;
- approve/refuse can be completed from STRATUM without STRATUM minting the human decision;
- the real approved apply and rollback loop is proven.

### Governance

- CLI and TUI use the same dispatch service;
- auto/manual paths emit equivalent evidence;
- every auto path binds its grant;
- trace reaches the scheduling decision;
- human approval and promotion remain ungrantable;
- mandatory evidence failures prevent or invalidate governed execution.

### Security

- no shell/network in the read-only tool lane;
- no symlink traversal under the V1 policy;
- no `.git`/`.builder` read access;
- no path escape or unbounded read;
- no parent environment pollution;
- no partial/unknown Goose CLI degradation;
- no stale-preimage patch application.

### Reliability

- no run/proposal identity collision or overwrite;
- no ledger fork under contention;
- deterministic crash recovery;
- actual exit codes and close evidence surfaced;
- successful run closure includes postflight and replay.

### Truth and review

- full repository gate battery passes;
- audit-docs and matrix validation pass;
- current docs/UI/authority records agree;
- remaining candidate states are named precisely;
- independent safety/evidence/product/simplification review is complete;
- final reviewed head SHA is the head actually merged.

## 9. Explicit non-goals

Unless separately authorized, this closure does **not** add:

- unrestricted shell execution;
- general network access;
- arbitrary command execution from STRATUM;
- autonomous HITL approval;
- grantable patch approval/refusal;
- automatic capability promotion;
- G4 enabled-by-default;
- silent support for unknown Goose CLI shapes;
- `git_status` inside the pure in-process low-risk gateway;
- a second source-mutation primitive parallel to the existing HITL apply lane.

## 10. Governing principle

The closure is ordered by dependency, not visual impact:

```text
green baseline
  -> invocation safety
  -> read-jail safety
  -> evidence durability
  -> identity
  -> unified authorization
  -> process supervision
  -> cockpit control
  -> affordance completion
  -> source-bound HITL proof
  -> truth/promotion audit
  -> independent review
```

No higher layer is allowed to make a lower-layer uncertainty disappear by UI wording. If evidence is missing, the system says evidence is missing. If authority is absent, it refuses. If a capability is implemented but not promoted, it remains a candidate. That is the control-plane standard this program exists to preserve.
