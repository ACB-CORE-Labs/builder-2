# Mastery S1 — Bound recommendations (code + readiness)

## Landed
- `require_wrp_binding` on model routing policy/recommendations
- `BUILDER_II_WRP_BIND=1` selects WRP alias in model_router when confidence high/medium
- Assignment dry-run `require_wrp` fail-closed
- Tests: `tests/test_wrp_s1_binding.py`
- Readiness: `planning/evidence/wrp_s1_readiness.json` (ready)
- Decision: `planning/evidence/wrp_s1_decision.json` (**blocked** until HUMAN after G-LEAD)

## Not landed
- Live lane / S2
- Default require_wrp_binding=true globally (defaults stay false)

## Governor (G-LEAD) — required
Eight-gate promotion_gate_audit for target_state=recommendation_only **bound**.
Emit `governor/promotion_gate_audit.json` + optional cert.
