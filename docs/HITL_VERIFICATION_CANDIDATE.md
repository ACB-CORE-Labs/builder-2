# HITL Verification Execution Candidate

## Scope

`builder_ii.hitl_verification_execution_candidate` records a candidate only / planned only path for a future operator-approved verification command.

builder-II is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench/UI/UX, and not a second CORE runtime. CORE is only a target profile.

## Boundary

This artifact has no execution authority:

- it does not execute commands;
- it does not run shell commands;
- it does not run models;
- it does not start Goose;
- it does not start deepagents;
- it does not mutate source files;
- it does not write target repositories;
- it does not mutate git, commit, push, or create pull requests;
- it does not convert planned verification into completed evidence;
- it does not grant authority.

## Candidate Proof

A valid candidate proves only that a future verification lane has a bounded, reviewable structure:

1. A bounded verification command intent or verification profile reference is present.
2. The command is compatible with a conservative allowlist/classification.
3. Operator review is required.
4. Approval, preflight, and request references are required at candidate stage.
5. Receipt, postflight, verification record, rollback/no-mutation assertion, and chain binding are explicitly required for the future manual/operator-approved stage.
6. `executes_now` is `false`.
7. `artifact_is_authority` is `false`.

## Command Classification

The candidate accepts only conservative command classes:

- `repo_native_pytest`: a simple pytest command such as `uv run pytest ...` with no shell control syntax.
- `builder_structural_validation`: a registered Tier 0 or Tier 1 builder command with no execution or mutation authority flags.
- `verification_profile_reference`: a safe relative reference to a verification profile artifact or verification profile report.

Unknown commands and commands containing shell control syntax fail closed.

## Required Governance

The governance block must explicitly disable:

- `runtime_execution`
- `model_execution`
- `shell_execution`
- `command_execution`
- `source_writes`
- `target_repo_writes`
- `memory_mutation`
- `git_mutation`
- `commit_push`
- `network_access`
- `goose_runtime_start`
- `deepagents_runtime`

`core_workbench_coupling` must be `NONE`.

## Chain Compatibility

The chain verifier extracts candidate-stage references to:

- `builder_ii.goose_command_proposal`
- `builder_ii.approval_record`
- `builder_ii.preflight_record`
- `builder_ii.hitl_execution_request`
- optional verification profile or verification profile report reference

Future receipt, postflight, verification, rollback, and chain-binding artifacts are requirements, not completed evidence at candidate stage.
