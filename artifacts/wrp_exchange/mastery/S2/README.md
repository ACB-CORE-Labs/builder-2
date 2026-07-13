# Mastery S2 — HITL live lane (v1)

## Surface
- `builder-wrp plan-live` → live_run_plan
- `builder-wrp approve-live` → live_run_approval (digest-bound)
- `builder-wrp run-approved` → live_run_receipt

## Guarantees
- Forced MSDA preflight on declared msda_tools
- Graph nodes: noop|record only
- No shell; no model/tool gateway invoke in v1
- Approval.plan_digest must match plan.digest

## Decision
planning/evidence/wrp_s2_readiness.json (ready)
planning/evidence/wrp_s2_decision.json (blocked until G-LEAD + HUMAN)
