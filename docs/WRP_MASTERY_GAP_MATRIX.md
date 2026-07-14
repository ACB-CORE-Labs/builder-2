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
[x] S4 readiness drafts (W.6)  [~] S4 HUMAN review packages ready  [ ] S4 HUMAN promo decisions  [ ] cloud invoke  [ ] trained R head research
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
| Fleet binding drives plan annotation | `LANDED` | P2.2 / W.3 | annotation + `check_fleet_plan_fidelity` / `builder-wrp fleet-fidelity`; **not** provider session authority |
| Agent RO runner candidate | `LANDED` | V.2 | `builder-agent run --read-only` + `builder-deepagents run-readonly`; `read_only_runtime_candidate`; no delegate |
| MSDA gates + OPA | `LANDED` | P2.3/P6 | pure + optional opa |
| MSDA preflight before all invokes | `PARTIAL` | P2.3 / W.2 | Option A policy: live/gateway nodes forced; env default off; tool/model receipts annotate `skipped_default_off`; no soft default-on (`docs/plan/WRP_MSDA_PREFLIGHT_POLICY.md`) |
| Semantic/structural RO doctor/map/preview | `LANDED` | V.1 | `builder-semantic` + `semantic_readonly.py` (repo_map based; serena/ast-grep detect-only; no rewrite) |
| Experience + receipt ingest + R* apply | `LANDED` | P4 | HITL φ policy |
| AgentFactory plan only | `LANDED` | P2.5 | `plan_agent_lifecycle` + CLI; `spawn_permitted=false` |
| AgentFactory spawn/retire language | `LANDED` | W.5 | `spawn_agent`/`retire_agent`/`prove_agent_lifecycle` + `builder-wrp agent-factory`; lifecycle *records* only (`spawn_executed=false`, UNBOUND); ExperienceStore digest bind; not S3 process spawn |
| SubtaskGraph + W5 repo-state replay | `LANDED` | P7 | commit_id/tree_hash |
| Orchestration patterns runtime | `LANDED` | P2.6 / W.4 | pure `patterns-prove` + graph_runtime; S2 v2 gateways separate; cloud invoke OPEN |
| HITL verify fixed-argv expansion (V.3) | `LANDED` | V.3 | wrp_doctor/patterns/fleet + semantic_doctor/map in SUPPORTED_COMMAND_PROFILES (not TARGET_CODE) |
| CORE target profile isolation | `LANDED` | V.4 | `builder_ii/targets/core.py` invariants + verification routing + path categories + semgrep *catalog*; `builder-targets show/doctor core`; no Workbench coupling |
| CORE Workbench boundary doc | `LANDED` | V.5 | `docs/plan/CORE_WORKBENCH_BOUNDARY.md` — builder-II helps Workbench *code* as target work; is not Workbench; adapter requirements design-only; `core_workbench_coupling` remains NONE |
| Class U measured + adaptivity axis | `LANDED` | P5/H11 | `axes.adaptivity` via `simulate_receipt_epochs` |
| Perf dashboards full | `PARTIAL` | P5 | axes filled; no product dashboard UI |
| vLLM / LangGraph / ModernBERT opt-in | `LANDED` | P6 | #148 |
| Backend registry + doctor inventory | `LANDED` | P6.1 | `backend_registry.py` + `builder-wrp backends` / `doctor-backends` (this PR) |
| Trained R head | `DEFERRED` | P6 | research track doc |
| Cloud provider model invoke | `OPEN` | S2+/S4 | record/stub only (H6) |
| S4 backend promotion decisions | `PARTIAL` | S4 / W.6 | readiness+decision *drafts* + HUMAN review handoff (`planning/evidence/s4_review_summary.md`, `wrp_s4_human_review_handoff.json`, exchange `mastery/S4-readiness/`); **HUMAN decides each**; still `s4_promoted=false`; no promo flip |

## Promotion stages

| Stage | Target | State |
| --- | --- | --- |
| S1 | bound recommendations | Approved (flagged) |
| S2 | HITL live | Approved |
| S3 | scoped enabled | **Blocked** |
| S4 | backend promos | OPEN (drafts + HUMAN handoff ready; no HUMAN approve yet) |

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
