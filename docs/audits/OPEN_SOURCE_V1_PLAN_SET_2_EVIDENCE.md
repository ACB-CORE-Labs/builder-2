# Open-source v1 Plan Set 2 evidence

Status: implementation and local-verification record only. This document is not
approval, authority, release promotion, or authorization for Plan Sets 3–7.

## Authority binding

- Canonical plan: `docs/plan/OPEN_SOURCE_V1_COMPLETION_PLAN.md`
- Approved plan digest:
  `28bf3978504c361fbfaa3df9a67b2702409de5184cecea346d7b35d226ee68e5`
- Scope: Plan Set 2 native Deep Agents integration and its callers, tests,
  documentation, artifact validation, and evidence surfaces.

## Implemented seam

- Optional dependency: `deepagents>=0.6.12,<0.7.0`; no Deep Agents, LangChain, or
  LangGraph import is required by the governance-only artifact validators.
- Official factory: `deepagents.create_deep_agent`; custom expected factory and
  runner exports are no longer the readiness contract.
- Model path: one shared LangChain adapter backed by `ModelExecutionGateway`, with
  existing envelope and receipt artifacts.
- Tool path: upstream `task` plus Builder-governed tools only; native filesystem,
  shell, Git, direct-provider, and target-repository mutation are denied.
- Delegation: each upstream subagent definition is generated from one validated WRP
  obligation and inherits its parent, budget, boundary, output, and file-ref fields.
- Persistence: upstream checkpoint state, pending writes, and channel blobs survive
  reconstruction through a digest-bound store; tampering fails closed.
- Middleware: cumulative model/tool budgets, two-worker default, four-worker hard
  cap, admission, receipts, interruption, cancellation, and hash-linked events.
- Caller: existing `execution-candidate -> approve-candidate -> run-approved ->
  resume-approved` chain, with the native readiness gate, two-key acknowledgement,
  original obligation paths, and exact checkpoint-digest resume.
- Evidence: native event/checkpoint/evidence kinds and the model/tool artifacts they
  reference are recognized by both artifact indexing and chain verification.

## Native exit scenario

`tests/test_native_deepagents_runtime.py` executes the official upstream graph and
establishes the bounded structural claim:

1. Two distinct WRP obligations are delegated through two upstream `task` calls.
2. Parent and children share one Builder-II gateway-backed model instance.
3. Model calls emit governed model receipts and the executable proof tool emits the
   existing policy/envelope/receipt chain.
4. The graph pauses at the required HITL tool.
5. A new runtime object restores persisted graph state from disk.
6. Resume succeeds only with the exact checkpoint-store digest.
7. Completed evidence closes both parent/child links and indexes with zero unknown or
   invalid artifacts.
8. Checkpoint tampering, worker-cap violations, budget reset, and persisted
   cancellation fail closed.

The gateway response strategy is deterministic test control. It proves adapter and
governance behavior, not model quality or live-provider quality.

## Local verification

The repository-authoritative local gate was run with:

```bash
bash scripts/ci.sh
```

Observed result before this evidence note was added:

- Rust validator build: passed.
- Python compile: passed.
- Documentation truth audit and completion matrix: passed.
- High-confidence secret scan: passed.
- Ruff, targeted mypy, TUI mypy, and Bandit: passed.
- Full pytest suite: `2725 passed, 2 skipped`.
- Gate summary: `ALL BLOCKING GATES PASSED (no skips).`

The same gate must pass again on the exact final working tree before delivery; the
delivery report is authoritative for that final rerun.

## Non-claims

- No Plan Set 3–7 implementation or authority.
- No Goose or MCP runtime promotion.
- No autonomous source, shell, Git, delivery, or target-repository mutation.
- No claim that model/subagent output is correct or verified.
- No GitHub workflow/check dependency; the merge gate is local.
