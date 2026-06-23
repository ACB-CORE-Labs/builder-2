---
name: core-governed-coding
description: CORE deterministic engine coding agent. Enforces versor_condition(F) < 1e-6, exact CGA recall, no ANN/HNSW/cosine, temperature 0, SPECULATIVE until CLI gates pass. Use for any CORE code change.
---

# CORE Governed Coding

## Hard invariants (refuse by name)
- `versor_condition(F) < 1e-6` on every runtime FieldState
- `versor_apply(V,F)` transitions; `cga_inner` recall only — no cosine, ANN, HNSW
- No stochastic generation in core cognitive paths
- Normalization ONLY at: `ingest/gate.py`, `language_packs/compiler.py`, `algebra/versor.py`, `sensorium/*/canonical.py`, `session/context.py`
- NO hot-path repair in `generate/stream.py`, `field/propagate.py`, `vault/store.py`
- Claim transitions ONLY via TeachingChainProposal + `vault/store.py`
- Proposals are **SPECULATIVE** until `builder verify` passes

## Forbidden edits
Never modify: `algebra/`, `field/`, `generate/`, `core/cognition/`, `vault/`, `teaching/`, `calibration/`, `sensorium/` unless explicitly tasked on CORE itself.

## Workflow
1. `/plan` for non-trivial sensitive changes
2. Read AGENTS.md, GROK.md, `docs/runtime_contracts.md` before edits
3. Trace call sites before writing
4. Label outputs [SPECULATIVE] until verification PASS
5. Run `builder verify <module>` — fix upstream cause on failure
6. Answer all 5 PR questions before finalizing
7. `/core-handoff` or handoff skill at session end

## Suite routing
algebra/, field/ → algebra | generate/, core/cognition/ → cognition | vault/, teaching/ → teaching | sensorium/ → sensorium | language_packs/ → packs | platform/ → smoke