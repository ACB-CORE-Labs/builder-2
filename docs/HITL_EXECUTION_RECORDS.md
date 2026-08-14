# HITL Execution Request & Receipt Records

## Platform Identity & Scope

builder-II is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench/UI/UX, and not a second CORE runtime. CORE is only a target profile.

## Overview

This document defines two design/record artifacts for the governed Human-In-The-Loop (HITL) command execution path:

- **`builder_ii.hitl_execution_request`** — records operator intent to execute a previously proposed, approved, and pre-flighted command.
- **`builder_ii.hitl_execution_receipt`** — records the outcome (or absence) of execution.

**These are design/record artifacts only. They do not execute commands. They do not grant authority.**

## Current State

Both artifact types are **design-only** templates:

| Property              | Execution Request        | Execution Receipt       |
|-----------------------|--------------------------|-------------------------|
| `current_state`       | `REQUEST_RECORDED_ONLY`  | `RECEIPT_TEMPLATE_ONLY` |
| `runtime_execution`   | `DISABLED`               | —                       |
| `execution_state`     | —                        | `NOT_EXECUTED`          |
| `artifact_is_authority` | `false`                | `false`                 |

## Execution Request Fields

| Field                      | Type     | Description                                          |
|----------------------------|----------|------------------------------------------------------|
| `kind`                     | string   | `builder_ii.hitl_execution_request`                  |
| `schema_version`           | integer  | Schema version (currently `1`)                       |
| `target`                   | object   | Target profile (name, repo, description)             |
| `command_proposal_ref`     | string   | Reference to the originating command proposal        |
| `approval_record_ref`      | string   | Reference to the governing approval record           |
| `preflight_record_ref`     | string   | Reference to the completed preflight record          |
| `requested_by`             | string   | Operator identity                                    |
| `requested_at`             | string   | ISO 8601 timestamp of the request                    |
| `explicit_operator_intent` | string   | Operator's stated intent for the execution           |
| `command_preview`          | string   | Human-readable preview of the command to be executed |
| `current_state`            | string   | `REQUEST_RECORDED_ONLY`                              |
| `runtime_execution`        | string   | `DISABLED`                                           |
| `artifact_is_authority`    | boolean  | `false`                                              |

## Execution Receipt Fields

| Field                | Type        | Description                                     |
|----------------------|-------------|-------------------------------------------------|
| `kind`               | string      | `builder_ii.hitl_execution_receipt`              |
| `schema_version`     | integer     | Schema version (currently `1`)                   |
| `target`             | object      | Target profile (name, repo, description)         |
| `request_ref`        | string      | Reference to the execution request               |
| `execution_state`    | string      | `NOT_EXECUTED`                                   |
| `exit_code`          | null        | Always null — no execution has occurred          |
| `stdout_ref`         | null        | Always null — no execution has occurred          |
| `stderr_ref`         | null        | Always null — no execution has occurred          |
| `started_at`         | null        | Always null — no execution has occurred          |
| `completed_at`       | null        | Always null — no execution has occurred          |
| `performed_actions`  | list (empty)| Always empty — no execution has occurred         |
| `current_state`      | string      | `RECEIPT_TEMPLATE_ONLY`                          |
| `artifact_is_authority` | boolean  | `false`                                          |

## Governance Block

Both artifact types carry a governance block that explicitly denies all forms of runtime execution:

- Shell execution: **DISABLED**
- Subprocess execution: **DISABLED**
- Command execution: **DISABLED**
- Model execution: **DISABLED**
- Source writes: **DISABLED**
- Git mutation: **DISABLED**
- Commit/push: **DISABLED**
- Network/MCP execution: **DISABLED**
- Goose runtime activation: **DISABLED**
- deepagents runtime: **DISABLED**
- CORE Workbench coupling: **NONE**
- `artifact_is_authority`: **false**

## Future Execution Path

Future promotion to active runtime execution requires the following governed chain, **all** of which must be satisfied before any command runs:

1. **Command proposal** — structured description of the exact command
2. **Approval** — explicit human authorization boundary
3. **Preflight** — environment readiness and risk assessment
4. **Explicit execution request** — intentional invocation bound to approved state
5. **Execution receipt** — capture of exit code, stdout, stderr, timing
6. **Postflight/handoff** — audit indexing and verification
7. **Rollback** — reversal path if execution produces undesirable results
8. **Verification** — confirmation that the outcome matches expectations

Until all gates are implemented, tested, documented, and approved, **shell/model/subprocess/git/network/Goose/deepagents execution remains disabled**.

## Validation Rules

- A valid execution request must include non-empty `command_proposal_ref`, `approval_record_ref`, and `preflight_record_ref`.
- A valid execution receipt must have `execution_state` set to `NOT_EXECUTED` and all result fields (`exit_code`, `stdout_ref`, `stderr_ref`, `started_at`, `completed_at`) set to `null`.
- Both artifacts fail validation if the governance block claims execution is enabled.
- Both artifacts fail validation if `artifact_is_authority` is `true`.
- Both artifacts fail validation if CORE Workbench coupling is anything other than `NONE`.
