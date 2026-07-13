# WRP Absolute Mastery — Gap Matrix

**Status:** RECORDED_ONLY gap ledger (not a promotion grant).  
**Sources:** CORE R&D Blueprint (geometry-first WRP); Multi-Platform Execution Master-Plan (Grok + Antigravity).  
**Charter:** session absolute-mastery plan (supersedes passive-only stop).  
**Current capability (truth):** `artifact_only` / `validation_only` / `recommendation_only` — **not** live-enabled.

Eight gates are **how** stages promote, not reasons to stop. Soft-stop at substrate is **failure**.

## Legend

| Status | Meaning |
| --- | --- |
| `LANDED` | Implemented at honest current power |
| `PARTIAL` | Exists but missing source-doc fidelity or binding |
| `OPEN` | Required for mastery; not done |
| `STAGE` | Unlocked by promotion stage S1–S4 |

## Gap rows

| Source requirement | Status | Mastery phase | Evidence path when closed |
| --- | --- | --- | --- |
| Spaces \(\mathcal{W},\mathcal{A},\mathcal{T},\Gamma\) typed | `LANDED` | — | `tests/test_wrp_spaces.py` |
| Digest-bound artifact kinds + `builder-wrp` | `LANDED` | — | `tests/test_wrp_*.py`, CLI |
| Dual-platform exchange + G0–W5 Governor cert | `LANDED` | P7 ops | `artifacts/wrp_exchange/` |
| Advisory WRP annotation in model_router / dry-run | `PARTIAL` | P1 S1 | Must **bind** as required input, not warn-only |
| Promotion readiness record | `PARTIAL` | P1 | `planning/evidence/wrp.json` — needs **decision** per stage |
| Promotion **decision** S1–S3 | `OPEN` | P1 | readiness + decision + verify evidence + matrix |
| Live lane `run-approved` | `OPEN` | P3 / S2 | `tests/scenarios/test_wrp_live_lane.py` |
| WorkloadClassifier rules + 95% fixtures | `LANDED` | P2.0 deepen | `builder-wrp score-classifier` |
| EmbeddingBackend + kNN (hash default; ModernBERT-class opt-in) | `PARTIAL` | P2.0 / P6 | Module + tests landed; wire into classifier + S4 embedder promo open |
| Collaboration topology + handoff zero-loss + &lt;50ms | `PARTIAL` | P2.1 | Maker/Governor nodes + live handoff |
| Fleet allocation ±10% budget | `LANDED` | P2.2 | Stress tests; must emit **fleet_binding** |
| Fleet binding drives session/model plan | `OPEN` | P1 S1 / P2.2 | consumed by router + live lane |
| MSDA declarative gates logged | `LANDED` | P2.3 | `tests/test_wrp_governance.py` |
| MSDA preflight before tool/model/MCP invoke | `OPEN` | P2.3 / P3 | gateway integration tests |
| OPA export + optional OPA eval parity | `PARTIAL` | P2.3 / P6 | `opa_adapter.py` landed; gateway preflight wire still OPEN |
| ExperienceStore append/freeze | `LANDED` | P2.4 | — |
| Receipt ingest → experience exemplars | `PARTIAL` | P2.4 / P4 | `receipt_ingest.py` landed; real ledger series + R* apply still OPEN |
| \(R^*\) synthetic epochs ≥30% | `LANDED` | P4 | fixture path only today |
| \(R^*\) from **real** receipts + **apply** via promotion | `OPEN` | P4 | receipt_ingest + apply path |
| AgentFactory plan only | `PARTIAL` | P2.5 | spawn/retire under HITL at S2 |
| SubtaskGraph plan + digest replay | `PARTIAL` | P2.6 / P2.8 | graph **runtime** landed (noop/record); live invoke + tree_hash OPEN |
| Orchestration patterns at runtime | `PARTIAL` | P2.6 / P3 | sequential, fan-out, hierarchical, handoff, cyclic in graph_runtime; gateway-backed nodes OPEN |
| Evaluator + proof R/D kinds | `PARTIAL` | P2.7 | Class U harness missing |
| Class U measured latency/cost | `OPEN` | P5 | `class_u_harness.py` + proof_record U |
| Perf axes (accuracy, cost, latency, safety, adaptivity) | `OPEN` | P5 | artifact dashboards |
| vLLM WRP research profile | `OPEN` | P6 | `docs/plan/WRP_VLLM_RESEARCH_PROFILE.md` + interface |
| LangGraph optional adapter | `OPEN` | P2.6 / P6 | adapter + skip-if-missing tests |
| Trained R head research track | `OPEN` | P6 | offline dataset/pipeline; no silent override |
| W5 Gitea/repo state reconstructive match | `OPEN` | P2.8 / P7 | commit_id + tree_hash binding |
| Merge ceremony on every authority PR | `PARTIAL` | P7 | process + templates |
| Scoped `enabled` live path | `OPEN` | P5 / S3 | eight-gate decision only |

## Promotion stages (target power)

| Stage | Target | Unlocks |
| --- | --- | --- |
| **S1** | recommendation_only **bound** | WRP required on routing recommendation / assignment dry-run fields |
| **S2** | HITL live lane | `builder-wrp run-approved` under digest-bound approval |
| **S3** | scoped `enabled` | Default governed multi-agent routing inside declared profiles |
| **S4** | backend promotions | Embedding / OPA / vLLM research each with own decision |

## Mastery checklist (all required)

See absolute mastery plan success definition. **None** of these boxes may be checked by documentation alone.

```text
[ ] Master-Plan W0–W5 green with Maker + Governor evidence
[ ] Live lane promoted and used under MSDA + budgets
[ ] R deterministic; R* applied through promotion; adaptivity measured
[ ] Proof R, D, U evidenced (U with numbers)
[ ] Dual-platform ceremony for authority changes
[ ] CAPABILITY_PROMOTION / matrix / command_authority match real power
[ ] Heavy backends exist as opt-in with tests; defaults M1-safe
[ ] This gap matrix has zero OPEN rows remaining
```
