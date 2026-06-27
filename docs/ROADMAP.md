# builder-II roadmap

CORE builder-II is CORE's governed engineering platform for local agent-assisted software development.

It is a CORE product and brand extension, but it is not the CORE runtime, not CORE Workbench/UI, and not a second CORE runtime. CORE remains a first-class target profile and brand lineage; builder-II remains generic-first in architecture.

The governing product doctrine is captured in [`docs/MANIFESTO.md`](MANIFESTO.md), [`docs/adrs/ADR-0001-core-builder-ii-governed-engineering-extension.md`](adrs/ADR-0001-core-builder-ii-governed-engineering-extension.md), and [`docs/adrs/ADR-0002-builder-convention-layer-over-codename-goose.md`](adrs/ADR-0002-builder-convention-layer-over-codename-goose.md).

## Current status

builder-II is complete on the no-runtime governance foundation. Verification profiles, handoff artifacts, quality gate artifacts, research planning artifacts, Goose session manifests, Goose read-only candidate audit artifacts, bounded read-only inspection artifacts, governed deepagents policy artifacts, and deepagents dependency-readiness artifacts remain artifact-only. Goose runtime behavior and deepagents runtime behavior are specified as design boundaries, not enabled.

Completed foundation surfaces:

- CORE-born product positioning with generic-first architecture
- Builder's Signet doctrine: Mechanical Sympathy, Semantic Rigor, and The Third Door
- builder convention-layer doctrine over Codename Goose
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
- Goose read-only candidate audit artifacts
- bounded read-only inspection artifacts
- governed deepagents policy artifacts
- deepagents dependency-readiness artifacts

The current foundation is intentionally no-runtime:

- no autonomous source writes
- no shell execution as an agent capability
- no deepagents construction
- no model execution through the bridge
- no command execution from quality gates
- no search, MCP, or source collection from research plans
- no Goose runtime activation from specs or manifests
- no repository inspection from Goose read-only audit candidates
- no arbitrary repository inspection; bounded inspection requires explicit operator paths
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
builder-goose readonly-audit .builder/artifacts/goose-session.json --output .builder/artifacts/goose-readonly-audit.json
builder-goose validate-audit .builder/artifacts/goose-readonly-audit.json
builder-goose inspect-readonly .builder/artifacts/goose-session.json --read-file README.md --output .builder/artifacts/goose-readonly-inspection.json
builder-goose validate-inspection .builder/artifacts/goose-readonly-inspection.json
builder-deepagents policy --target builder --task "..." --output .builder/artifacts/deepagents-policy.json
builder-deepagents validate .builder/artifacts/deepagents-policy.json
builder-deepagents readiness --mode metadata_only --output .builder/artifacts/deepagents-readiness.json
builder-deepagents validate-readiness .builder/artifacts/deepagents-readiness.json
builder-bridge render patch_planner --target builder --format json --output .builder/artifacts/bridge-spec.json
builder-bridge validate-artifact .builder/artifacts/bridge-spec.json
```

Every command above either validates configuration, renders a reviewable plan/specification, or writes an explicit artifact path requested by the operator. None of these commands grants runtime authority.

## Remaining extension surfaces

These are not required for the governance foundation, but remain planned thin extensions:

- governed engineering scenario tests
- session configuration spine artifact
- Codename Goose projection artifact
- builder command wrapper around Goose projection
- agent/subagent orchestration plan artifact
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

1. Keep documentation and metadata aligned with CORE-born, generic-first platform identity.
2. Treat Goose session manifests, Goose read-only candidate audits, bounded read-only inspection artifacts, governed deepagents policy artifacts, and dependency-readiness artifacts as complete artifact-only infrastructure.
3. Add governed engineering scenario tests that prove end-to-end session propagation across target/profile resolution, Goose session manifest, planned verification report, handoff/receipt, and artifact chain verification.
4. Add a session configuration spine artifact that resolves target/provider/model/agent/authority/context/verification into one reviewable record.
5. Add a Codename Goose projection artifact that renders env/recipe/context/session fields without launching Goose.
6. Add builder command wrappers around the projection layer.
7. Add agent/subagent orchestration plan artifacts before any subagent runtime construction.
8. Design the read-only runtime candidate and runtime audit artifact schema.
9. Add cross-layer compatibility and denied-action tests before runtime promotion.
10. Introduce model routing as a policy artifact before any automatic routing behavior.
11. Add measured Rust and MLX performance candidates only where evidence shows value.
12. Treat MCP as a policy/inventory/audit seam before any server connection or tool invocation.
