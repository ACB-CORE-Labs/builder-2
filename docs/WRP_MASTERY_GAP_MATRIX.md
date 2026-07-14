# WRP Absolute Mastery — Gap Matrix

**Status:** RECORDED_ONLY gap ledger (not a promotion grant).  
**Sources:** CORE R&D Blueprint; Multi-Platform Master-Plan.  
**Current capability (truth):** recommendation/validation/HITL candidates — **not** S3 enabled multi-agent. P6 = opt-in substrate; S4 promo OPEN.

**Progress marker:** [`docs/WRP_MASTERY_PROGRESS.md`](WRP_MASTERY_PROGRESS.md).

### Pipeline cursor

```text
[x] P0–P5  [x] S1/S2 decided  [x] S3 readiness + HUMAN blocked
[x] P6 backends  [x] P7 W5 + ceremony template
[x] Post-P6 PARTIAL harden (adaptivity, handoff measure, fleet annotate, agent plan CLI)
[ ] S4 backend promotion decisions  [ ] cloud invoke  [ ] trained R head research
```

## Legend

| Status | Meaning |
| --- | --- |
| `LANDED` | Implemented at honest current power |
| `PARTIAL` | Exists but incomplete fidelity |
| `OPEN` | Not done |
| `DEFERRED` | Named research track |

## Gap rows

| Source requirement | Status | Mastery phase | Evidence |
| --- | --- | --- | --- |
| Spaces typed + digest artifacts + CLI | `LANDED` | — | `tests/test_wrp_*` |
| Dual-platform exchange / ceremony | `LANDED` | P7 | template + packages; G-LEAD optional this phase |
| S1 bind + S2 live + S2 v2 gateways | `LANDED` | S1/S2 | decisions on main |
| S3 enablement | `PARTIAL` | S3 | HUMAN **blocked** (#147) |
| WorkloadClassifier + embed wire | `LANDED` | P2/P6 | hash default; modernbert fail-closed |
| Collaboration handoff zero-loss + &lt;50ms local | `LANDED` | P2.1 | `measure_handoff_overhead` + `builder-wrp handoff-measure` (local pure scope) |
| Fleet allocation ±10% | `LANDED` | P2.2 | stress tests |
| Fleet binding drives plan annotation | `LANDED` | P2.2 | `selected_alias` → record-mode `model_gateway` payload; **not** provider authority |
| MSDA gates + OPA | `LANDED` | P2.3/P6 | pure + optional opa |
| MSDA preflight before all invokes | `PARTIAL` | P2.3 | live/gateway nodes forced; global env default off (`msda-status`); no soft default-on |
| Experience + receipt ingest + R* apply | `LANDED` | P4 | HITL φ policy |
| AgentFactory plan only | `LANDED` | P2.5 | `plan_agent_lifecycle` + CLI; `spawn_permitted=false` |
| SubtaskGraph + W5 repo-state replay | `LANDED` | P7 | commit_id/tree_hash |
| Orchestration patterns runtime | `PARTIAL` | P2.6 | patterns + S2 v2 gateways; cloud invoke OPEN |
| Class U measured + adaptivity axis | `LANDED` | P5/H11 | `axes.adaptivity` via `simulate_receipt_epochs` |
| Perf dashboards full | `PARTIAL` | P5 | axes filled; no product dashboard UI |
| vLLM / LangGraph / ModernBERT opt-in | `LANDED` | P6 | #148 |
| Backend registry + doctor inventory | `LANDED` | P6.1 | `backend_registry.py` + `builder-wrp backends` / `doctor-backends` (this PR) |
| Trained R head | `DEFERRED` | P6 | research track doc |
| Cloud provider model invoke | `OPEN` | S2+/S4 | record/stub only (H6) |
| S4 backend promotion decisions | `OPEN` | S4 | readiness not decision |

## Promotion stages

| Stage | Target | State |
| --- | --- | --- |
| S1 | bound recommendations | Approved (flagged) |
| S2 | HITL live | Approved |
| S3 | scoped enabled | **Blocked** |
| S4 | backend promos | OPEN |

## Mastery checklist

```text
[~] W0–W5 green with Maker evidence
[~] Live lane under MSDA (HITL; not S3)
[x] R / R* / adaptivity measured
[x] Proof R/D/U with numbers
[~] Ceremony practiced (G-LEAD optional)
[~] Authority docs match code
[x] Heavy backends opt-in M1-safe
[~] Zero OPEN rows (intentional OPEN remain)
```
