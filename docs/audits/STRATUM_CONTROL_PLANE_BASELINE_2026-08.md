# STRATUM Governed Control Plane — Baseline Audit

Date: 2026-08-08  
Status: **BASELINE RECORDED — EXECUTION VERIFICATION PENDING OPERATOR RUN**  
Repository: `ACB-CORE-Labs/builder-2`

This audit records the starting truth for the STRATUM governed-control-plane closure. It is intentionally conservative: facts obtained from repository inspection are separated from prior local-test claims in commit messages, and no unavailable test run is restated as independently verified.

## 1. Immutable baseline identity

| Item | Value |
|---|---|
| `main` observed at closure start | `2dabf2d25b599c85b5a047fb843a73c629679418` |
| Frozen Claude branch | `claude/system-capabilities-ux-jda2t1` |
| Frozen Claude head | `d51e398ac0aaf703b0e54ea344e273fa432a96c4` |
| Closure branch | `feat/stratum-governed-control-plane-v1-closure` |
| Closure branch parent | `d51e398ac0aaf703b0e54ea344e273fa432a96c4` |
| Claude branch relation to observed `main` | 9 commits ahead, 0 behind |
| Completion-matrix promotion from Claude work | none claimed by the branch |

The predecessor branch is frozen for auditability. Closure work proceeds only on the closure branch.

## 2. What repository inspection establishes

The frozen Claude branch contains substantive implementation, not only design work:

- reachable `builder-goose start-governed` and `builder-goose run-governed` command surfaces;
- a shared `session_ledger.py` append path using an exclusive `flock`;
- governed MCP read tools for file read, directory listing, and literal grep;
- streamed Goose run lifecycle events and a bounded raw-output log concept;
- STRATUM `Ctrl+G` task entry and background dispatch into the run cockpit;
- a new `governed_dispatch_confirmation` ratification kind and dispatch resolver/recorder;
- direct governed HITL approve/refuse handoff from STRATUM;
- in-loop `propose_patch` conversion into a passive HITL proposal artifact;
- honesty/polish repairs including retirement of the broken legacy `builder start` runtime path;
- explicit documentation that cockpit Start/Stop/Resume over deepagents was not built in the Claude stream.

These are code-presence/reachability observations. They are not promotion claims.

## 3. Verification provenance — do not conflate with present proof

Claude's later commits repeatedly report the following local comparison:

- full suite on then-current `main`: **32 failures**;
- full suite on the Claude branch: **29 failures**;
- focused new lanes plus ruff/mypy/bandit/audit-docs reported green.

Those numbers are useful historical diagnostics, but they are **not independently reproduced by this closure audit**. At the frozen head there was no PR-associated GitHub Actions result available through the repository connector. Therefore the only honest current status is:

> **Full blocking battery: PENDING OPERATOR EXECUTION.**

The closure program rejects "fewer failures than main" as an acceptance criterion. The required final state is a green blocking battery.

## 4. Known load-bearing findings at closure start

The following findings were identified by adversarial code review and are treated as closure obligations rather than optional polish.

### B0-01 — Headless governed invocation can degrade

Severity: **P0 / boundary integrity**

The current headless resolver primarily requires Goose to advertise task delivery (`--text`) while recipe loading and builtin stripping are conditionally appended only when those flags appear in help text. A command called `run-governed` must refuse unless the complete governed boundary is mechanically representable.

Required closure: one capability resolver that proves task delivery + governed recipe + unauthorized-builtin removal before spawn.

### B0-02 — Repository grep jail is not yet a complete symlink boundary

Severity: **P0 / sandbox escape**

The initial grep root is resolved through the jail, but recursively discovered files can still be opened after lexical containment checks. V1 closure should reject symlink traversal rather than attempting a partially portable "safe symlink" policy.

Related issue: bounded `read_file` currently reads the complete file before truncating the returned bytes, so output is bounded while I/O/memory is not.

Required closure: one strict read sandbox with bounded reads and no symlink traversal.

### B0-03 — Mandatory lifecycle/ratification evidence is currently best-effort in places

Severity: **P0 / epistemic integrity**

Lifecycle append failures and STRATUM ratification-record failures may be caught and surfaced as warnings while execution proceeds. That violates the stated rule that auto-ratification relocates only the pause, never the evidence emission.

Required closure: evidence required to classify an operation as governed must fail closed or leave an explicit failed/incomplete state; it may not silently downgrade to a warning.

### B0-04 — CLI/TUI ratification evidence is not yet one canonical ceremony

Severity: **P0 / governance equivalence**

STRATUM resolves/records dispatch ratification, then launches `run-governed`; direct CLI invocation does not consume the same dispatch ceremony, and the ordinary Goose launch receipt does not yet bind the ratification point/grant decision in the planned traceable shape.

Required closure: one non-TUI dispatch-plan/authorization service consumed by both CLI and STRATUM.

### B0-05 — Run-bound artifacts still have collision/overwrite hazards

Severity: **P1 / evidence identity**

Observed examples include stable task-manifest naming, timestamp-derived session identity, `_live_runs` keyed by manifest path, and one patch-proposal filename per session. A second proposal or concurrent run must not replace evidence from the first.

