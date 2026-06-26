# Capability promotion registry

builder-II capabilities must move through explicit, documented promotion states. A capability is never enabled merely because code exists, a dependency imports, an artifact validates, or an agent profile can be rendered.

This registry records current artifact and bridge capabilities and the gates required before any future runtime promotion.

## Promotion states

| State | Meaning |
| --- | --- |
| `unavailable` | No supported command, artifact, or implementation exists. |
| `spec_only` | builder-II can render a specification, prompt, plan, or profile, but cannot run it. |
| `smoke_only` | builder-II can inspect import/readiness status without constructing or running the dependency. |
| `artifact_only` | builder-II can emit an explicit output artifact requested by the user. |
| `validation_only` | builder-II can validate artifact schema and governance invariants, but cannot execute artifact contents. |
| `read_only_runtime_candidate` | A future design candidate for read-only runtime behavior exists, but it is not enabled. |
| `hitl_runtime_candidate` | A future HITL-gated runtime design candidate exists, but it is not enabled. |
| `enabled` | The capability is enabled by documented command surface, tests, failure modes, human approval boundary, output artifact, rollback path, and verification path. |

## Capability promotion rule

A capability can move from disabled to enabled only when it has all of the following:

- docs
- tests
- command surface
- failure mode
- human approval boundary
- output artifact
- rollback path
- verification path

Missing any item keeps the capability below `enabled`.

## Current deepagents bridge state

| Property | Current value |
| --- | --- |
| Dependency mode | `optional` |
| Runtime execution | `disabled` |
| Model execution | `disabled` |
| File writes | `disabled` except explicit user-provided artifact output paths |
| Shell execution | `disabled` |
| Agent construction | `disabled` |
| Deepagents construction | `disabled` |
| CORE Workbench/UI coupling | none |
| Current maximum state | `validation_only` |

The deepagents bridge currently supports:

- optional import/readiness smoke reporting
- readiness artifact output by explicit user-provided path
- dry-run bridge spec artifact output by explicit user-provided path
- artifact validation for supported builder-II bridge artifact schemas

The deepagents bridge does not support:

- constructing deepagents agents
- running models
- executing shell commands
- granting file-edit/write authority
- mutating durable memory
- treating artifact contents as permission grants
- coupling builder-II to CORE Workbench/UI behavior

## Current target bundle state

| Property | Current value |
| --- | --- |
| Command surface | `builder-bundle create`, `builder-bundle validate` |
| Runtime execution | `disabled` |
| Model execution | `disabled` |
| Agent construction | `disabled` |
| File writes | only explicit user-provided bundle output path |
| Shell execution | `disabled` |
| Artifact authority | evidence only, never permission |
| Current maximum state | `validation_only` |

Target bundles currently support:

- packaging one target profile
- packaging one agent profile
- embedding a dry-run bridge spec artifact
- embedding optional deepagents readiness state
- recording disabled governance limits
- validating bundle schema and no-runtime invariants

Target bundles do not execute their suggested commands.

## Completed gates for validation-only state

| Gate | Status | Evidence |
| --- | --- | --- |
| Docs | complete | `docs/BRIDGE.md`, `docs/TARGET_BUNDLES.md`, this registry |
| Tests | complete | bridge smoke, artifact output, bundle output, and validation tests |
| Command surface | complete | `builder-bridge doctor`, `deepagents-smoke`, `render`, `validate-artifact`; `builder-bundle create`, `builder-bundle validate` |
| Failure mode | complete | validation errors and nonzero CLI exit for invalid artifacts |
| Output artifact | complete | readiness, dry-run bridge spec, and target bundle JSON artifacts |
| Verification path | complete | pytest plus CLI smoke/render/validate/bundle commands |
| Human approval boundary | not complete for runtime | no runtime behavior is promoted |
| Rollback path | not complete for runtime | no runtime behavior is promoted |

## Required gates before runtime promotion

Before builder-II may promote any deepagents bridge behavior beyond `validation_only`, a future PR must provide all of the following:

- design document for read-only runtime behavior
- explicit HITL approval boundary
- rollback path
- runtime sandbox contract
- no-write enforcement tests
- no-shell enforcement tests
- failure-mode tests for denied runtime actions
- audit artifact for runtime attempts
- command surface that defaults to dry-run/disabled
- clear statement that CORE remains a target profile, not builder-II platform identity
- clear statement that CORE Workbench/UI remains separate

## Current bridge and bundle commands and states

| Command | State | Runtime authority |
| --- | --- | --- |
| `builder-bridge doctor` | `smoke_only` | none |
| `builder-bridge deepagents-smoke` | `smoke_only` | none |
| `builder-bridge deepagents-smoke --json` | `artifact_only` | none |
| `builder-bridge deepagents-smoke --output PATH` | `artifact_only` | writes only the explicit artifact path |
| `builder-bridge render PROFILE --target TARGET` | `spec_only` | none |
| `builder-bridge render PROFILE --target TARGET --format json` | `artifact_only` | none |
| `builder-bridge render PROFILE --target TARGET --format json --output PATH` | `artifact_only` | writes only the explicit artifact path |
| `builder-bridge validate-artifact PATH` | `validation_only` | reads and validates only |
| `builder-bundle create --target TARGET --agent PROFILE` | `artifact_only` | none |
| `builder-bundle create --target TARGET --agent PROFILE --output PATH` | `artifact_only` | writes only the explicit artifact path |
| `builder-bundle validate PATH` | `validation_only` | reads and validates only |

## Non-promotion statement

Validated artifacts are evidence, not authority. A valid artifact proves only that the artifact matches the current schema and disabled-runtime invariants. It does not authorize model execution, agent construction, file mutation, shell execution, memory mutation, commits, pushes, or pull request creation.
