# Deepagents Policy

## Status

Deepagents integration in builder-II is **optional and governed**.
This document clarifies the distinction between artifact-only policy
surfaces and the bounded approved protocol lane.

---

## Two Distinct Surfaces

### 1. Artifact-only policy surfaces

Passive readiness artifacts, bridge specs, profile rendering, and dry-run
planning outputs are **artifact-only**. They:

- Produce governed JSON/YAML/Markdown artifacts for operator review.
- Do not invoke models, tools, shell commands, or source writes.
- Do not promote capabilities beyond read-only planning.
- Are always safe to emit; they carry no execution authority.

### 2. Bounded approved protocol lane

The approved protocol lane exposes a governed execution path with the
following operations:

| Operation | Description |
|---|---|
| `execution-candidate` | Propose an execution candidate artifact for operator review |
| `approve-candidate` | Operator approves a digest-bound execution candidate |
| `run-approved` | Execute an approved, digest-bound candidate |
| `resume-approved` | Resume an interrupted approved run |
| `replay-run` | Replay a completed run from its event ledger |
| `evidence-bundle` | Collect and seal the evidence bundle for a completed run |

**This lane is NOT native deepagents runtime promotion.** It is a
deterministic, governed protocol backend (`protocol_fake`) that:

- Requires explicit operator approval before any execution step.
- Binds every approval to a content digest of the candidate artifact.
- Emits a full event ledger for every run.
- Supports denial probes and replay from ledger.
- Produces a sealed evidence bundle on completion.
- Does **not** invoke native deepagents construction.
- Does **not** invoke native model execution.
- Does **not** grant direct tool, MCP, shell, or source-write authority.

---

## protocol_fake Backend

`protocol_fake` is the deterministic governed protocol backend for the
approved lane. It is **not** a native deepagents runtime and does **not**
promote native deepagents construction or model invocation.

It is called `protocol_fake` to clearly signal that it is a **governed
proof lane** — a bounded simulation of what a future native deepagents
backend would do — not the real thing.

---

## optional_deepagents Gate

`optional_deepagents` integration remains **gated** by:

1. Backend readiness audit (all readiness checks must pass).
2. Digest-bound approval of the execution candidate.
3. Denial probes confirming the approval boundary holds.
4. Event ledger confirming the run is fully observable.
5. Replay confirming the ledger is sufficient for re-execution.
6. Evidence bundle confirming all artifacts are sealed.

Until all gates pass, `optional_deepagents` remains in artifact-only
mode. Promotion to a live backend requires an explicit capability
promotion record per the builder-II Capability Promotion Rule.

---

## What Remains Disabled

The following capabilities are **disabled** and require explicit
capability promotion before they can be enabled:

- Native deepagents construction.
- Native model invocation.
- Direct tool/MCP execution authority.
- Shell execution as agent authority.
- Autonomous source writes.

---

## Summary

| Surface | Execution authority | Model invocation | Shell | Source write |
|---|---|---|---|---|
| Artifact-only policy | ❌ None | ❌ None | ❌ None | ❌ None |
| Approved protocol lane (`protocol_fake`) | ✅ Governed, digest-bound | ❌ None | ❌ None | ❌ None |
| Native deepagents (disabled) | — | — | — | — |

Governance is not weakened by this clarification — it is made explicit.
