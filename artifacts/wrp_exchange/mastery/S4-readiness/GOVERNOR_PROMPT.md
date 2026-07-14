# G-LEAD — S4 readiness HUMAN review handoff (draft packages only)

You are G-LEAD (Gemini-3.1-Pro or equivalent dual-correction reviewer).  
Dual-correction certifier only. Do not implement Maker code as authority.  
Do not claim S4 promotion. Do not start engines. Do not invent performance numbers.

**Wave:** S4 backend readiness review packages  
**Scope:** planning/evidence + exchange only  
**PR context:** docs package consolidating W.6 drafts for HUMAN review  

## What was shipped (honest scope)

- W.6 (#155): `builder_ii/wrp/s4_readiness.py` + `builder-wrp s4-readiness list|draft`  
- Per-backend readiness + decision templates under `planning/evidence/wrp_s4_*`  
- Gate audit skeleton `wrp_s4_promotion_gate_audit.json` (`status=DRAFT`)  
- Consolidated HUMAN summary `planning/evidence/s4_review_summary.md`  
- This exchange package under `artifacts/wrp_exchange/mastery/S4-readiness/`  
- **No** runtime enablement, **no** `s4_promoted=true`, **no** bulk approve  

## Backends under review (each independent)

1. `modernbert_embed`  
2. `opa`  
3. `langgraph`  
4. `vllm_research`  

## Honesty locks (must remain true)

| Lock | Required |
| --- | --- |
| `readiness.ready` | `true` (evidence refs for review) |
| `decision.approved` | `false` |
| `decision.decided_by` | `PENDING_HUMAN` until HUMAN decides |
| `s4_promoted` | `false` |
| `s3_enabled` | `false` |
| enablement / engine start | none |
| bulk S4 flip | forbidden |

## Eight-gate checklist (this readiness handoff package)

1. **Docs** — S4 described as OPEN drafts; no inflated “promoted” claims  
2. **Tests** — `test_wrp_s4_readiness_drafts` + backend registry tests exist and pass  
3. **Surface** — `builder-wrp s4-readiness` is validation_only  
4. **Failure mode** — decisions default blocked; doctor does not start engines  
5. **Human boundary** — per-backend HUMAN decision; this cert is not approval  
6. **Output artifacts** — JSON pairs + summary + this exchange  
7. **Rollback** — leave decisions blocked; keep `s4_promoted=false`  
8. **Verification** — `builder-promotion validate` + `doctor-backends` + `audit-docs`  

## Emit only (if certifying the handoff package — not a promo PASS)

```text
artifacts/wrp_exchange/mastery/S4-readiness/governor/promotion_gate_audit.json
artifacts/wrp_exchange/mastery/S4-readiness/governor/wave_mastery_S4_readiness_cert.json
```

Cert language must state:

- handoff package completeness **or** gaps  
- `decision.approved` still false for all backends  
- HUMAN still required for each backend  
- **not** “S4 promoted”  

If any honesty lock is violated, emit **FAIL** with concrete paths. Do not soft-pass.
