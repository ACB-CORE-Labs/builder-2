# builder-II roadmap

builder-II is a generic governed local agent/developer platform.

It is not CORE, not CORE Workbench/UI, and not a second CORE runtime. CORE remains a target profile only.

## Current status

builder-II is complete on the no-runtime governance foundation. Verification profiles, handoff artifacts, quality gate artifacts, research planning artifacts, Goose session manifests, and governed deepagents policy artifacts remain artifact-only. Goose runtime behavior and deepagents runtime behavior are specified as design boundaries, not enabled.

Completed foundation surfaces:

- generic platform core
- explicit target profiles: `generic`, `builder`, `core`
- generic agent profiles
- context pack artifacts
- optional deepagents bridge specs
- optional deepagents readiness smoke
- readiness and bridge spec artifact output
- bridge artifact validation
- capability promotion registry
- target bundle artifacts
- verification profile registry
- handoff artifact commands
- quality gate artifacts
- research planning artifacts
- Goose runtime design spec
- runtime promotion contract
- Goose session manifest artifacts
- governed deepagents policy artifacts

The current foundation is intentionally no-runtime:

- no autonomous source writes
- no shell execution as an agent capability
- no deepagents construction
- no model execution through the bridge
- no command execution from quality gates
- no search, MCP, or source collection from research plans
- no Goose runtime activation from specs or manifests
- no memory mutation
- no commit/push automation
- no CORE Workbench/UI coupling

## Current operating loop

```bash
builder setup
builder doctor
builder-targets validate
builder-agent validate
builder-verification validate
builder-context pack --target builder --changed --task "..."
builder-verification artifact builder_full --target builder --task "..." --output .builder/artifacts/verification-profile.json
builder-verification validate .builder/artifacts/verification-profile.json
builder-bundle create --target builder --agent patch_planner --task "..." --output .builder/artifacts/target-bundle.json
builder-bundle validate .builder/artifacts/target-bundle.json
builder-research plan --target generic --profile research_planner --task "..." --output .builder/artifacts/research-plan.json
builder-research validate .builder/artifacts/research-plan.json
builder-quality plan --target builder --profile builder_full --task "..." --output .builder/artifacts/quality-gate.json
builder-quality validate .builder/artifacts/quality-gate.json
builder-notes handoff --target builder --agent handoff_scribe --task "..." --summary "..." --output .builder/artifacts/handoff.json
builder-notes validate .builder/artifacts/handoff.json
builder-goose manifest --target builder --agent patch_planner --mode read_only --task "..." --output .builder/artifacts/goose-session.json
builder-goose validate .builder/artifacts/goose-session.json
builder-deepagents policy --target builder --task "..." --output .builder/artifacts/deepagents-policy.json
builder-deepagents validate .builder/artifacts/deepagents-policy.json
builder-bridge render patch_planner --target builder --format json --output .builder/artifacts/bridge-spec.json
builder-bridge validate-artifact .builder/artifacts/bridge-spec.json
```

Every command above either validates configuration, renders a reviewable plan/specification, or writes an explicit artifact path requested by the operator. None of these commands grants runtime authority.

## Remaining extension surfaces

These are not required for the governance foundation, but remain planned thin extensions:

- prompt/eval lanes
- read-only runner candidate
- runtime audit artifacts
- command proposal artifacts
- HITL approval artifacts
- approved verification execution candidate
- patch proposal artifacts
- approved patch application candidate

Each future capability must satisfy the capability promotion rule before it can move beyond disabled/spec/artifact/validation states.

## Performance and integration priorities

See `docs/plan/PERFORMANCE_AND_EFFICIENCY_AMENDMENT.md` for the detailed amendment.

The amendment adds three first-class candidate tracks without promoting runtime behavior:

- Rust-backed artifact validation and processing, gated by measurement and parity evidence.
- MLX + UMA context compression, restricted to provenance-preserving review artifacts.
- Model routing and hybrid execution policy, introduced first as an artifact surface rather than hidden automatic model calls.

These tracks run alongside the existing runtime integration phases. They must preserve the no-runtime governance foundation, the capability promotion rule, target-profile boundaries, and the separation between builder-II and CORE Workbench/UI.

## Design-halt RFCs

During implementation halts, builder-II may advance through design-only RFCs that clarify future artifact contracts without enabling runtime behavior.

Current RFCs:

- `docs/plan/ARTIFACT_MEMORY_RFC.md` — artifact graph memory, memory atom envelope, reconstruction posture, and summary boundaries.
- `docs/plan/DEEPAGENTS_WORK_ARTIFACTS_RFC.md` — deepagents plan/assignment/result/review/gate artifacts before any deepagents runtime construction.
- `docs/plan/RUST_VALIDATION_SPIKE.md` — measurement-first Rust validation spike plan with Python reference parity.
- `docs/plan/GOOSE_DEEPAGENTS_MCP_SEAM.md` — Goose as operator runtime, deepagents as governed inner harness, and MCP as policy-gated integration seam.
- `docs/plan/MCP_POLICY_ARTIFACT_RFC.md` — deny-by-default MCP policy artifact for tools, resources, prompts, roots, sampling, elicitation, auth, limits, and result handling.
- `docs/plan/MCP_TOOL_INVENTORY_RFC.md` — MCP inventory artifact, tool/resource/prompt hashes, risk classification, and change detection before policy or invocation.

These RFCs are not implementation authority. They do not enable memory mutation, deepagents construction, Rust dependencies, shell execution, command execution, model calls, source mutation, MCP connection, MCP tool execution, source collection, or Goose runtime activation.

## Near-term order

1. Keep documentation and metadata aligned with the generic-first platform identity.
2. Treat Goose session manifests and governed deepagents policy artifacts as complete artifact-only infrastructure.
3. Design the read-only runtime candidate and runtime audit artifact schema.
4. Add cross-layer compatibility and denied-action tests before runtime promotion.
5. Introduce model routing as a policy artifact before any automatic routing behavior.
6. Add measured Rust and MLX performance candidates only where evidence shows value.
7. Treat MCP as a policy/inventory/audit seam before any server connection or tool invocation.
