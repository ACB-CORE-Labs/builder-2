# Deepagents Runtime Harness

## Capability State
Capability state: `OPERATIONALLY_VERIFIED` (Assurance: `BOUNDED_EXECUTION_VERIFIED` over `protocol_fake`)

---

## 1. Verified Runtime Trunk

The verified runtime trunk for deepagents is:
$$\text{execution-candidate} \longrightarrow \text{approve-candidate} \longrightarrow \text{run-approved} \longrightarrow \text{replay-run} \longrightarrow \text{collect-results}$$

- **Execution Candidate:** Emitted as a digest-bound execution plan (`builder-deepagents execution-candidate`).
- **Approval Candidate:** Sealed with a flag-driven, digest-bound operator approval (`builder-deepagents approve-candidate`).
- **Run Approved:** Executed over the deterministic `protocol_fake` backend (`builder-deepagents run-approved`), producing execution receipts and appending to the tamper-evident event chain.
- **Proposal-Only Results:** All subagent emissions remain proposal-only artifacts.

*Note on legacy command:* `builder-deepagents run-plan` is a legacy structural projection, not the runtime trunk: it runs no backend, executes no tools, and produces no execution evidence.

---

## 2. Required Negative Space Guardrails

- **No autonomous writes:** Modifying target code requires the separate HITL patch application lane.
- **No unconstrained shell execution:** Shell execution is denied inside the subagent envelope.
- **No unrouted model execution:** Model calls must cross the governed `ModelExecutionGateway`.
- **No ambient MCP or Goose activation:** Subagents cannot invoke MCP tools or start Goose sessions without explicit delegation tickets.
- **Native Backend Status:** The native `optional_deepagents` backend remains unpromoted behind the backend readiness gate and two-key acknowledgment.

---

## 3. The Eight Promotion Gates

1. **Docs:** This specification and [`docs/DEEPAGENTS_POLICY.md`](DEEPAGENTS_POLICY.md) define the formal boundary.
2. **Tests:** Validated via `tests/test_deepagents_runtime.py`, `tests/test_deepagents_execution.py`, and scenario tests.
3. **Command Surface:** Managed through `builder-deepagents execution-candidate`, `approve-candidate`, `run-approved`, `replay-run`, and `collect-results`.
4. **Failure Mode:** Fails closed if an unapproved capability is requested. Exceptions halt the harness cleanly without state mutation.
5. **Human Approval Boundary:** Requires an explicit digest-bound candidate approval artifact before `run-approved` spawns work.
6. **Output Artifact:** Emits `builder_ii.deepagents_execution_receipt` and tamper-evident event ledger records.
7. **Rollback Path:** Non-mutating execution; rollback consists of archiving emitted proposal and receipt JSON files.
8. **Verification Path:** Verified via `builder-deepagents replay-run` confirming deterministic re-execution of the event chain.

