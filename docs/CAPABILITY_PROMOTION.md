# Capability promotion registry

builder-II capabilities must move through explicit, documented promotion states. A capability is never enabled merely because code exists, a dependency imports, an artifact validates, or an agent profile can be rendered.

This registry records current artifact, bridge, bundle, verification, quality, handoff, research, and Goose-session capabilities and the gates required before any future runtime promotion.

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

## Current platform state

| Property | Current value |
| --- | --- |
| Runtime execution | `disabled` |
| Goose runtime start | `disabled` |
| Model execution through bridge | `disabled` |
| File writes | `disabled` except explicit user-provided artifact output paths |
| Shell execution | `disabled` |
| Command execution from artifacts | `disabled` |
| Agent construction | `disabled` |
| Deepagents construction | `disabled` |
| Memory mutation | `disabled` |
| Commit/push automation | `disabled` |
| Pull request automation | `disabled` |
| Search/MCP/source collection | `disabled` |
| CORE Workbench/UI coupling | none |
| Current maximum state | `validation_only` |

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

## Current artifact surfaces

| Surface | Command surface | State | Runtime authority |
| --- | --- | --- | --- |
| readiness artifact | `builder-bridge deepagents-smoke --output PATH` | `artifact_only` | none |
| bridge spec | `builder-bridge render`, `builder-bridge validate-artifact` | `validation_only` | none |
| target bundle | `builder-bundle create`, `builder-bundle validate` | `validation_only` | none |
| verification profile | `builder-verification artifact`, `builder-verification validate` | `validation_only` | none |
| quality gate | `builder-quality plan`, `builder-quality validate` | `validation_only` | none |
| handoff | `builder-notes handoff`, `builder-notes validate` | `validation_only` | none |
| research plan | `builder-research plan`, `builder-research validate` | `validation_only` | none |
| Goose session manifest | `builder-goose manifest`, `builder-goose validate` | `validation_only` | none |

All listed artifact surfaces are evidence and review objects. They do not execute their contents.

## Artifact authority rule

Validated artifacts are evidence, not authority. A valid artifact proves only that the artifact matches the current schema and disabled-runtime invariants.

A valid artifact does not authorize:

- model execution;
- agent construction;
- deepagents construction;
- Goose runtime start;
- command execution;
- file mutation;
- shell execution;
- source collection;
- web search;
- MCP execution;
- memory mutation;
- commits;
- pushes;
- pull request creation.

## Completed gates for validation-only state

| Gate | Status | Evidence |
| --- | --- | --- |
| Docs | complete | `docs/BRIDGE.md`, `docs/TARGET_BUNDLES.md`, `docs/VERIFICATION_PROFILES.md`, `docs/QUALITY_GATES.md`, `docs/HANDOFF_ARTIFACTS.md`, `docs/RESEARCH_PLANS.md`, `docs/GOOSE_SESSION.md`, this registry |
| Tests | complete | bridge, bundle, verification profile, quality gate, handoff, research plan, and Goose session artifact tests |
| Command surface | complete | bridge, bundle, verification, quality, notes, research, and Goose CLI commands |
| Failure mode | complete | validation errors and nonzero CLI exit for invalid artifacts |
| Output artifact | complete | readiness, bridge spec, target bundle, verification profile, quality gate, handoff, research plan, and Goose session JSON artifacts |
| Verification path | complete | pytest plus CLI artifact validation commands |
| Human approval boundary | not complete for runtime | no runtime behavior is promoted |
| Rollback path | not complete for runtime | no runtime behavior is promoted |

## Required gates before runtime promotion

Before builder-II may promote any behavior beyond `validation_only`, a future PR must provide all of the following:

- design document for the specific runtime behavior;
- explicit runtime mode;
- explicit HITL approval boundary;
- rollback path;
- runtime sandbox or target-boundary contract;
- no-write enforcement tests;
- no-shell enforcement tests;
- failure-mode tests for denied runtime actions;
- audit artifact for runtime attempts;
- command surface that defaults to dry-run/disabled where applicable;
- target profile compatibility checks;
- verification profile compatibility checks;
- quality gate compatibility checks;
- clear recovery path after interruption;
- clear statement that CORE remains a target profile, not builder-II platform identity;
- clear statement that CORE Workbench/UI remains separate.

## Current commands and states

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
| `builder-quality plan --target TARGET --profile PROFILE` | `artifact_only` | none |
| `builder-quality plan --target TARGET --profile PROFILE --output PATH` | `artifact_only` | writes only the explicit artifact path |
| `builder-quality validate PATH` | `validation_only` | reads and validates only |
| `builder-notes handoff --target TARGET --agent PROFILE` | `artifact_only` | none |
| `builder-notes handoff --target TARGET --agent PROFILE --output PATH` | `artifact_only` | writes only the explicit artifact path |
| `builder-notes validate PATH` | `validation_only` | reads and validates only |
| `builder-research plan --target TARGET --profile PROFILE` | `artifact_only` | none |
| `builder-research plan --target TARGET --profile PROFILE --output PATH` | `artifact_only` | writes only the explicit artifact path |
| `builder-research validate PATH` | `validation_only` | reads and validates only |
| `builder-goose manifest --target TARGET --agent PROFILE` | `artifact_only` | none |
| `builder-goose manifest --target TARGET --agent PROFILE --output PATH` | `artifact_only` | writes only the explicit artifact path |
| `builder-goose validate PATH` | `validation_only` | reads and validates only |

## Non-promotion statement

No current artifact surface authorizes model execution, agent construction, command execution, file mutation, shell execution, memory mutation, commits, pushes, pull request creation, Goose runtime activation, deepagents construction, source collection, web search, or MCP execution.
