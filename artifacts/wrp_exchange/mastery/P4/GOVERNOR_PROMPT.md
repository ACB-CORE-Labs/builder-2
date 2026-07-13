# Governor — mastery/P4 R* apply

## Focus (G-LEAD / 3.1-Pro)
Dual-correction cannot self-grant authority.

Verify:
1. `apply-rstar-approved` refuses without digest-bound approval
2. New `phi_policy` is versioned (parent_policy_digest); DEFAULT_PHI never mutated
3. Classifier uses φ only with explicit bind (`phi_bound` / `phi_policy_digest`)
4. `updates_live_routing_defaults=false` on plan, policy, receipt
5. Delta caps / axis allowlist fail closed
6. CAPABILITY_PROMOTION / gap matrix / COMMAND_AUTHORITY match real power (HITL candidate, not S3)

Write cert to: `artifacts/wrp_exchange/mastery/P4/governor/wave_mastery_P4_cert.json`
