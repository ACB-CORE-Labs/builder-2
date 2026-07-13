# WRP Acceptance Criteria (W0–W5)

Mapped from the Multi-Platform Execution Master-Plan to concrete Maker proof commands.
Governor certification is required for merge ceremony; Maker tests alone are not self-certification.

| Wave | Acceptance criterion | Maker proof | Pytest |
| --- | --- | --- | --- |
| G0 | ADR-0007 + skeleton + kinds + exchange layout | docs present; package imports | `tests/test_wrp_spaces.py`, `tests/test_wrp_forward_and_exchange.py` |
| W0 | Classifier routes ≥95% of fixtures to correct tier | `builder-wrp score-classifier` | `tests/test_wrp_classifier.py` |
| W1 | Handoff zero state loss; topology validation &lt;50ms avg | handoff keys + latency test | `tests/test_wrp_collaboration.py` |
| W2 | Fleet allocation within 10% of token budget under stress | budget stress fixtures | `tests/test_wrp_allocation.py` |
| W3 | 100% of access requests validated before any execution claim | gate fixtures all logged; `execution_permitted=false` | `tests/test_wrp_governance.py` |
| W4 | Trajectory correction reduces error ≥30% over 5 epochs (fixtures) | `builder-wrp simulate-epochs` | `tests/test_wrp_adjoint.py` |
| W5 | Replay yields perfect sequence/digest match | `builder-wrp replay` | `tests/scenarios/test_wrp_full_lane.py` |

## Batch command

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

## Governor artifacts (Antigravity)

| Wave | Gemini-3.1-Pro | Gemini-3.5-Flash |
| --- | --- | --- |
| G0 | `governor.adr0007_review` / wave cert | — |
| Wn | `governor.wave_Wn_cert.json` | `governor.wave_Wn_scorecard.json` |
| pre-push | `governor.merge_certification.json` | log digest package |
