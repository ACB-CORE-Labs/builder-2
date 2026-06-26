# builder-II roadmap

builder-II is the generic governed local agent/developer platform.

It is not CORE, not CORE Workbench/UI, and not a second CORE runtime. CORE remains a target profile only.

## Current status

builder-II is complete on the no-runtime governance foundation once the target bundle artifact surface is merged.

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

The current foundation is intentionally no-runtime:

- no autonomous source writes
- no shell execution as an agent capability
- no deepagents construction
- no model execution through the bridge
- no memory mutation
- no commit/push automation
- no CORE Workbench/UI coupling

## Current operating loop

```bash
builder setup
builder doctor
builder-targets validate
builder-agent validate
builder-context pack --target builder --changed --task "..."
builder-bundle create --target builder --agent patch_planner --task "..." --output .builder/artifacts/target-bundle.json
builder-bundle validate .builder/artifacts/target-bundle.json
builder-bridge render patch_planner --target builder --format json --output .builder/artifacts/bridge-spec.json
builder-bridge validate-artifact .builder/artifacts/bridge-spec.json
```

## Remaining extension surfaces

These are not required for the governance foundation, but remain planned thin extensions:

- verification profile registry
- quality gate command surface
- notes/handoff artifact commands
- prompt/eval lanes
- read-only runner design spec
- later HITL-gated runtime candidate

Each future capability must satisfy the capability promotion rule before it can move beyond disabled/spec/artifact/validation states.
