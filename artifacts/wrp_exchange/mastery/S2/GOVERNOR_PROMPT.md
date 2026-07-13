# G-LEAD — S2 HITL live lane eight-gate audit

You are G-LEAD (Gemini-3.1-Pro). Audit PR for S2 hitl_runtime_candidate.

Read: artifacts/wrp_exchange/mastery/S2/, planning/evidence/wrp_s2_*.json,
builder_ii/wrp/live_lane.py, tests/test_wrp_live_lane.py, CAPABILITY_PROMOTION WRP row.

Verify: approval digest binding; MSDA forced; no shell; no gateway invoke S2 v1;
decision blocked pending HUMAN; S3 not claimed.

Emit governor/promotion_gate_audit.json status PASS|FAIL with eight gates.
Do not approve HUMAN decision.
