# Absolute mastery — living plan checklist (WRP + Vision)

**Status:** RECORDED_ONLY checklist mirror (not a promotion grant).  
**Authority:** Prefer code + `planning/evidence/*` + `docs/WRP_*` when conflict.  
**Synthesis:** [`docs/WRP_ABSOLUTE_MASTERY_SYNTHESIS.md`](../docs/WRP_ABSOLUTE_MASTERY_SYNTHESIS.md)

## Meaning of “done” here

Planning + evidence + smoke for WRP (W) and Vision (V) tracks are complete.  
**Not done:** S3 enablement, S4 runtime promo flip, cloud invoke, full platform operational matrix.

## W track (WRP)

- [x] W.1 Backend registry + doctor  
- [x] W.2 MSDA Option A preflight annotations  
- [x] W.3 Fleet fidelity  
- [x] W.4 Patterns prove (pure graph_runtime)  
- [x] W.5 AgentFactory spawn/retire lifecycle records  
- [x] W.6 S4 readiness drafts  

## V track (Vision)

- [x] V.1 builder-semantic RO  
- [x] V.2 agent RO runner candidate  
- [x] V.3 fixed-argv HITL verify profiles  
- [x] V.4 CORE target profile isolation  
- [x] V.5 Workbench boundary doc  
- [x] V.6 Final operating loop smoke  

## S track (promotion stages)

- [x] S1 bound recommendations — HUMAN approved (flagged)  
- [x] S2 HITL live — HUMAN approved (`hitl_runtime_candidate`)  
- [x] S3 readiness package + HUMAN **blocked** enablement  
- [x] S4 readiness drafts + HUMAN **per-backend** decisions recorded  
- [ ] S4 runtime `s4_promoted` flip (explicitly **not** done)  
- [ ] S3 re-open enablement (only with stronger U)  

## S4 HUMAN decision snapshot

| Backend | Decision | Next |
| --- | --- | --- |
| opa | approved (impl PR later, opt-in) | optional separate PR |
| modernbert_embed | approved (impl PR later, opt-in) | optional separate PR |
| langgraph | blocked | more evidence |
| vllm_research | blocked | research wave |

## Ceremonial verification

```bash
uv run builder-platform matrix
uv run builder-platform audit-docs
CORE_REPO_PATH=<path-to-core> uv run builder-platform final-loop-smoke \
  --targets builder,core -o .builder/artifacts/v6-smoke
```

## Honesty locks

- `s3_enabled=false`  
- `s4_promoted=false` (runtime)  
- no bulk S4 flip  
- no cloud invoke as product default  
- Workbench coupling `NONE`  
- model output ≠ approval  

## Next (optional, not required for synthesis)

1. Opt-in implementation PR for `opa` only  
2. Opt-in implementation PR for `modernbert_embed` only  
3. Keep langgraph/vllm blocked until re-review  
