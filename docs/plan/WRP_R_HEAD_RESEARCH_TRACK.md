# Trained R Head — Research Track (P6 deferred)

**Status:** DELIBERATELY DEFERRED research track.  
**Not** implemented as a production override of deterministic \(R\).

## Intent (Blueprint)

Offline dataset + training pipeline for a learned routing head that could advise
\(R\) under dual-platform review. Must never silently override pure forward
operator defaults.

## Current honesty

| Item | State |
| --- | --- |
| Deterministic \(R\) | Landed (`forward_operator`) |
| \(R^*\) HITL φ apply | Landed (P4) |
| Trained R head weights | **Not shipped** |
| Silent override of DEFAULT_PHI / live routing | **Forbidden** |

## Re-open criteria

1. Offline dataset schema + freeze digests
2. Training pipeline outside default `uv sync`
3. Separate S4 readiness + HUMAN + G-LEAD decision
4. Explicit bind flag (never default)

Until then, gap matrix row remains OPEN as a named research deferral — not an
accidental omission.
