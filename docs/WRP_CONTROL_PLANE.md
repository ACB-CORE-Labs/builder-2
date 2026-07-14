# WRP Control Plane

Geometry-first Workload–Router–Pool (WRP) orchestration & routing control plane for builder-II.

**ADR:** [`docs/adrs/ADR-0007-orchestration-router-control-plane.md`](adrs/ADR-0007-orchestration-router-control-plane.md)  
**Acceptance:** [`docs/WRP_ACCEPTANCE.md`](WRP_ACCEPTANCE.md)  
**Gap ledger:** [`docs/WRP_MASTERY_GAP_MATRIX.md`](WRP_MASTERY_GAP_MATRIX.md)

## Current truth (do not inflate)

| Dimension | State today |
| --- | --- |
| Capability promotion | `artifact_only` / `validation_only` / `recommendation_only` + HITL candidates for S2 live/v2 gateways + P4 φ apply |
| Command surface | `builder-wrp` Tier 1 (incl. `benchmark --class u`) + Tier 3 `run-approved` / `apply-rstar-approved` |
| Live multi-agent execution | **Not S3-enabled** — S2 HITL graph (+ v2 record/stub gateways); P4/P5 do not enable multi-agent |
| Absolute mastery | **In progress** — P0–P7 substrate + post-P6 PARTIAL harden; S3 HUMAN **blocked**; S4 + cloud invoke OPEN ([`WRP_MASTERY_PROGRESS.md`](WRP_MASTERY_PROGRESS.md)) |

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
| S1 | Recommendations **bound** into routing / assignment dry-run | **Decided approved** on main (`planning/evidence/wrp_s1_decision.json`); flags still required for bind |
| S2 | HITL live lane (`builder-wrp run-approved`) | **Decided approved** (v1 + v2 gateway nodes on main); forced MSDA; default gateway `record`; not S3 |
| S3 | Scoped `enabled` for declared profiles | **HUMAN blocked** (`planning/evidence/wrp_s3_decision.json`) after readiness G-LEAD PASS — Class U micro-only (H7); no enablement runtime |
| S4 | Backend promotions (embed / OPA / LangGraph / vLLM research) | Open — W.6 readiness+decision *drafts* under `planning/evidence/wrp_s4_*` (`builder-wrp s4-readiness draft`); HUMAN decides each; `s4_promoted=false` |

## Live lane contract (S2 v1 — code present; decision may still be pending)

**CLI:** `plan-live` → `approve-live` → `run-approved`.

```text
inputs (v1):
  - digest-bound builder_ii.wrp.live_run_plan
  - digest-bound builder_ii.wrp.live_run_approval (plan_digest must match)
  - msda_tools[] with forced preflight (enabled=True for the lane)
  - optional fleet_binding + wrp_binding (required selected_alias / classification_digest when present)
behavior (v1):
  - forced MSDA allow for every declared tool or refuse
  - graph execute noop|record only (no shell node types)
  - model_gateway_invoked=false; tool_gateway_invoked=false
  - never shell=True
outputs:
  - builder_ii.wrp.live_run_receipt (+ optional experience_store digest)
rollback:
  - fail closed before mutate; delete receipts; no live policy apply
```

**Honest limit:** S2 is decided approved on main (`planning/evidence/wrp_s2_decision.json`). Tier 3 `hitl_runtime_candidate` for `run-approved` is the command class, not S3 `enabled`.

### S2 v2 gateway nodes (HITL; default record mode)

**CLI:** `plan-live --s2-version v2 [--gateway-mode record|stub_tool]` → `approve-live` → `run-approved`.

```text
behavior (v2):
  - allowed_node_types: noop|record|model_gateway|tool_gateway
  - every gateway node forces MSDA preflight before any work
  - gateway_mode=record (default): digest-bound synthetic gateway receipts; no network; no cloud provider
  - gateway_mode=stub_tool: in-process B7 allowlist only (builtin.echo|builtin.utc_static); model_gateway refuses stub_tool
  - cloud_provider_invoke must be false; executes_shell must be false
  - plan flags model_gateway_invoked/tool_gateway_invoked must match actual node_specs
```

v2 extends node types under the same HITL class — not S3 scoped `enabled`, and not silent cloud model enablement.

## P4 R* apply contract (HITL φ-policy versioning)

**CLI:** `phi-policy-init` → `corrections-from-receipts` → `plan-rstar-apply` → `approve-rstar-apply` → `apply-rstar-approved`.

```text
inputs:
  - real receipts (model_call | tool_call | verification | wrp_live_step)
  - digest-bound builder_ii.wrp.phi_policy (base version)
  - digest-bound builder_ii.wrp.rstar_apply_plan (correction digests + proposed φ)
  - digest-bound builder_ii.wrp.rstar_apply_approval (plan_digest must match)
behavior:
  - aggregate failure-driven suggested_phi_deltas with per-axis cap (MAX_DELTA_PER_AXIS)
  - emit NEW versioned phi_policy (parent_policy_digest chain); never mutate DEFAULT_PHI
  - classifier uses applied φ only when explicitly bound (phi= / phi_policy_digest)
  - updates_live_routing_defaults=false always
outputs:
  - builder_ii.wrp.rstar_apply_receipt + optional new phi_policy
rollback:
  - discard plan/approval/receipt; keep prior phi_policy version; DEFAULT_PHI untouched
```

## P5 Class U harness (measured utility; validation only)

**CLI:** `builder-wrp benchmark --class u --target builder [-o class_u_report.json]`.

```text
behavior:
  - runs fixed local S2 v2 scenarios (record gateways, stub_tool B7, v1 refuse flags, MSDA shell deny)
  - records wall_ms, peak_rss_mb, pass_ratio, safety flags
  - emits builder_ii.wrp.class_u_report + proof_record U + performance_measurement rows
  - proof U held only when thresholds met; still grants_authority=false; s3_enabled=false
```

## Non-authority boundaries (current)

- S2 v1 does not invoke gateways; S2 v2 gateway nodes default to **record** (no cloud provider / no shell); no Goose/deepagents.
- Does not grant promotion authority by module existence or by plan/approval alone.
- Adjoint corrections require HITL `apply-rstar-approved` to produce a versioned φ policy; still no silent live default mutation.
- Maker packages are not self-certified; Governor cert is separate for promotion decisions.
- Enabling by module existence alone is forbidden; **failing to complete the decision after G-LEAD PASS is also failure.**

## Operators (substrate)

| Wave | Operator | CLI | Kind |
| --- | --- | --- | --- |
| W0 | WorkloadClassifier | `builder-wrp classify` | `builder_ii.wrp.workload_classification` |
| W1 | CollaborationPlanner | `builder-wrp plan-collab` | `builder_ii.wrp.collaboration_topology` |
| W2 | AllocationOptimizer | `builder-wrp allocate` | `builder_ii.wrp.fleet_allocation` |
| W3 | GovernanceRouter / MSDA | `builder-wrp gate`, `msda-policy` | `msda_policy`, `msda_gate_decision` |
| W4 | ExperienceStore + \(R^*\) | `experience-init`, `adjoint`, `simulate-epochs`, `corrections-from-receipts`, `plan-rstar-apply`, `approve-rstar-apply`, `apply-rstar-approved`, `phi-policy-init` | `experience_store`, `adjoint_correction`, `phi_policy`, `rstar_apply_*` |
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
