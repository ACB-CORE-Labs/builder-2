# Rollback Artifacts

## Platform Identity & Scope

builder-II is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench/UI/UX, and not a second CORE runtime. CORE is only a target profile.

## Overview

Rollback artifacts are design-only governance records. They model future rollback readiness without performing rollback.

This document defines two artifact kinds:

- `builder_ii.rollback_plan`
- `builder_ii.rollback_receipt`

These artifacts do not execute rollback, do not mutate files, do not run shell commands, do not perform Git operations, do not activate Goose runtime, and do not activate deepagents runtime.

## Rollback Plan

A rollback plan records the intended rollback strategy and the related artifacts that would be needed for a future human-gated rollback workflow.

Required fields include:

- `kind`: `builder_ii.rollback_plan`
- `schema_version`: `1`
- `target`: target profile object
- `related_artifact_refs`: non-empty list of non-empty strings
- `rollback_strategy`: non-empty string
- `operator_note`: string
- `current_state`: `PLAN_RECORDED_ONLY`
- `runtime_execution`: `DISABLED`
- `performed_actions`: empty list
- `artifact_is_authority`: `false`
- `governance`: disabled governance block

## Rollback Receipt

A rollback receipt records that rollback has not executed. It is a template-only record until a future promoted capability defines active rollback execution.

Required fields include:

- `kind`: `builder_ii.rollback_receipt`
- `schema_version`: `1`
- `target`: target profile object
- `rollback_plan_ref`: non-empty string
- `rollback_state`: `NOT_EXECUTED`
- `performed_actions`: empty list
- `current_state`: `RECEIPT_TEMPLATE_ONLY`
- `artifact_is_authority`: `false`
- `governance`: disabled governance block

## Governance

Both artifacts deny all runtime authority:

- `runtime_execution`: `DISABLED`
- `shell_execution`: `DISABLED`
- `model_execution`: `DISABLED`
- `source_writes`: `DISABLED`
- `git_mutation`: `DISABLED`
- `network_access`: `DISABLED`
- `goose_runtime_activation`: `DISABLED`
- `deepagents_runtime`: `DISABLED`
- `artifact_is_authority`: `false`
- `core_workbench_coupling`: `NONE`

These records follow the same governance posture as the HITL, voice, and read-only inspection artifacts: artifacts may describe future governed behavior, but it does not grant authority or execute behavior.

## Current Limits

Current rollback artifacts are governance records only.

They do not:

- execute rollback
- apply patches
- write target source
- mutate files
- run shell commands
- invoke subprocesses
- run models
- perform Git operations
- commit or push
- access the network
- invoke MCP tools
- activate Goose runtime
- activate deepagents runtime
- couple builder-II to CORE Workbench/UI

Future rollback execution must be separately promoted with docs, tests, command surface, failure mode, human approval boundary, output artifact, rollback path, and verification path.
