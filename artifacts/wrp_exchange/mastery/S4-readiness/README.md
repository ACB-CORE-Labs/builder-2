# WRP exchange package — mastery/S4-readiness

**Scope:** HUMAN / G-LEAD handoff for S4 **backend promotion readiness review**.  
**Does not** promote any backend. **Does not** enable S3 multi-agent. **Does not** start engines.

| Item | Path |
| --- | --- |
| Consolidated summary | `planning/evidence/s4_review_summary.md` |
| Wave gate audit (DRAFT) | `planning/evidence/wrp_s4_promotion_gate_audit.json` |
| Per-backend readiness | `planning/evidence/wrp_s4_<backend>_readiness.json` |
| Per-backend decision template | `planning/evidence/wrp_s4_<backend>_decision.json` (`blocked` / PENDING_HUMAN) |
| Maker exchange | `maker_candidate_manifest.json` (this dir) |
| G-LEAD brief | `GOVERNOR_PROMPT.md` (this dir) |
| Governor emit dir | `governor/` (empty until G-LEAD / HUMAN cert) |

## Backends (independent HUMAN decisions)

- `modernbert_embed`
- `opa`
- `langgraph`
- `vllm_research`

## Honesty locks (must remain true after any cert unless HUMAN issues a new approved decision)

- every `decision.approved == false` until HUMAN replaces template  
- `s4_promoted == false` on doctor/inventory/draft packages  
- no engine start by doctor / s4-readiness CLI  
- no bulk S4 flip  
- S3 remains HUMAN blocked (`planning/evidence/wrp_s3_decision.json`)  
- live multi-agent path remains `hitl_runtime_candidate` only  

## Governor emit targets (optional G-LEAD)

If dual-platform ceremony is used for this wave (optional this phase; HUMAN may review Maker package alone):

1. `artifacts/wrp_exchange/mastery/S4-readiness/governor/wave_mastery_S4_readiness_cert.json`  
2. `artifacts/wrp_exchange/mastery/S4-readiness/governor/promotion_gate_audit.json`  

Start with `GOVERNOR_PROMPT.md`. Do not implement Maker code as authority. Do not self-certify promotion PASS.
