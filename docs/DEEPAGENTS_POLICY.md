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

### 2. Bounded approved execution lane

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

The lane has two explicit backends:

- `protocol_fake`, retained only as a deterministic structural test double; and
- `optional_deepagents`, the official `create_deep_agent` integration.

Both require explicit operator approval before execution. The native backend additionally requires a passing readiness gate, sealed WRP obligations, model registry/policy bindings, and `--native-backend-acknowledged`. It:

- Requires explicit operator approval before any execution step.
- Binds every approval to a content digest of the candidate artifact.
- Emits a full event ledger for every run.
- Supports denial probes and replay from ledger.
- Produces a sealed evidence bundle on completion.
- constructs only through `deepagents.create_deep_agent`;
- routes every model call through `ModelExecutionGateway` and records receipts;
- admits only Builder-governed tools and records their policy/envelope/receipt chain;
- denies native filesystem, shell, Git, direct-provider, and target-repository write authority; and
- requires digest-bound persisted state for HITL resume.

---

## protocol_fake Backend

`protocol_fake` is the deterministic governed protocol backend for the
approved lane. It is **not** a native deepagents runtime and does **not**
promote native deepagents construction or model invocation.

It is called `protocol_fake` to clearly signal that it is a governed structural proof lane, not native-runtime evidence. Its results may not be cited as proof that `create_deep_agent` ran.

---

## optional_deepagents Gate

`optional_deepagents` integration remains **gated** by:

1. Backend readiness audit (all readiness checks must pass).
2. Digest-bound approval of the execution candidate.
3. Denial probes confirming the approval boundary holds.
4. Event ledger confirming the run is fully observable.
5. Replay confirming the ledger is sufficient for re-execution.
6. Evidence bundle confirming all artifacts are sealed.

`optional_deepagents` runs only after all gates pass for the exact candidate. A passing readiness artifact alone constructs nothing and grants no authority.

---

## What Remains Disabled

The following capabilities are **disabled** and require explicit
capability promotion before they can be enabled:

- Ambient or unapproved native deepagents construction.
- Direct model-provider invocation outside `ModelExecutionGateway`.
- Direct tool/MCP execution authority.
- Shell execution as agent authority.
- Autonomous source writes.

---

## Summary

| Surface | Execution authority | Model invocation | Shell | Source write |
|---|---|---|---|---|
| Artifact-only policy | ❌ None | ❌ None | ❌ None | ❌ None |
| Approved protocol lane (`protocol_fake`) | ✅ Governed, digest-bound | ❌ None | ❌ None | ❌ None |
| Native Deep Agents (`optional_deepagents`) | ✅ Digest-bound and two-key gated | ✅ Through `ModelExecutionGateway` only | ❌ None | ❌ None |

Governance is not weakened by this clarification — it is made explicit.
