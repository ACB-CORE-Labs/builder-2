# Runtime Governance Release Audit

**Date:** 2026-06-27
**Status:** Runtime-governance foundation complete; all execution capabilities remain disabled by default.

## 1. Platform Identity and Scope

builder-II is a generic governed local agent/developer platform.

builder-II is not CORE, not CORE Workbench/UI/UX, and not a second CORE runtime. CORE is only a target profile.
This audit covers the current builder-II governance foundation after the HITL command execution spec, HITL execution request/receipt artifacts, HITL execution artifact CLI, HITL patch application spec, rollback artifacts, execution postflight and verification record specs, command surface audit, and registry closure sweep.

## 2. Completed Runtime-Governance Foundation

The current foundation includes these merged surfaces:

- HITL command execution spec: `docs/HITL_COMMAND_EXECUTION.md`, `builder_ii/hitl_command_execution.py`, `tests/test_hitl_command_execution.py`
- HITL execution request/receipt artifacts: `builder_ii/hitl_execution_records.py`, `docs/HITL_EXECUTION_RECORDS.md`, `tests/test_hitl_execution_records.py`
- HITL execution artifact CLI: `builder_ii/hitl_execution_cli.py`, `docs/HITL_EXECUTION_CLI.md`, `tests/test_hitl_execution_cli.py`
- HITL patch application spec: `builder_ii/hitl_patch_spec.py`, `docs/HITL_PATCH_SPEC.md`, `tests/test_hitl_patch_spec.py`
- Rollback plan/receipt artifacts: `builder_ii/rollback_artifacts.py`, `docs/ROLLBACK_ARTIFACTS.md`, `tests/test_rollback_artifacts.py`
- Execution postflight and verification record specs: `builder_ii/execution_postflight_records.py`, `docs/EXECUTION_POSTFLIGHT_RECORDS.md`, `tests/test_execution_postflight_records.py`
- Command surface audit: `docs/COMMAND_SURFACE_AUDIT.md`, `tests/test_command_surface_audit.py`
- Registry closure: `builder_ii/artifact_index_records.py`, `builder_ii/artifact_chain_verification.py`, `docs/ARTIFACT_INDEX.md`, `tests/test_registry_closure.py`

These surfaces are governance/spec/record surfaces. They describe future controlled behavior, but they do not grant runtime authority.

## 3. Registered Governance Artifact Kinds

The artifact index registry and chain verification registry account for these runtime-governance artifact kinds:

- `builder_ii.hitl_execution_request`
- `builder_ii.hitl_execution_receipt`
- `builder_ii.hitl_patch_application_spec`
- `builder_ii.rollback_plan`
- `builder_ii.rollback_receipt`
- `builder_ii.execution_postflight_record`
- `builder_ii.execution_verification_record`

The registry closure sweep validates these kinds natively and documents that they currently produce no outbound chain references. If future PRs add cross-record SHA references, the chain reference extractor must be updated and tested then.

## 4. Command Surface Audit

`docs/COMMAND_SURFACE_AUDIT.md` is the current command surface inventory. `tests/test_command_surface_audit.py` parses `pyproject.toml` and fails if any registered `builder-*` console script is missing from the audit document.

The command surface audit asserts:

- no shell execution is enabled
- no model execution is enabled
- no patch application is enabled
- no autonomous writes are enabled
- no Goose runtime activation is enabled
- no deepagents runtime is enabled
- builder-II is not CORE Workbench/UI
- CORE is only a target profile

## 5. Disabled-by-Default Runtime Claims

The following capabilities are not enabled in the current foundation release:

| Capability | Current status |
|---|---|
| Shell execution | NOT ENABLED |
| Command execution | NOT ENABLED |
| Model execution | NOT ENABLED |
| Patch application | NOT ENABLED |
| Autonomous writes | NOT ENABLED |
| Source writes by agent runtime | NOT ENABLED |
| Git mutation | NOT ENABLED |
| Commit/push automation | NOT ENABLED |
| Network/MCP execution | NOT ENABLED |
| Goose runtime activation | NOT ENABLED |
| deepagents runtime | NOT ENABLED |
| Rollback execution | NOT ENABLED |
| Voice/TTS/STT runtime | NOT ENABLED |
| CORE Workbench/UI coupling | NONE |

## 6. No-Authority Claims

The current foundation enforces these no-authority claims:

- Artifact validity does not grant runtime authority.
- Design-only artifacts describe future governance contracts; they do not activate those contracts.
- `artifact_is_authority` remains `false` on governance artifacts that carry the field.
- `core_workbench_coupling` remains `NONE` on governance artifacts that carry the field.
- No runtime capability is promoted to `enabled`.
- No artifact or CLI surface may bypass the human approval boundary.

## 7. Future Promotion Ladder

Every runtime capability remains gated by all of the following before any promotion to enabled behavior:

1. docs
2. tests
3. command surface
4. failure mode
5. human approval boundary
6. output artifact
7. rollback path
8. verification path

The next safe promotion candidates are artifact/CLI/spec-only work, not active runtime execution:

- HITL execution artifact CLI without execution (COMPLETED - creates governance artifacts only, does not execute commands)
- execution postflight and verification record specs

The first real execution surface, the bounded HITL command executor, must not start until the request, receipt, postflight, verification, rollback, and command-surface controls are complete and reviewed.

## 8. Release Verification Checklist

Use these checks for this foundation state:

```bash
uv run pytest tests/test_runtime_governance_release_audit.py -q
uv run pytest tests/test_registry_closure.py tests/test_artifact_index_records.py tests/test_artifact_chain_verification.py -q
uv run pytest tests/test_command_surface_audit.py -q
CORE_REPO_PATH=. uv run pytest -q
git diff --check
```

## 9. Summary

builder-II is now positioned as a governed local agent/developer platform with a closed runtime-governance foundation. The platform has recorded command execution, patch application, rollback, command-surface, and registry governance surfaces while keeping shell execution, model execution, patch application, rollback execution, autonomous writes, Goose runtime activation, deepagents runtime, voice/TTS/STT runtime, and CORE Workbench/UI coupling disabled by default.
