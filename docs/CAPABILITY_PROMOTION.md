# Capability promotion registry

builder-II capabilities must move through explicit, documented promotion states. A capability is never enabled merely because code exists, a dependency imports, an artifact validates, or an agent profile can be rendered.

This registry records current artifact, bridge, bundle, and verification-profile capabilities and the gates required before any future runtime promotion.

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

## Current verification profile state

| Property | Current value |
| --- | --- |
| Command surface | `builder-verification list`, `show`, `artifact`, `validate` |
| Runtime execution | `disabled` |
| Model execution | `disabled` |
| Agent construction | `disabled` |
| Command execution | `disabled` |
| File writes | only explicit user-provided artifact output path |
| Shell execution | `disabled` |
| Artifact authority | evidence only, never permission |
| Current maximum state | `validation_only` |

Verification profiles propose target-scoped verification commands as reviewable text. They do not run the proposed commands.

## Completed gates for validation-only state

| Gate | Status | Evidence |
| --- | --- | --- |
| Docs | complete | `docs/BRIDGE.md`, `docs/TARGET_BUNDLES.md`, `docs/VERIFICATION_PROFILES.md`, this registry |
| Tests | complete | bridge, bundle, and verification profile artifact tests |
| Command surface | complete | bridge, bundle, and verification profile CLI commands |
| Failure mode | complete | validation errors and nonzero CLI exit for invalid artifacts |
| Output artifact | complete | readiness, bridge spec, target bundle, and verification profile JSON artifacts |
| Verification path | complete | pytest plus CLI artifact validation commands |
| Human approval boundary | not complete for runtime | no runtime behavior is promoted |
| Rollback path | not complete for runtime | no runtime behavior is promoted |

## Required gates before runtime promotion

Before builder-II may promote any bridge behavior beyond `validation_only`, a future PR must provide all of the following:

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

## Current bridge, bundle, and verification commands and states

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
| `builder-verification list` | `spec_only` | none |
| `builder-verification show PROFILE` | `spec_only` | none |
| `builder-verification artifact PROFILE` | `artifact_only` | none |
| `builder-verification artifact PROFILE --output PATH` | `artifact_only` | writes only the explicit artifact path |
| `builder-verification validate PATH` | `validation_only` | reads and validates only |

## Non-promotion statement

Validated artifacts are evidence, not authority. A valid artifact proves only that the artifact matches the current schema and disabled-runtime invariants. It does not authorize model execution, agent construction, command execution, file mutation, shell execution, memory mutation, commits, pushes, or pull request creation.
