# WRP MSDA Preflight Policy (W.2 / H9)

**Status:** RECORDED_ONLY product policy (Option A).  
**Not** a promotion grant. **Not** global soft-enable.

## Decision: Option A

| Option | Description | Status |
| --- | --- | --- |
| **A** | Default env **off**; S2 live lane + gateway **nodes** force preflight; tool/model gateways annotate skip/enforced on receipts | **ACCEPTED** |
| B | Product default-on for all tool/model invokes | **Rejected** without allowlist redesign + promotion |
| C | Always evaluate, soft-fail denials when off | **Rejected** (blurred fail-closed) |

## Forced vs env-gated

| Surface | Preflight |
| --- | --- |
| `builder-wrp run-approved` / live_lane | **Forced** (`enabled=True`) |
| S2 v2 `gateway_nodes` | **Forced** (`enabled=True`) |
| `tool_invocation_gateway` / `model_execution_gateway` | Env `BUILDER_II_WRP_MSDA_PREFLIGHT=1` or skip with audit annotation |

## Receipt annotation (Option A)

When preflight is skipped (default):

```json
{
  "enforced": false,
  "skipped": true,
  "skip_mode": "skipped_default_off",
  "env_name": "BUILDER_II_WRP_MSDA_PREFLIGHT",
  "grants_authority": false
}
```

When preflight ran and allowed: `enforced=true`, `skipped=false`, optional `decision_digest`.

## CLI honesty

```bash
uv run builder-wrp msda-status
```

## Re-open Option B only with

1. Expanded default MSDA allow rules for legitimate local model/tool paths  
2. Eight-gate readiness + HUMAN decision  
3. CAPABILITY_PROMOTION / matrix update
