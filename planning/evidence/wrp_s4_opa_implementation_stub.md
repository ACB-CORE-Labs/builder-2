# S4 implementation stub — `opa` (future PR only)

**Status:** STUB / design note  
**HUMAN decision:** approved for future opt-in implementation PR (`planning/evidence/wrp_s4_opa_decision.json`)  
**Runtime today:** pure MSDA default; `s4_promoted=false`; doctor may report opa binary availability without promoting

## Allowed future PR scope (opt-in, M1-safe)

1. Keep pure-Python MSDA as **default** path.  
2. Document/register opt-in `--backend opa` (already present) under validation_only honesty.  
3. Tests: fail-closed when `opa` missing; parity notes vs pure eval.  
4. **Do not** start engines by default; **do not** flip global S4; **do not** change S3.

## Out of scope for first impl PR

- Bulk S4  
- Cloud invoke  
- Making OPA required on M1  

## Rollback

Unset opt-in flags; delete or supersede decision only via HUMAN lineage; keep pure MSDA.
