# WRP Absolute Mastery — Gap Matrix

**Status:** RECORDED_ONLY gap ledger (not a promotion grant).  
**Sources:** CORE R&D Blueprint (geometry-first WRP); Multi-Platform Execution Master-Plan (Grok + Antigravity).  
**Charter:** session absolute-mastery plan (supersedes passive-only stop).  
**Current capability (truth):** `artifact_only` / `validation_only` / `recommendation_only` + S2/P4 **HITL candidates** — **not** S3 live-enabled multi-agent.

**Progress marker (living cursor):** [`docs/WRP_MASTERY_PROGRESS.md`](WRP_MASTERY_PROGRESS.md) — what is DONE, where we stand after #144, hiccups/concerns.

Eight gates are **how** stages promote, not reasons to stop. Soft-stop at substrate is **failure**.

### Pipeline cursor (summary)

```text
[x] P0  [x] P2 pure/wires  [x] S1 decided  [x] S2 v1 decided  [x] S2 v2 code
[x] P4 R* apply  [x] P5 Class U numbers
[~] S3 readiness drafted (decision blocked)  [ ] P6 backends (heavy)  [ ] P7 W5 repo-state / full ceremony
```

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
| Advisory WRP annotation in model_router / dry-run | `LANDED` | P1 S1 | **S1 decided (approved on main):** bind when `require_wrp_binding` / `BUILDER_II_WRP_BIND` / dry-run `require_wrp`; default still advisory |
| Promotion readiness record | `LANDED` | P1 | `planning/evidence/wrp_s1_readiness.json` ready on main |
| Promotion **decision** S1–S3 | `PARTIAL` | P1 | **S1+S2 approved**; S3 readiness recorded + decision **blocked** PENDING_HUMAN (`planning/evidence/wrp_s3_{readiness,decision}.json`) — not enabled |
| Live lane `run-approved` | `LANDED` | P3 / S2 | **S2 decided approved**: HITL v1 + **v2 gateway nodes** (#143) on main; forced MSDA; not S3 |
| WorkloadClassifier rules + 95% fixtures | `LANDED` | P2.0 deepen | `builder-wrp score-classifier` |
| EmbeddingBackend + kNN (hash default; ModernBERT-class opt-in) | `PARTIAL` | P2.0 / P6 | Module + tests landed; wire into classifier + S4 embedder promo open |
| Collaboration topology + handoff zero-loss + &lt;50ms | `PARTIAL` | P2.1 | Maker/Governor nodes + live handoff |
| Fleet allocation ±10% budget | `LANDED` | P2.2 | Stress tests; must emit **fleet_binding** |
| Fleet binding drives session/model plan | `PARTIAL` | P2.2 | `fleet_binding` on allocation + routing recommendation + S2 plan fields; does not alone authorize session/model execution |
| MSDA declarative gates logged | `LANDED` | P2.3 | `tests/test_wrp_governance.py` |
| MSDA preflight before tool/model/MCP invoke | `PARTIAL` | P2.3 / P3 | `msda_preflight` + gateway hooks when `BUILDER_II_WRP_MSDA_PREFLIGHT=1`; default off |
| OPA export + optional OPA eval parity | `PARTIAL` | P2.3 / P6 | `opa_adapter.py` landed; preflight uses pure MSDA |
| Classifier ↔ EmbeddingBackend wire | `PARTIAL` | P2.0 | `use_embedding` / `BUILDER_II_WRP_EMBED`; HashingEmbedder+kNN; default metric path |
| ExperienceStore append/freeze | `LANDED` | P2.4 | — |
| Receipt ingest → experience exemplars | `LANDED` | P2.4 / P4 | `receipt_ingest.py` + `corrections_from_receipts` / CLI |
| \(R^*\) synthetic epochs ≥30% | `LANDED` | P4 | fixture path (`simulate-epochs`) |
| \(R^*\) from **real** receipts + **apply** via promotion | `LANDED` | P4 | real-receipt epochs + HITL `plan-rstar-apply` → `approve-rstar-apply` → `apply-rstar-approved` → versioned `phi_policy`; explicit classifier bind only |
| AgentFactory plan only | `PARTIAL` | P2.5 | spawn/retire under HITL at S2 |
| SubtaskGraph plan + digest replay | `PARTIAL` | P2.6 / P2.8 | graph **runtime** landed (noop/record); live invoke + tree_hash OPEN |
| Orchestration patterns at runtime | `PARTIAL` | P2.6 / P3 | sequential, fan-out, hierarchical, handoff, cyclic in graph_runtime; **S2 v2** model/tool gateway nodes (record/stub) landed; cloud provider invoke still OPEN |
| Evaluator + proof R/D kinds | `LANDED` | P2.7 / P5 | R/D via fixtures; Class U via `class_u_harness` |
| Class U measured latency/cost | `LANDED` | P5 | `class_u_harness.py` + `builder-wrp benchmark --class u` + proof_record U + performance_measurement rows |
| Perf axes (accuracy, cost, latency, safety, adaptivity) | `PARTIAL` | P5 | axes on class_u_report; adaptivity still P4 epoch path (not full dashboards) |
| vLLM WRP research profile | `OPEN` | P6 | `docs/plan/WRP_VLLM_RESEARCH_PROFILE.md` + interface |
| LangGraph optional adapter | `OPEN` | P2.6 / P6 | adapter + skip-if-missing tests |
| Trained R head research track | `OPEN` | P6 | offline dataset/pipeline; no silent override |
| W5 Gitea/repo state reconstructive match | `OPEN` | P2.8 / P7 | commit_id + tree_hash binding |
| Merge ceremony on every authority PR | `PARTIAL` | P7 | process + templates |
| Scoped `enabled` live path | `PARTIAL` | S3 (after P5) | Readiness draft + decision **blocked** (H7: Class U micro-only); G-LEAD/HUMAN ceremony still required before any enablement code |

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
[~] Master-Plan W0–W5 green with Maker + Governor evidence   (W5 repo-state still OPEN)
[~] Live lane promoted and used under MSDA + budgets         (S2 HITL decided; not S3 enabled)
[x] R deterministic; R* applied through promotion (HITL φ-policy); adaptivity measured on receipt epochs
[x] Proof R, D, U evidenced (U with numbers via class_u_harness #144)
[~] Dual-platform ceremony for authority changes             (S2/S2-v2/P5 strong; P4 exchange cert thin)
[~] CAPABILITY_PROMOTION / matrix / command_authority match  (WRP updated; watch drift on each PR)
[~] Heavy backends exist as opt-in with tests; defaults M1-safe (hash embed/OPA partial; vLLM/LangGraph OPEN)
[ ] This gap matrix has zero OPEN rows remaining
```

See [`WRP_MASTERY_PROGRESS.md`](WRP_MASTERY_PROGRESS.md) §5 for hiccups H1–H12.
