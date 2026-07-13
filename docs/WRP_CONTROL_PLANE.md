# WRP Control Plane

Geometry-first Workload–Router–Pool (WRP) orchestration & routing control plane for builder-II.

**ADR:** [`docs/adrs/ADR-0007-orchestration-router-control-plane.md`](adrs/ADR-0007-orchestration-router-control-plane.md)  
**Acceptance:** [`docs/WRP_ACCEPTANCE.md`](WRP_ACCEPTANCE.md)  
**Gap ledger:** [`docs/WRP_MASTERY_GAP_MATRIX.md`](WRP_MASTERY_GAP_MATRIX.md)

## Current truth (do not inflate)

| Dimension | State today |
| --- | --- |
| Capability promotion | `artifact_only` / `validation_only` / `recommendation_only` |
| Command surface | `builder-wrp` (Tier 1) — plan/validate/recommend |
| Live multi-agent execution | **Not enabled** — G0–W5 Governor cert ≠ enabled |
| Absolute mastery | **In progress** (phases P0–P7); substrate landed, live lane and promotion decisions open |

This document states both **what exists** and the **mastery target**. Target language is not a grant of power.

## Absolute mastery target (end state)

Source docs require a coordination **substrate that runs**, not only JSON:

1. Digest-bound operators for classify → topology → allocate → MSDA gate → factory bind → graph execute → evaluate → experience → optional \(R^*\).
2. **Live orchestration lane** under HITL / promotion envelopes (`run-approved` when S2 is decided).
3. Forward \(R\) deterministic under frozen experience; \(R^*\) applied only via promotion, then actually applied.
4. Proof classes **R / D / U** with measured Class U.
5. Dual-platform Maker (Grok) / Governor (Antigravity) merge ceremony on authority changes.
6. Opt-in backends (embedding/ModernBERT-class, OPA eval, vLLM research profile, LangGraph adapter) exist and are promotion-ready; **defaults stay M1-safe**.

Eight promotion gates are the **mechanism** of enablement, not a permanent stop.

## Staged promotion (S1–S4)

| Stage | Target power | Status |
| --- | --- | --- |
| S1 | Recommendations **bound** into routing / assignment dry-run | **Code landed** (`require_wrp_binding` / `BUILDER_II_WRP_BIND` / dry-run `require_wrp`); promotion decision blocked until G-LEAD + HUMAN |
| S2 | HITL live lane (`builder-wrp run-approved`) | Open |
| S3 | Scoped `enabled` for declared profiles | Open |
| S4 | Backend promotions (embed / OPA / vLLM research) | Open |

## Live lane contract (target — not current command)

When S2 is promoted, the live lane must:

```text
inputs:
  - digest-bound forward_route or packed WRP plan
  - HITL approval / promotion decision ref
  - MSDA policy + gate decisions
  - budget envelope; tool ∩ model allowlists
behavior:
  - execute graph via already-promoted substrates only
  - every step: MSDA preflight → invoke → receipt → experience append
  - never shell=True; never unbound tools; never silent cloud escalation
outputs:
  - wrp_live_run_receipt; experience delta; evaluation; optional adjoint recommendation
rollback:
  - failure receipt; no silent policy apply; HITL patch rollback for mutations
```

Until S2 decision evidence lands, **no** live-lane command may claim execution authority.

## Non-authority boundaries (current)

- Does not execute models, shell, MCP, Goose, or deepagents **today**.
- Does not grant promotion authority by artifact existence.
- Adjoint corrections require HITL promotion to apply to live policy.
- Maker packages are not self-certified; Governor cert is separate.
- Enabling by module existence alone is forbidden; **failing to run promotion when evidence is ready is also failure.**

## Operators (substrate)

| Wave | Operator | CLI | Kind |
| --- | --- | --- | --- |
| W0 | WorkloadClassifier | `builder-wrp classify` | `builder_ii.wrp.workload_classification` |
| W1 | CollaborationPlanner | `builder-wrp plan-collab` | `builder_ii.wrp.collaboration_topology` |
| W2 | AllocationOptimizer | `builder-wrp allocate` | `builder_ii.wrp.fleet_allocation` |
| W3 | GovernanceRouter / MSDA | `builder-wrp gate`, `msda-policy` | `msda_policy`, `msda_gate_decision` |
| W4 | ExperienceStore + \(R^*\) | `builder-wrp experience-init`, `adjoint`, `simulate-epochs` | `experience_store`, `adjoint_correction` |
| W5 | SubtaskGraph + replay | `builder-wrp graph`, `replay` | `subtask_graph`, `replay_report` |
| compose | Forward \(R\) | `builder-wrp route` | `forward_route` |

## Spaces

- \(\mathcal{W}\): domain, difficulty, safety, context, interaction ∈ [0,1]
- \(\mathcal{A}\): role, reasoning_coverage, tool_coverage, model_family, platform
- \(\mathcal{T}\): MSDA policy + allowed/denied tools and data domains
- \(\Gamma\): subtask graph nodes/edges + orchestration patterns

## Orchestration patterns (target executable)

Sequential chain; parallel fan-out/fan-in; hierarchical manager-worker; handoff-based routing; cyclic revisitation with Evaluator stop conditions. Named today; **runtime execution** is a mastery open item.

## Dual-platform exchange

```text
artifacts/wrp_exchange/<WAVE>/
  maker_candidate_manifest.json
  governor/   # Antigravity writes cert + scorecard here
  README.md

artifacts/wrp_exchange/mastery/P0…P7/
  maker_candidate_manifest.json
  test_metadata.json
  promotion_evidence/   # when applicable
  governor/
```

```bash
builder-wrp package-exchange --wave G0 --summary "constitutionalization" --branch feat/wrp-control-plane
```

## Mechanical sympathy

Default lanes remain local (`phi-reasoning`, `qwen-coder`) per `docs/model_role_matrix.md`.
High-cost models are recommended only when non-trivial. ModernBERT-class embeddings, OPA binary eval, and vLLM WRP are **opt-in backends** required for source fidelity, **not** M1 defaults.

## Validation

```bash
builder-wrp validate path/to/artifact.json
uv run pytest tests/test_wrp_*.py tests/scenarios/test_wrp_full_lane.py -q
uv run builder-platform audit-docs
```
