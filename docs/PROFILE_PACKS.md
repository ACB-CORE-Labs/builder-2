# Profile packs

Profile packs are passive capability-factory manifests for composing target, agent, task, tool, context, verification, approval, projection, MCP, model-policy, handoff, and pack metadata into one reviewable substrate.

They are not a runtime, not an agent factory, not a model router, not an MCP client, and not authority to execute anything.

## Lifecycle commands

```bash
builder-profile-pack scaffold --target builder --output .builder/profile-pack/manifest.json
builder-profile-pack render .builder/profile-pack/manifest.json --output .builder/profile-pack/render-plan.json
builder-profile-pack dry-run .builder/profile-pack/manifest.json --render-plan .builder/profile-pack/render-plan.json --output .builder/profile-pack/dry-run.json
builder-profile-pack validate .builder/profile-pack/manifest.json --output .builder/profile-pack/validation-report.json
```

## Artifact kinds

| Kind | State | Purpose |
| --- | --- | --- |
| `builder_ii.profile_pack_manifest` | `PLANNED_ONLY` | Declares pack areas, entries, source refs, content hashes, and deny-by-default authority classifications. |
| `builder_ii.profile_pack_render_plan` | `RENDERED_ONLY` | Plans deterministic passive render outputs for manifest entries. |
| `builder_ii.profile_pack_dry_run` | `DRY_RUN_ONLY` | Shows what would render and proves every step remains non-executing. |
| `builder_ii.profile_pack_validation_report` | `VALIDATED_ONLY` | Records validation results without converting validity into promotion. |
| `builder_ii.profile_pack` | `PACKED_ONLY` | Binds lifecycle artifacts as passive refs for index and chain verification. |

## Required areas

Every manifest must include these areas:

- target profiles
- agent profiles
- subagent profiles
- task profiles
- tool profiles
- context definitions
- verification profiles
- approval policies
- Goose projection stubs
- deepagents projection stubs
- MCP inventory/policy stubs
- handoff profiles
- packs

The scaffold also includes a model-policy stub area because model policies must not silently become model calls.

## Fail-closed rules

Validation fails when:

- an artifact kind, pack area, or profile kind is unknown;
- an entry id is duplicated;
- `schema_version` is missing or wrong;
- `authority_classification` is missing or does not match the profile kind;
- required source refs or SHA-256 content hashes are missing;
- a tool profile does not default to `denied`;
- MCP entries are anything beyond inventory/policy stubs;
- Goose projections claim to start Goose;
- deepagents projections claim to construct agents or delegate;
- model policies claim to call models;
- verification profiles claim to execute commands;
- handoff profiles claim verification evidence;
- planned, rendered, dry-run, or validated artifacts claim to be executed, authorized, or promoted.

## Authority boundary

Profile packs do not:

- start Goose;
- construct deepagents or subagents;
- call models;
- connect to MCP servers;
- call MCP tools;
- execute shell commands;
- run verification commands;
- write target repository source;
- mutate memory;
- approve HITL gates;
- create verification evidence;
- promote capabilities.

A valid profile pack is structured review evidence only. It can help the operator see the capability geometry, but it does not grant permission to use those capabilities.

## Verification

```bash
uv run pytest tests/test_profile_pack.py tests/test_profile_pack_cli.py -q
uv run pytest tests/test_artifact_index_records.py tests/test_artifact_chain_verification.py tests/test_command_authority.py -q
```
