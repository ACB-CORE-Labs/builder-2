# Target bundle artifacts

Target bundles are governed, reviewable JSON artifacts that package the selected target profile, agent profile, verification profile, dry-run bridge spec, deepagents readiness state, task context, governance limits, and suggested next steps.

They are handoff objects for planning and review. They are not runtime permissions.

## Commands

```bash
builder-bundle create --target builder --agent patch_planner --task "plan the next bounded PR"
builder-bundle create --target builder --agent patch_planner --task "plan the next bounded PR" --output .builder/artifacts/target-bundle.json
builder-bundle validate .builder/artifacts/target-bundle.json
```

For a generic repository target:

```bash
builder-bundle create --target generic --generic-repo /path/to/repo --agent repo_mapper --task "map this repo" --output .builder/artifacts/target-bundle.json
```

## Artifact contents

A target bundle includes:

- `kind: builder_ii.target_profile_bundle`
- `schema_version: 1`
- task description
- selected target profile
- selected agent profile
- default verification profile artifact for the selected target
- dry-run bridge spec artifact
- optional deepagents readiness artifact
- governance state and disabled authority limits
- suggested next commands

## Governance boundary

Target bundles do not:

- construct deepagents agents
- run models
- execute shell commands
- edit files
- mutate memory
- commit or push
- open pull requests
- authorize future runtime actions
- couple builder-II to CORE Workbench/UI

The only write performed by `builder-bundle create --output PATH` is the explicit user-provided artifact path.

## Validation

`builder-bundle validate PATH` validates only the target bundle artifact schema and disabled-authority invariants.

Validation checks:

- bundle kind and schema version
- known target and agent profile names
- embedded verification profile artifact validity
- disabled runtime/model/agent construction state
- denied tools in the embedded bridge spec
- optional deepagents dependency mode
- artifacts are not authority grants

A valid bundle is evidence for review. It is not permission to execute its suggested commands.

## Relationship to verification and bridge artifacts

Target bundles include the same verification profile artifact shape produced by:

```bash
builder-verification artifact builder_full --target builder
```

Target bundles also include the same dry-run bridge spec artifact shape produced by:

```bash
builder-bridge render patch_planner --target builder --format json
```

They also include the same optional readiness shape produced by:

```bash
builder-bridge deepagents-smoke --json
```

The bundle is the higher-level handoff object that ties those artifacts to one target, one agent profile, one verification profile, one task description, and the current governance boundary.
