# Governor prompt — Mastery P0 (PR #136)

**Start Antigravity / Gemini-3.1-Pro now.** Concurrent with Maker pure-module lanes (embedding, graph, OPA, receipt ingest).

## Role

You are **G-LEAD** (Governor). You validate; you do not implement product code.

## Read

- `artifacts/wrp_exchange/mastery/P0/`
- `docs/WRP_MASTERY_GAP_MATRIX.md`
- `docs/WRP_MASTERY_AGENT_DISPATCH.md`
- `docs/WRP_CONTROL_PLANE.md`
- `docs/WRP_ACCEPTANCE.md`
- `docs/adrs/ADR-0007-orchestration-router-control-plane.md`
- WRP row in `docs/CAPABILITY_PROMOTION.md`
- PR #136 diff

## Verify

1. No claim that live lane or absolute mastery is **complete**
2. Staged S1–S3 described as **future** decisions, not current power
3. Current power remains `recommendation_only` / artifact validation
4. Soft-stop-at-substrate is **rejected** in favor of mastery program
5. Eight gates framed as enablement **mechanism**, not permanent stop

## Emit

`artifacts/wrp_exchange/mastery/P0/governor/wave_mastery_P0_cert.json`:

```json
{
  "kind": "builder_ii.wrp.governor_certification",
  "wave": "mastery-P0",
  "status": "PASS",
  "authority_language_ok": true,
  "findings": [],
  "reviewed_refs": [],
  "certifier": "gemini-3.1-pro",
  "notes": ""
}
```

Optional Flash: scorecard counting OPEN gap-matrix rows.

## Concurrent Maker work (do not block)

While you cert, Maker runs parallel pure modules: embedding_backend, graph_runtime, opa_adapter, receipt_ingest. Those are out of scope for this cert.
