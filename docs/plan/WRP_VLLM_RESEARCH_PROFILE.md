# WRP vLLM Research Profile (P6 substrate)

**Status:** RESEARCH / NON-DEFAULT interface + stub only.  
**Not** a promotion decision. **Not** a default runtime path. **Not** S3 enablement.

## Purpose

Document a dual-platform (Maker/Governor) research target for a vLLM-backed WRP
router profile without shipping weights, requiring GPU deps in CI, or soft-enabling
cloud/provider invoke.

## Interface

| Surface | Location | Behavior |
| --- | --- | --- |
| Profile metadata | `builder_ii/wrp/vllm_profile.py` → `VllmResearchProfile` | Immutable; `is_default_runtime=false`, `grants_authority=false` |
| Status | `profile_status()` / `builder-wrp vllm-profile` | Emits review JSON; never starts an engine |
| Client protocol | `VllmWrPClient` | `complete(prompt)` contract for future research |
| Stub | `StubVllmClient` | Fail-closed unless `BUILDER_II_WRP_VLLM=research` **and** real client injected |

## Opt-in

```bash
export BUILDER_II_WRP_VLLM=research
# still fails closed without an injected client / installed engine
uv run builder-wrp vllm-profile
```

Default classify / route / gate / live-lane paths **never** consult this profile.

## Mechanical sympathy

- M1 16GB local defaults remain pure hash/MSDA graph paths.
- Research profile `gpu_memory_utilization` and model id are placeholders for
  dual-platform review on larger hosts — not installed by `uv sync`.

## Promotion (future S4)

A separate readiness + HUMAN decision + G-LEAD eight-gate package is required
before any CAPABILITY_PROMOTION flip for a vLLM backend. This document alone is
not authority.
