# WRP P2 Remainder Wires

**Status:** Implementation PR (recommendation/validation only; no S2).  
**Depends on:** S1 approved on main.

## Wires

| Wire | Module | Activation | Default |
| --- | --- | --- | --- |
| Fleet binding | `allocation_optimizer.fleet_binding` → `create_model_routing_recommendation` | pass `fleet_binding` / `fleet_allocation` on request | always emitted on allocate |
| MSDA preflight | `wrp/msda_preflight.py` → tool + model gateways | `BUILDER_II_WRP_MSDA_PREFLIGHT=1` | **off** |
| Classifier embed | `classify_workload(use_embedding=…)` | `use_embedding=True` or `BUILDER_II_WRP_EMBED=1` | metric path |

## Non-goals

- Live lane / `run-approved` (S2)
- Default-on MSDA preflight (would deny most model_call tools under default policy)
- ModernBERT default

## Tests

`tests/test_wrp_p2_remainder_wires.py`
