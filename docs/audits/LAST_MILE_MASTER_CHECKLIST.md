# builder-II Last Mile — Master Checklist

**Status:** ACTIVE tracking ledger (not a promotion grant).  
**Plan:** goal plan + session battle-plan.  
**Doctrine:** Planned ≠ executed ≠ verified ≠ promoted.

Legend: `PENDING` · `IN_PROGRESS` · `DONE` · `DEFERRED` · `BLOCKED` · `N/A (already green)`

Last updated: 2026-07-19 (implementation wave)

---

## Preconditions

| ID | Item | Status | Notes |
| --- | --- | --- | --- |
| P0 | Sync worktree to `origin/main` | DONE | Fast-forward to cbf7879 (#176) |
| P1 | Feature branch from main | DONE | `feat/last-mile-w0.1-price-book-tokens` |
| P2 | Local CI battery green | DONE | `bash scripts/ci.sh --receipt` → PASSED; 2452 passed |

---

## Wave 0 — Foundations

| ID | Item | Status | Evidence |
| --- | --- | --- | --- |
| W0.1 | Real token accounting + price book | DONE | `builder_ii/price_book.py`, `token_accounting.py`, gateway cost_report |
| W0.1.a–f | Artifact/CLI/tests/docs | DONE | `tests/test_price_book.py`, `tests/test_gateway_measured_cost.py`, `docs/MODEL_COSTING.md` |
| W0.2 | Unified runtime event ledger spine | DONE | `runtime_event_append.py`, `validate_event_chain_integrity`, gateway ledger_bound path |
| W0.2.* | Chain integrity + gateway non-CLI append | DONE | `tests/test_runtime_event_ledger_spine.py` |
| W0.3 | Receipt-backed merge honesty | DONE (docs) / BLOCKED (admin runner) | `gate_battery_receipt.py` docstring, `BRANCH_PROTECTION_REQUIRED.md` Forgejo section; remote runner still human-admin |

---

## Wave 1 — Governed Execution Seam

| ID | Item | Status | Evidence |
| --- | --- | --- | --- |
| W1.1 | Model budget deny/debit | DONE | Durable debit + 3-tuple return; `tests/test_model_budget.py`, `tests/test_budget_debit_integrity.py` |
| W1.2 | **SEAM invoke_local** | DONE | `gateway_nodes.py` mode, live_lane flags, `tests/test_wrp_invoke_local_seam.py` |
| W1.3 | Cost-aware routing | DONE | `model_routing_policy.py` cheapest-capable + savings metric; still RECOMMENDATION_ONLY |

---

## Wave 2 — Cloud & variety

| ID | Item | Status | Notes |
| --- | --- | --- | --- |
| W2.1 | Real cloud adapters | DEFERRED | Registry/health present; live cloud needs secrets + per-provider promotion PRs; CI stays stub-only |
| W2.2 | `invoke_cloud` | DEFERRED | Explicitly **not** in `GATEWAY_MODES`; H6 honesty; needs ADR + HUMAN ceremony |

---

## Wave 3 — Subagent orchestration

| ID | Item | Status | Notes |
| --- | --- | --- | --- |
| W3.1 | Governed subagent step via seam | DONE (partial) | `wrp/subagent_executor.py`; `spawn_executed` remains false by design |
| W3.1 full spawn_executed flip | DEFERRED | Schema versioning + HUMAN ceremony required |
| W3.2 | Production Class U → S3 | DEFERRED | HUMAN blocked; needs production-shaped harness on real repos |
| W3.3 | LangGraph harness | DEFERRED | S4-blocked; opt-in only |

---

## Wave 4 — Runtime loop tail

| ID | Item | Status | Notes |
| --- | --- | --- | --- |
| W4.1 | Goose readonly | N/A (already OV) | Polish not required for acceptance |
| W4.2 | HITL patch | N/A (already OV) | |
| W4.X | Arbitrary HITL command exec | N/A (permanent non-goal) | `tests/test_last_mile_non_goals.py` |

---

## Wave 5 — Replay / observability / release

| ID | Item | Status | Notes |
| --- | --- | --- | --- |
| W5.1 | Run manifests | DONE | `builder_ii/run_manifest.py`, `tests/test_run_manifest.py` |
| W5.2 | OpenTelemetry export | DEFERRED | Optional; not required for seam honesty |
| W5.3 | Secret redaction expansion | DEFERRED | Prompt scan already present; full ledger redaction follow-up |
| W5.4 | E2E demos / release checklist | DEFERRED | Operator playbooks exist; formal release package later |

---

## Continuous / process

| ID | Item | Status | Notes |
| --- | --- | --- | --- |
| C1 | One-writer discipline | DONE | Contended surfaces updated carefully |
| C2 | TDD | DONE | Tests for each wave outcome |
| C3 | `bash scripts/ci.sh` | DONE | PASSED + receipt |
| C4 | Permanent non-goals pinned | DONE | `tests/test_last_mile_non_goals.py` |
| C5 | audit-docs | DONE | valid, 0 violations |

---

## Session log

| When | Change |
| --- | --- |
| 2026-07-18 | Checklist created |
| 2026-07-19 | W0.1–W1.3 + W3.1 partial + W5.1 landed; CI green; cloud/S3/OTel deferred honestly |