Required closure: collision-resistant run identity and content-/run-addressed artifacts.

### B0-06 — In-loop proposal event does not yet bind the proposal strongly enough

Severity: **P0 / traceability**

The branch successfully turns a refused write into a passive proposal, but the event path must digest-bind that exact proposal artifact and the proposal itself must bind source preimage/origin identity.

Required closure: source-bound, content-addressed proposals referenced from the denial event.

### B0-07 — Cockpit Stage 2 is absent

Severity: **P1 / functional incompleteness**

Deepagents Start/Resume and wrapper Stop from the cockpit remain unbuilt by the frozen branch. The branch's ROADMAP states this explicitly.

Required closure: complete the governed cockpit lifecycle with separate dispatch/process-control authority.

### B0-08 — C3 affordance realization is partial

Severity: **P1 / UX-contract incompleteness**

HITL A/R now directly hand off to governed CLI when the registry allows, but prepare-package and subagent assignment remain compose-only in the inspected branch.

Required closure: the registry-derived affordance controls actual behavior for each named action, with compose/refuse retained where the registry requires it.

### B0-09 — The existing Stage-D scenario is not the complete approved-apply proof

Severity: **P1 / verification incompleteness**

The current scenario proves proposal creation, gate visibility, no mutation, and several refusal paths. It does not yet prove real proposal -> real human approval artifact -> real verification receipt -> successful governed apply -> rollback bundle -> exact rollback restoration.

Required closure: a temporary-repository end-to-end proof using the real governed lanes.

### B0-10 — Operator-facing truth still contains stale pre-dispatch language

Severity: **P1 / truth drift**

Some STRATUM launch/help strings still describe the surface as "observe + compose only" even though `Ctrl+G` dispatch exists.

Required closure: final symmetric sweep across runtime behavior, CLI help, TUI labels, authority records, matrix notes, and docs.

## 5. Phase-0 code/process deliverables

Phase 0 adds three permanent pieces of closure infrastructure:

1. `docs/plan/STRATUM_GOVERNED_CONTROL_PLANE_V1_CLOSURE.md` — governing implementation contract.
2. This baseline audit — immutable starting facts, known findings, and verification provenance.
3. `scripts/verify_stratum_control_plane.sh` — a focused, reproducible high-signal test lane for the existing governed-control-plane substrate.

The focused lane is added to `scripts/ci.sh` as a **blocking** gate and is pinned by `tests/test_ci_gate_parity.py`. It is deliberately redundant with the eventual full pytest run: its purpose is to produce a narrow, immediately meaningful failure surface for this closure program, not to replace repository-wide verification.

## 6. Operator execution runbook

When a suitable development machine is available, run from a clean checkout of the closure branch:

```bash
git status --short
git rev-parse HEAD
uv sync --all-groups

# High-signal closure lane
bash scripts/verify_stratum_control_plane.sh

# Truth surfaces
uv run builder-platform audit-docs
uv run builder-platform matrix

# Canonical complete battery + receipt
bash scripts/ci.sh --receipt .builder/artifacts/gate-battery-receipt.json
```

Record at minimum:

```text
Host / architecture:
OS:
Python:
uv:
Goose version (if installed):
Goose `run --help` digest (if applicable):
Closure branch HEAD:
Working tree clean before run: yes/no
Focused lane: pass/fail
Audit-docs: pass/fail
Matrix validation: pass/fail
Full blocking battery: pass/fail
Gate-battery receipt path/digest:
```

If the battery is red, classify every failure before changing code:

| Class | Meaning | Action |
|---|---|---|
| closure regression | caused by Claude/closure changes | repair before next capability phase |
| pre-existing deterministic debt | also reproducible on audited `main` | repair or explicitly isolate through an honest, reviewed baseline fix; never normalize |
| environment/provisioning failure | toolchain/dependency/host issue | repair provisioning; do not weaken a gate |
| flaky/order-sensitive | nondeterministic test/system behavior | reproduce with seed, fix determinism/root cause |
| stale test invariant | test pins a behavior that is intentionally obsolete | rewrite to the underlying invariant in the same change, never merely delete the assertion |

No broad skip/xfail, `|| true`, `continue-on-error`, or selective CI tier is an acceptable baseline repair.

## 7. Phase-0 exit gate

Phase 0 is structurally implemented when the plan, audit, blocking focused lane, parity pin, closure branch, and draft PR exist.

Phase 0 is **verified closed** only after operator/CI execution establishes:

- focused closure lane passes;
- docs truth audit passes;
- completion matrix validation passes;
- complete `scripts/ci.sh` passes with no unexplained/skipped CI gate;
- gate-battery receipt is produced from the exact closure head;
- every discovered failure has a classified disposition.

Until those execution results exist, the phase status remains:

> **IMPLEMENTED / VERIFICATION PENDING — no capability promotion.**

## 8. Baseline principle

This audit exists so later phases cannot rewrite history by saying "the system was already basically green" or "that failure was inherited." The closure begins from an explicit measured boundary: substantial architecture is present, several important invariants are not yet closed, and the complete test battery has not yet been independently proven green. Every later claim must become stronger because evidence became stronger, not because wording became more optimistic.
