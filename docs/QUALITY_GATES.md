# Quality gate artifacts

Quality gate artifacts are governed JSON plans that bind a target to a verification profile, required evidence, merge blockers, rollback requirements, and approval expectations.

They do not run tests or execute commands. They are reviewable gates that future Goose/runtime phases must satisfy before merge or promotion.

## Commands

```bash
builder-quality plan --target builder --profile builder_full --task "Implement quality gates"
builder-quality plan --target builder --profile builder_full --task "Implement quality gates" --output .builder/artifacts/quality-gate.json
builder-quality validate .builder/artifacts/quality-gate.json
```

Repeatable fields:

```bash
--blocker "missing full suite"
--rollback "record recovery path"
```

## Artifact contents

A quality gate artifact includes:

- `kind: builder_ii.quality_gate`
- `schema_version: 1`
- selected target
- task
- embedded verification profile artifact
- required command proposals
- required evidence
- merge blockers
- rollback requirements
- approval requirement
- governance boundary

## Governance boundary

Quality gate artifacts do not:

- execute commands
- run tests
- run models
- construct agents
- execute shell commands
- edit source files
- commit or push
- authorize future runtime actions
- couple builder-II to CORE Workbench/UI

The only write performed by `builder-quality plan --output PATH` is the explicit output path.

## Validation

`builder-quality validate PATH` validates the quality gate schema and disabled-action invariants.

Validation checks:

- gate kind and schema version
- valid target
- embedded verification profile artifact validity
- profile compatibility with target
- non-empty required commands, evidence, blockers, and rollback requirements
- approval required
- disabled runtime, model, agent, command, and shell execution fields

A valid quality gate is evidence for review. It is not permission to run any command.

## Relationship to the operating loop

```bash
builder-verification artifact builder_full --target builder --task "..." --output .builder/artifacts/verification-profile.json
builder-quality plan --target builder --profile builder_full --task "..." --output .builder/artifacts/quality-gate.json
builder-quality validate .builder/artifacts/quality-gate.json
builder-notes handoff --target builder --agent handoff_scribe --task "..." --summary "..." --output .builder/artifacts/handoff.json
```

Future runtime modes may consume quality gates, but the gate itself never grants execution authority.
