# builder-II Last Mile — Master Checklist

**Status:** COMPLETE for battle-plan implementable scope (absolute non-done reasons only).  
**Doctrine:** Planned ≠ executed ≠ verified ≠ promoted.

Legend: `DONE` · `ALREADY FULLY COMPLETED` · `REMOVED FROM DESIGN`

Last updated: 2026-07-19 (remainder wave)

---

## Preconditions

| ID | Item | Status | Notes |
| --- | --- | --- | --- |
| P0 | Sync worktree to `origin/main` | DONE | Base for remainder branch |
| P1 | Feature branch | DONE | `feat/last-mile-remainder` |
| P2 | Local CI battery | DONE | `bash scripts/ci.sh` on tip |

---

## Wave 0 — Foundations

| ID | Item | Status | Evidence |
| --- | --- | --- | --- |
| W0.1 | Real token accounting + price book | DONE | `price_book.py`, `token_accounting.py`, gateway cost_report |
| W0.2 | Unified runtime event ledger spine | DONE | `runtime_event_append.py`, chain integrity |
| W0.3 | Server-side green gate (in-repo) | DONE | `scripts/ci.sh` + `.github/workflows/ci.yml` + gate battery receipt; local-first authority (Forgejo runner enable is ops applying *existing* workflow — not missing code) |

---

## Wave 1 — Governed Execution Seam

| ID | Item | Status | Evidence |
| --- | --- | --- | --- |
| W1.1 | Model budget deny/debit | DONE | Durable debit + integrity tests |
| W1.2 | SEAM invoke_local | DONE | `gateway_nodes.py`, seam tests |
| W1.3 | Cost-aware routing | DONE | cheapest-capable + savings metric |

---

## Wave 2 — Cloud & variety

| ID | Item | Status | Evidence |
| --- | --- | --- | --- |
| W2.1 | Real cloud adapters | DONE | `builder_ii/cloud_chat.py`; OpenAI-compatible + stub; token-ref egress |
| W2.2 | invoke_cloud | DONE | In `GATEWAY_MODES`; hard gates; ADR `docs/adr/0001-invoke-cloud-seam.md` |

---

## Wave 3 — Subagent orchestration

| ID | Item | Status | Evidence |
| --- | --- | --- | --- |
| W3.1 | Governed subagent executor | DONE | Multi-step loop + kill-switch + budget inherit; `spawn_executed` earned only under gates (`subagent_executor.py`) |
| W3.2 | Production-shaped Class U + S3 ceremony path | DONE | `production_shaped_multi_agent` scenario; `s3_enablement.py` session-scoped decision (global default stays false by design) |
| W3.3 | LangGraph → WRP seam compile | DONE | `compile_projection_to_wrp_seam_plan`; opt-in compile remains fail-closed |

---

## Wave 4 — Runtime loop tail

| ID | Item | Status | Notes |
| --- | --- | --- | --- |
| W4.1 | Goose readonly | ALREADY FULLY COMPLETED | CAPABILITY_PROMOTION / matrix OV path |
| W4.2 | HITL patch apply | ALREADY FULLY COMPLETED | OPERATIONALLY_VERIFIED lane |
| W4.X | Arbitrary HITL command exec | REMOVED FROM DESIGN | MASTERPIECE_PLAN permanent non-goal; `RunCommandDisabledError` |

---

## Wave 5 — Replay / observability / release

| ID | Item | Status | Evidence |
| --- | --- | --- | --- |
| W5.1 | Run manifests + replay harness | DONE | `run_manifest.py` + `replay_harness.py` |
| W5.2 | OpenTelemetry export | DONE | `otel_ledger_export.py` (OTLP JSON from ledger) |
| W5.3 | Secret-boundary hardening | DONE | `secret_redaction.py`; receipt redaction before digest |
| W5.4 | E2E demos / release checklist | DONE | `docs/LAST_MILE_RELEASE_CHECKLIST.md`, `scripts/last_mile_demo.sh` |

---

## Continuous / process

| ID | Item | Status | Notes |
| --- | --- | --- | --- |
| C1 | One-writer discipline | DONE | |
| C2 | TDD | DONE | Tests per wave outcome |
| C3 | Local CI | DONE | Full battery on ship tip |
| C4 | Permanent non-goals pinned | DONE | `tests/test_last_mile_non_goals.py` |
| C5 | audit-docs | DONE | |
| C6–C8 | Push/PR/merge feature #177 | DONE | Prior ship |
| C9 | Remainder PR | DONE | feat/last-mile-remainder |

---

## Session log

| When | Change |
| --- | --- |
| 2026-07-18 | Checklist created |
| 2026-07-19 | W0.1–W1.3 + partials shipped (#177) |
| 2026-07-19 | Remainder: W2–W5 + W3 full + W0.3 honesty; no DEFERRED finish-line |
