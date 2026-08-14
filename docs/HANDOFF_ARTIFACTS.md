# Handoff artifacts

Handoff artifacts are governed JSON records for continuity between builder-II sessions, reviews, Goose sessions, and future runtime steps.

They are review objects only. They do not mutate a notes vault by default.

## Commands

```bash
builder-notes handoff --target builder --agent handoff_scribe --task "Implement quality gates" --summary "Added bundle and notes support"
builder-notes handoff --target builder --agent handoff_scribe --task "Implement quality gates" --summary "Added bundle and notes support" --next "Run quality plan" --output .builder/artifacts/handoff.json
builder-notes validate .builder/artifacts/handoff.json
```

Repeatable fields:

```bash
--next "next step"
--blocker "known blocker"
--verification "verification evidence"
```

## Artifact contents

A handoff artifact includes:

- `kind: builder_ii.handoff_artifact`
- `schema_version: 1`
- creation timestamp
- target
- agent profile
- task
- summary
- next steps
- blockers
- verification evidence
- governance boundary

## Governance boundary

Handoff artifacts do not:

- mutate the notes vault
- run models
- construct agents
- execute shell commands
- edit source files
- commit or push
- open pull requests
- authorize future runtime actions
- couple builder-II to CORE Workbench/UI

The only write performed by `builder-notes handoff --output PATH` is the explicit output path.

## Validation

`builder-notes validate PATH` validates the handoff schema and disabled-action invariants.

Validation checks:

- kind and schema version
- valid target and agent profile names
- required task and summary fields
- list-valued next steps, blockers, and verification evidence
- disabled runtime, model, agent, shell, and notes-vault mutation fields

A valid handoff is evidence for review. It is not permission to execute any suggested next step.

## Relationship to the operating loop

```bash
builder-context pack --target builder --changed --task "..."
builder-bundle create --target builder --agent patch_planner --task "..." --output .builder/artifacts/target-bundle.json
builder-verification artifact builder_full --target builder --task "..." --output .builder/artifacts/verification-profile.json
builder-notes handoff --target builder --agent handoff_scribe --task "..." --summary "..." --output .builder/artifacts/handoff.json
```
