# builder-II Platform Release Audit

This audit closes the current governed local developer platform slice.

builder-II is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench, not CORE UI/UX, and not a second CORE runtime. CORE is represented only as a target profile.

## Release boundary

This release proves that builder-II can prepare, describe, verify, and hand off governed local development sessions without granting hidden runtime authority.

The platform supports:

- target/profile resolution
- governed session workflow planning
- Goose read-only session planning
- verification profile reporting
- governed handoff notes
- HITL governance artifacts
- optional deepagents bridge readiness
- command-surface audit closure
- artifact index and chain verification closure
- runtime governance boundary enforcement

## Proven platform chain

The current governed preparation chain is:

```text
target/profile resolution
-> session workflow plan
-> Goose read-only session plan
-> verification profile report
-> handoff note
-> optional deepagents bridge readiness report
```

This chain is artifact-first and verification-first. It does not execute commands by default.

## Required artifact kinds

The current closure slice includes:

- `builder_ii.session_workflow_plan`
- `builder_ii.goose_readonly_session_plan`
- `builder_ii.verification_profile_report`
- `builder_ii.handoff_note`
- `builder_ii.deepagents_bridge_readiness_report`

## HITL and runtime governance

The platform retains the existing HITL governance boundary:

- approval records
- preflight records
- HITL execution request records
- execution postflight records
- execution verification records
- rollback artifacts
- HITL evidence bundles

These artifacts describe and verify externally performed work. They do not silently grant execution authority.

## Non-negotiable runtime boundaries

This release audit requires:

- no autonomous source writes by default
- no shell execution by default
- no subprocess-backed runtime authority
- no model/runtime execution by readiness artifacts
- no deepagents hard dependency
- no deepagents delegation by default
- no Deephaven changes
- no CORE Workbench/UI coupling
- CORE remains a target profile only

## Command surface expectation

Every CLI registered in `pyproject.toml` must be covered by `docs/COMMAND_SURFACE_AUDIT.md`.

Command surfaces must remain explicit, documented, and governed.

## Artifact registry expectation

Every first-class artifact kind in this release slice must be recognized by the artifact index and chain verification registries when applicable.

Reference-carrying artifacts must expose references to the artifact chain verifier.

## Verification

The release audit is valid only when these checks pass:

```bash
CORE_REPO_PATH=. uv run pytest tests/test_builder_platform_release_audit.py tests/test_runtime_governance_release_audit.py tests/test_command_surface_audit.py tests/test_registry_closure.py tests/test_artifact_index_records.py tests/test_artifact_chain_verification.py -q
CORE_REPO_PATH=. uv run pytest -q
git diff --check
```

## Release verdict

This audit is a platform closure checkpoint.

It does not promote autonomous execution. It proves that builder-II has the governed artifact spine required for future HITL-gated execution capabilities.
