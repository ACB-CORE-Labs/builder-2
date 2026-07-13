# WRP Control Plane

Geometry-first Workload–Router–Pool orchestration & routing control plane for builder-II.

**Capability state:** `artifact_only` / `validation_only` / `recommendation_only`  
**Command surface:** `builder-wrp` (Tier 1)  
**ADR:** [`docs/adrs/ADR-0007-orchestration-router-control-plane.md`](adrs/ADR-0007-orchestration-router-control-plane.md)

## Non-authority boundaries

- Does not execute models, shell, MCP, Goose, or deepagents.
- Does not grant promotion authority.
- Adjoint corrections require HITL promotion to apply to live policy.
- Maker packages are not self-certified; Governor cert is separate.

## Operators

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

## Dual-platform exchange

```text
artifacts/wrp_exchange/<WAVE>/
  maker_candidate_manifest.json
  governor/   # Antigravity writes cert + scorecard here
  README.md
```

```bash
builder-wrp package-exchange --wave G0 --summary "constitutionalization" --branch feat/wrp-control-plane
```

## Mechanical sympathy

Default lanes remain local (`phi-reasoning`, `qwen-coder`) per `docs/model_role_matrix.md`.
High-cost models are recommended only when `non_trivial=true`. ModernBERT/vLLM are non-default references.

## Validation

```bash
builder-wrp validate path/to/artifact.json
uv run pytest tests/test_wrp_*.py tests/scenarios/test_wrp_full_lane.py -q
```
