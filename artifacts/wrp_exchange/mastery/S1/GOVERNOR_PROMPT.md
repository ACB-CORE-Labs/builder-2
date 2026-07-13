# G-LEAD prompt — S1 bound recommendations

You are Governor (Gemini-3.1-Pro) for WRP absolute mastery **S1**.

Read: artifacts/wrp_exchange/mastery/S1/, planning/evidence/wrp_s1_readiness.json,
planning/evidence/wrp_s1_decision.json, docs/plan/WRP_S1_BINDING_DESIGN.md,
CAPABILITY_PROMOTION WRP row, tests/test_wrp_s1_binding.py.

Verify eight gates for **bound recommendation_only** (not live enablement):
docs, tests, cli, failure_mode, approval_boundary, output_artifact, rollback, verification.

Confirm:
1. Default still unbound (require_wrp_binding false) unless flag set
2. No model/shell/MCP execution claimed
3. Fail-closed when require true and classification missing
4. Decision correctly blocked pending HUMAN

Emit governor/promotion_gate_audit.json {status PASS|FAIL, gates{}, findings[]}.
Do not approve HUMAN decision yourself — audit only.
