# Antigravity Governor prompt pack — WRP G0–W5

## Start these agents

### 1) Gemini-3.1-Pro (architectural dual-correction)

Review:

- `docs/adrs/ADR-0007-orchestration-router-control-plane.md`
- `docs/WRP_CONTROL_PLANE.md`
- `docs/WRP_ACCEPTANCE.md`
- `docs/CAPABILITY_PROMOTION.md` row for WRP
- `builder_ii/wrp/**` and `builder_ii/cli/wrp_cli.py`

Check:

1. No authority inflation (artifact ≠ authority; no live multi-agent promotion).
2. R\* cannot update live routing without HITL.
3. MSDA is deny-by-default; `execution_permitted` always false on gate artifacts.
4. Mechanical sympathy: no ModernBERT/vLLM defaults.
5. Dual-platform Maker/Governor exchange is file-mediated.

Write: `governor/wave_G0-W5_cert.json` with decision `PASS` | `FAIL` | `PASS_WITH_NOTES` + findings.

### 2) Gemini-3.5-Flash (scorecard)

Parse Maker test metadata and score W0–W5 acceptance table in `docs/WRP_ACCEPTANCE.md`.

Write: `governor/wave_G0-W5_scorecard.json`.

Do **not** push or merge. Certification only.
