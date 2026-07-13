# ADR-0007: Orchestration & Router Control Plane (WRP)

**Status:** Proposed (Maker draft — requires Governor dual-review + human acceptance)

**Date:** 2026-04-13

## Context

As builder-II scales multi-agent workflows, keyword heuristics in `model_router.py` and
passive `model_routing_policy` / `orchestration_*` artifacts are necessary but insufficient
as a **control plane**. Research references (STAR, MasRouter, OmniRouter, MSDA, MAAP, MoIRA,
LangGraph, ModernBERT, vLLM WRP) describe useful operator shapes, but must not be imported as
a second authority or as heavy default runtimes on Apple Silicon M1 16GB.

We need a geometry-first Workload–Router–Pool (WRP) plane that:

1. Decomposes work into explicit coordinates in Workload Space \(\mathcal{W}\).
2. Maps via forward operator \(R\) to agent configuration, tools/policy, and trajectory \(\Gamma\).
3. Records adjoint corrections \(R^*\) as **recommendations**, never silent live-routing mutation.
4. Preserves builder-II invariants: planned ≠ executed ≠ verified ≠ promoted; artifact ≠ authority.

## Decision

Implement the WRP control plane as **digest-bound artifacts** under `builder_ii/wrp/` with CLI
`builder-wrp`, default promotion state **artifact_only / validation_only / recommendation_only**.

| Operator | Module | Artifact kind(s) |
| --- | --- | --- |
| WorkloadClassifier (F0) | `workload_classifier.py` | `builder_ii.wrp.workload_classification` |
| CollaborationPlanner (F1) | `collaboration_planner.py` | `builder_ii.wrp.collaboration_topology` |
| AllocationOptimizer (F2) | `allocation_optimizer.py` | `builder_ii.wrp.fleet_allocation` |
| GovernanceRouter (F3) | `governance_router.py` | `builder_ii.wrp.msda_policy`, `msda_gate_decision` |
| ExperienceStore (F4) | `experience_store.py` | `builder_ii.wrp.experience_store` |
| AgentFactory | `agent_factory.py` | `builder_ii.wrp.agent_factory_plan` |
| SubtaskGraphManager | `subtask_graph.py` | `builder_ii.wrp.subtask_graph`, `replay_report` |
| Evaluator | `evaluator.py` | `builder_ii.wrp.trajectory_evaluation`, `proof_record` |
| Forward \(R\) | `forward_operator.py` | `builder_ii.wrp.forward_route` |
| Adjoint \(R^*\) | `adjoint_operator.py` | `builder_ii.wrp.adjoint_correction` |

### Explicit non-decisions

- **No** default ModernBERT / torch training / ANN embedding path on M1.
- **No** LangGraph runtime dependency (pure-Python DAG).
- **No** OPA sidecar as required runtime (declarative MSDA JSON; OPA optional for Governor review).
- **No** vLLM as Apple Silicon default (research/target-profile reference only).
- **No** live multi-agent execution promotion by virtue of module existence.
- Dual-platform Maker (Grok Build) / Governor (Antigravity) merge ceremony is **file-mediated**.

## Consequences

### Positive

- Auditable, deterministic routing recommendations under frozen experience.
- Clear Maker vs Governor roles without network coupling between platforms.
- Bridges existing orchestration assignment, model routing policy, and obligation lanes.

### Negative / costs

- Additional artifact kinds and CLI surface area.
- Sub-millisecond classification cost is replaced by explicit feature rules (acceptable).
- Governor certification is a process dependency before push when ceremony is enforced.

### Authority boundary

WRP artifacts **never** set `artifact_is_authority`, never execute models/tools/shell, and never
flip capability promotion matrices. Applying \(R^*\) weight suggestions requires a separate HITL
promotion path (eight gates + evidence).

## Evidence / tests

```bash
uv run pytest tests/test_wrp_spaces.py tests/test_wrp_classifier.py \
  tests/test_wrp_collaboration.py tests/test_wrp_allocation.py \
  tests/test_wrp_governance.py tests/test_wrp_adjoint.py \
  tests/test_wrp_forward_and_exchange.py tests/test_wrp_cli.py \
  tests/scenarios/test_wrp_full_lane.py -q
```

Acceptance mapping: `docs/WRP_ACCEPTANCE.md`.

## Relations

- Extends passive surfaces in `model_routing_policy`, `orchestration_plan`, `orchestration_obligation`.
- Does not supersede Goose / deepagents runtime promotion contracts (`docs/RUNTIME_PROMOTION.md`).
- Compatible with CodeVault boundary ADR-0005 (WRP is not CodeVault; CodeVault outputs remain non-authority).
