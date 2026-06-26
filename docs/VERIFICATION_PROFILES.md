# Verification profiles

Verification profiles are no-runtime planning artifacts for selecting verification commands. They propose commands and required evidence, but they do not execute commands.

## Commands

```bash
builder-verification list
builder-verification list --target builder
builder-verification show builder_full --target builder --task "verify target bundle work"
builder-verification artifact builder_full --target builder --task "verify target bundle work"
builder-verification artifact builder_full --target builder --task "verify target bundle work" --output .builder/artifacts/verification-profile.json
builder-verification validate
builder-verification validate .builder/artifacts/verification-profile.json
```

## Included profiles

| Profile | Targets | Purpose |
| --- | --- | --- |
| `generic_basic` | `generic` | Propose minimal repo-local verification without assuming project-specific tooling. |
| `builder_fast` | `builder` | Propose the smallest responsible builder-II verification path. |
| `builder_full` | `builder` | Propose full builder-II foundation verification before platform-surface merges. |
| `core_smoke` | `core` | Propose conservative CORE target smoke verification without making builder-II CORE-specific. |
| `core_focused` | `core` | Propose focused CORE verification commands based on changed paths. |

## Artifact contents

A verification profile artifact includes:

- `kind: builder_ii.verification_profile`
- `schema_version: 1`
- profile name and description
- selected target and task context
- compatible targets
- proposed commands
- required evidence
- failure mode
- rollback hint
- governance boundary

## Governance boundary

Verification profiles do not:

- execute commands
- run models
- construct agents
- write files except explicit artifact output paths
- mutate memory
- commit or push
- authorize future runtime actions
- couple builder-II to CORE Workbench/UI

A valid verification profile artifact is evidence for review. It is not permission to run the proposed commands.

## Relationship to target bundles

Target bundles embed the default verification profile for the selected target:

- `generic` -> `generic_basic`
- `builder` -> `builder_full`
- `core` -> `core_smoke`

This keeps verification planning target-scoped and reviewable without making builder-II a runtime executor.
