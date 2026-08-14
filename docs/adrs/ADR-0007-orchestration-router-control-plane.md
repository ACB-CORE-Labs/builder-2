# ADR-0007: Orchestration & Router Control Plane (WRP)

**Status:** Accepted (amended for absolute mastery staged promotion)

**Date:** 2026-04-13  
**Amended:** 2026-07-13 — staged enablement; opt-in backends; cert ≠ terminal stop

## Context

As builder-II scales multi-agent workflows, keyword heuristics in `model_router.py` and
passive `model_routing_policy` / `orchestration_*` artifacts are necessary but insufficient
as a **control plane**. Research references (STAR, MasRouter, OmniRouter, MSDA, MAAP, MoIRA,
LangGraph, ModernBERT, vLLM WRP) describe useful operator shapes. They must not be imported as
a second authority or as **default** heavy runtimes on Apple Silicon M1 16GB — but they also
must not be permanently abandoned under a passive-only soft stop.

We need a geometry-first Workload–Router–Pool (WRP) plane that:

1. Decomposes work into explicit coordinates in Workload Space \(\mathcal{W}\).
2. Maps via forward operator \(R\) to agent configuration, tools/policy, and trajectory \(\Gamma\).
3. Records adjoint corrections \(R^*\); **applies** them only through HITL/promotion (never silent).
4. Preserves builder-II invariants: planned ≠ executed ≠ verified ≠ promoted; artifact ≠ authority.
5. Reaches **absolute mastery**: live orchestration under gates, proof R/D/U, dual-platform ceremony.

Source charters: CORE R&D Blueprint; Multi-Platform (Grok + Antigravity) Execution Master-Plan.

## Decision

### D1 — Substrate

Implement the WRP control plane as **digest-bound artifacts** under `builder_ii/wrp/` with CLI
`builder-wrp`. Initial land: **artifact_only / validation_only / recommendation_only**.

| Operator | Module | Artifact kind(s) |
| --- | --- | --- |
| WorkloadClassifier (F0) | `workload_classifier.py` | `builder_ii.wrp.workload_classification` |
| CollaborationPlanner (F1) | `collaboration_planner.py` | `builder_ii.wrp.collaboration_topology` |
| AllocationOptimizer (F2) | `allocation_optimizer.py` | `builder_ii.wrp.fleet_allocation` |
| GovernanceRouter (F3) | `governance_router.py` | `builder_ii.wrp.msda_policy`, `msda_gate_decision` |
| ExperienceStore (F4) | `experience_store.py` | `builder_ii.wrp.experience_store` |
| AgentFactory | `agent_factory.py` | `builder_ii.wrp.agent_factory_plan` + W.5 `agent_lifecycle_record` / `agent_lifecycle_proof` (validation_only records; spawn_executed=false; not S3 process spawn) |
| SubtaskGraphManager | `subtask_graph.py` / `graph_runtime.py` | `subtask_graph`, `replay_report`, live run receipts |
| Evaluator | `evaluator.py` | `trajectory_evaluation`, `proof_record` |
| Forward \(R\) | `forward_operator.py` | `builder_ii.wrp.forward_route` |
| Adjoint \(R^*\) | `adjoint_operator.py` | `builder_ii.wrp.adjoint_correction` |

### D2 — Staged promotion (absolute mastery)

Enablement proceeds through **explicit promotion decisions** (eight gates + evidence). Stages:

| Stage | Target | Effect |
| --- | --- | --- |
| **S1** | recommendation_only **bound** | WRP outputs required inputs to routing recommendation / assignment dry-run |
| **S2** | HITL live lane | `builder-wrp run-approved` executes bounded graph under approval envelope |
| **S3** | scoped `enabled` | Live lane default inside operator-declared profiles/allowlists |
| **S4** | backend promotions | Embedding / OPA / vLLM research each have independent readiness+decision |

**G0–W5 Governor certification proves substrate quality. It does not complete mastery and does not enable live execution.**

Failing to open a promotion decision when readiness is complete is a process failure, not governance success.

### D3 — Opt-in backends (source fidelity; non-default)

| Backend | Default on M1 | Mastery requirement |
| --- | --- | --- |
| Rule + hashing / kNN classifier | Yes | Required |
| ModernBERT-class / small embedder | No (explicit flag/extra) | Protocol + tests + readiness |
| Pure-Python graph runtime | Yes | Required for S2 |
| LangGraph adapter | No (optional extra) | Adapter + tests with dep present/absent |
| MSDA pure-Python | Yes | Required; preflight at S2 |
| OPA export / optional `opa` eval | Export yes; binary optional | Parity corpus mandatory |
| vLLM WRP research profile | No | Design + interface + spike; not M1 default |
| Trained R head | No | Offline research track; never silent override of deterministic R |

### D4 — Dual-platform ceremony

Maker (Grok Build: Grok-4.5 + Composer) / Governor (Antigravity: Gemini-3.1-Pro + Flash).
File-mediated exchange under `artifacts/wrp_exchange/`. Authority-changing PRs require Governor
cert or recorded human override.

### Explicit non-decisions (narrow)

- **No** ModernBERT / torch / vLLM as **default** on M1 16GB.
- **No** LangGraph as **required** install dependency for core package.
- **No** OPA sidecar as **required** runtime for core package.
- **No** live multi-agent execution **by virtue of module existence alone**.
- **No** autonomous source mutation outside existing HITL patch lane.
- **No** unbounded shell (`shell=True`).

These non-decisions **do not** forbid implementing opt-in backends, HITL live lane, applied \(R^*\),
or scoped enablement under eight gates.

## Consequences

### Positive

- Auditable, deterministic routing under frozen experience.
- Clear Maker vs Governor roles without network coupling.
- Path from substrate → bound recommendations → live lane → scoped enablement.
- Bridges orchestration assignment, model routing, tool/MCP gateways, verification profiles.

### Negative / costs

- Larger surface (live receipts, promotion evidence, backend adapters).
- Governor ceremony is process cost on authority PRs.
- Class U and adaptivity require measurement campaigns.

### Authority boundary

WRP artifacts alone never set `artifact_is_authority` and never flip matrices.
Live power exists only after the matching promotion decision and command_authority update.
Applying \(R^*\) requires promotion; after approval, updates **must be applied** to versioned
experience/policy stores (not left inert).

## Evidence / tests

```bash
uv run pytest tests/test_wrp_spaces.py tests/test_wrp_classifier.py \
  tests/test_wrp_collaboration.py tests/test_wrp_allocation.py \
  tests/test_wrp_governance.py tests/test_wrp_adjoint.py \
  tests/test_wrp_forward_and_exchange.py tests/test_wrp_cli.py \
  tests/scenarios/test_wrp_full_lane.py -q
```

Acceptance: `docs/WRP_ACCEPTANCE.md`. Gap ledger: `docs/WRP_CONTROL_PLANE.md`.
Control plane: `docs/WRP_CONTROL_PLANE.md`.

## Relations

- Extends `model_routing_policy`, `orchestration_plan`, `orchestration_obligation`.
- Live lane may only invoke **already-promoted** substrates (model gateway, tools/MCP, Goose readonly, HITL verify/patch, deepagents under their contracts).
- Does not supersede Goose / deepagents runtime promotion contracts (`docs/RUNTIME_PROMOTION.md`).
