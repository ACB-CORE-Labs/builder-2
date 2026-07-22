# ADR 0001 — WRP `invoke_cloud` gateway mode (W2.2)

## Status

Accepted (implemented).

## Context

W1.2 added `invoke_local` as the governed execution seam for local/stub providers.
Provider variety and cost savings require cloud models under the same governance
grammar: MSDA → HITL approval → budget → ledger → receipt.

## Decision

Add `gateway_mode=invoke_cloud` to `GATEWAY_MODES` with **harder** gates than local:

1. `payload.approval_path` — per-call approval artifact file required
2. `payload.hard_spend_cap_usd` (or `max_usd`) — hard USD ceiling
3. `settings.allow_cloud_models` / `BUILDER_ALLOW_CLOUD_MODELS` must be true (stubs may opt-in offline for CI)
4. `risk_classification=cloud_external` models only
5. Egress record on receipt (`cloud_egress`) using **token refs**, never raw secrets
6. Live-lane plans must set `cloud_provider_invoke=true` **iff** `gateway_mode=invoke_cloud`

Default mode remains `record`. Cloud is never self-enabled by ambient ambient flags alone.

## Consequences

- Cloud adapters (`builder_ii/adapters/openai_compat/cloud_chat.py`) implement OpenAI-compatible HTTP clients.
- CI uses stub providers + injected transport; live keys stay operator-owned env vars.
- Permanent non-goal of arbitrary HITL shell exec is unchanged.
