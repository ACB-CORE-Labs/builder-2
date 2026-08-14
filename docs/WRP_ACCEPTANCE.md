# WRP Acceptance Criteria

Mapped from:

1. **Multi-Platform Execution Master-Plan** §5 (W0–W5 high-assurance criteria)
2. **CORE R&D Blueprint** proof classes R/D/U and performance axes
3. Absolute mastery charter (promotion + live enablement required)

Governor certification is required for merge ceremony on authority-changing work; Maker tests alone are not self-certification.

## Current vs mastery

| Layer | Meaning |
| --- | --- |
| **Substrate green** | Fixture/unit acceptance for digest-bound operators (landed for G0–W5 artifact plane) |
| **Mastery green** | Same criteria under **bound recommendations**, **live lane**, **real receipts**, and **repo-state replay** where specified |

Substrate green is **necessary** and **insufficient** for absolute mastery.

## Wave acceptance (Master-Plan §5)

| Wave | Acceptance criterion | Substrate proof (landed) | Mastery proof (required) |
| --- | --- | --- | --- |
| G0 | ADR-0007 + skeleton + kinds + exchange | docs; import tests | ADR staged promotion amendment; gap matrix |
| W0 | Classifier routes ≥95% of samples to correct tier | `builder-wrp score-classifier`; `tests/test_wrp_classifier.py` | Same + embedding/kNN backend path; live classify in lane |
| W1 | Handoffs &lt;50ms overhead; zero state loss | handoff + latency tests | Maker/Governor agent nodes; live handoff scenario |
| W2 | Fleet allocation within 10% token budget under stress | stress fixtures | Fleet **binding** consumed by session/live lane |
| W3 | 100% access requests validated before execution | gate fixtures; decisions logged | MSDA **preflight** on tool/model/MCP; OPA export/parity |
| W4 | Trajectory correction reduces error ≥30% over 5 epochs | `simulate-epochs` fixtures | Real receipt series + **applied** \(R^*\) via promotion |
| W5 | Reconstructive match | planned vs observed WRP digests | Digests **and** bound repo `commit_id` / `tree_hash` |

## Proof classes (Blueprint)

| Class | Criterion | Substrate | Mastery |
| --- | --- | --- | --- |
| **R** Representation integrity | \(\mathcal{W}\) mapping preserves intent axes | space + classifier fixtures | Live lane preserves workload coords on receipts |
| **D** Detection validity | Unauthorized tool/data denied | MSDA deny fixtures | Gateway preflight denies without allow digest |
| **U** Engineering utility | Measurable latency/cost gain vs monolithic | proof_record kind allows U | Class U harness with **numbers** on fixed suite |

## Performance axes (Blueprint)

Recorded as artifacts (not vanity UI):

1. Accuracy — trajectory success rate  
2. Cost efficiency — token reduction vs monolithic  
3. Latency — classify → completion  
4. Safety — MSDA boundary adherence  
5. Adaptivity — \(R^*\) improvement rate on future \(R\)  

## Batch substrate command

```bash
uv run pytest \
  tests/test_wrp_spaces.py \
  tests/test_wrp_classifier.py \
  tests/test_wrp_collaboration.py \
  tests/test_wrp_allocation.py \
  tests/test_wrp_governance.py \
  tests/test_wrp_adjoint.py \
  tests/test_wrp_forward_and_exchange.py \
  tests/test_wrp_cli.py \
  tests/scenarios/test_wrp_full_lane.py -q
```

## Mastery batch (as phases land)

```bash
uv run pytest tests/test_wrp_*.py tests/scenarios/test_wrp_full_lane.py tests/scenarios/test_wrp_live_lane.py -q
bash scripts/ci.sh
uv run builder-platform audit-docs
```

## Governor artifacts (Antigravity)

| Wave / phase | Gemini-3.1-Pro | Gemini-3.5-Flash |
| --- | --- | --- |
| G0 / Pn | wave cert / mastery phase cert | scorecard |
| pre-push authority PR | `governor.merge_certification.json` | log digest package |
| promotion S1–S4 | `governor.promotion_gate_audit.json` | eight-gate check table extract |

## Promotion acceptance

A stage is accepted only when:

1. Eight gates evidenced (`docs`, `tests`, `cli_surface`, `failure_mode`, `approval_boundary`, `output_artifact`, `rollback_path`, `verification_path`)  
2. `builder_ii.promotion_readiness_record` ready for that `target_state`  
3. `builder_ii.promotion_decision_record` (or HITL promotion decision) **approved** by human  
4. CAPABILITY_PROMOTION / command_authority / matrix updated to match **actual** power  
5. Governor promotion gate audit PASS  

Readiness without decision is **not** acceptance.
