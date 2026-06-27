# Governed Prepare Package

The governed prepare package command creates a bounded set of local preparation artifacts for a builder-II development session.

builder-II is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench, not CORE UI/UX, and not a second CORE runtime. CORE is only a target profile.

## Purpose

The command turns the proven platform spine into a practical operator entrypoint.

It writes explicit artifact files under the requested output directory. It does not execute target-repo work.

## Command

    builder-session prepare-package \
      --target builder \
      --repo-path . \
      --task "prepare governed builder-II development session" \
      --output-dir .builder/artifacts/prepare-package

## Artifacts

The package writes:

- session-workflow.json
- goose-readonly-session.json
- verification-profile-report.json
- handoff-note.json
- deepagents-bridge-readiness.json
- prepare-package.json

## Runtime boundary

The command does not:

- execute shell commands
- import or use subprocess
- activate Goose
- activate or delegate to deepagents
- execute model/runtime work
- write to the target repository
- touch Deephaven
- grant runtime authority
- couple builder-II to CORE Workbench/UI

## Artifact semantics

The verification profile report is planned-only.

The handoff note is a summary artifact and does not become authority.

The deepagents readiness report is optional and readiness-only.

The package manifest is a local index over the generated artifacts.

## Human responsibility

The operator must inspect the generated artifacts and run any verification commands manually.

Any future execution, source write, Goose activation, or deepagents delegation remains HITL-gated.
