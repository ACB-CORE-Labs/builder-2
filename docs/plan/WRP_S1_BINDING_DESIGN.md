# WRP S1 Binding Design (M-LEAD)

**Stage:** S1 — `recommendation_only` **operationally bound** (not live execution).  
**Status:** Design for implementation after P0 merge + pure-module landings.  
**Owner:** M-LEAD (Grok-4.5) only for contested files.

## Problem

Today WRP is **annotation-only**:

- `model_router.choose_model_alias` appends WRP tier/alias to `rationale` string; does not change selected alias from WRP.
- `orchestration_assignment` dry-run may attach `wrp_workload_recommendation` optionally; failure is warn-and-continue.

S1 requires WRP classification (and fleet binding when present) to be **required structured fields** on routing recommendation / dry-run artifacts, with fail-closed options.

## Target behavior (S1)

### A. `builder_ii.model_routing_recommendation`

Add required block when policy flag `require_wrp_binding: true` (default **false** until S1 decision; S1 decision flips default or sets explicit true in canonical policy fixtures):

```json
"wrp_binding": {
  "required": true,
  "classification_digest": "<64 hex>",
  "tier": "primary",
  "recommended_model_alias": "qwen-coder",
  "confidence": 0.82,
  "source_kind": "builder_ii.wrp.workload_classification"
}
```

Rules:

1. If `require_wrp_binding` and classification fails → **raise** (no silent skip).
2. If binding present, recommendation `selected` / top candidate **must prefer** WRP alias when it appears in filtered registry candidates; if not in candidates, record `wrp_alias_excluded_reason` and keep policy winner (fail-open on alias, fail-closed on missing binding when required).
3. Validator rejects missing `wrp_binding` when policy requires it.

### B. `model_router.choose_model_alias` / `plan_session`

- Env `BUILDER_II_WRP_BIND=1` or session plan field `wrp_bind: true` → WRP alias **wins** over keyword heuristic when confidence ≥ threshold (reuse classifier threshold).
- Without bind flag: keep advisory rationale (backward compatible).
- S1 promotion sets bind true for builder target profile defaults via config — **after** decision record.

### C. Orchestration assignment dry-run

- `wrp_workload_recommendation` becomes **required** when assignment policy `require_wrp: true`.
- Include digests; dry-run fails validation if absent under require flag.

### D. Fleet binding (P2.2 couples here)

`fleet_allocation` gains `fleet_binding: { selected_alias, token_budget_remaining, risk_class }`.  
S1 may land classification bind first; fleet bind follows same pattern in same or follow-up PR.

## Promotion evidence (S1)

| Gate | Evidence |
| --- | --- |
| docs | This design + WRP_CONTROL_PLANE S1 row |
| tests | `tests/test_wrp_s1_binding.py` — require flag on/off, prefer alias, fail closed |
| cli | existing builder-model-policy / builder-wrp classify |
| failure_mode | missing WRP when required → non-zero / validation errors |
| approval | human-approved `promotion_decision_record` |
| output | recommendation JSON with wrp_binding |
| rollback | flip require flag off; demote decision |
| verification | pytest selection + audit-docs |

## Implementation order

1. Tests for validator + create_model_routing_recommendation wrp_binding  
2. Wire classify_workload into create path  
3. model_router bind flag  
4. assignment dry-run require  
5. readiness `wrp_s1.json` + decision record  
6. CAPABILITY_PROMOTION / command notes: “bound recommendation_only”  
7. Governor promotion_gate_audit  

## Non-goals for S1

- No `run-approved` live lane (S2)  
- No gateway MSDA preflight (P3)  
- No experience apply (P4)  

## Parallelism

- Implement after M-FAST pure modules merge OR in parallel only for **tests that mock** classify_workload.  
- Do not wait for OPA/graph for S1 classification bind.  
- Governor S1 audit runs when readiness draft exists (concurrent with final test polish).
