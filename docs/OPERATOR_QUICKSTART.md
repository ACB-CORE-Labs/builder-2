# Operator Quickstart

This guide shows the first complete operator lane for builder-II.

builder-II is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench, not CORE UI/UX, and not a second CORE runtime. CORE is only a target profile.

## Purpose

The governed prepare package lane gives an operator one bounded path to prepare, validate, and inspect a local development session package.

This lane is artifact-first and human-governed.

## Lane

    builder-session prepare-package
    builder-session validate-prepare-package
    builder-session summarize-prepare-package

## Example

Create a governed package:

    builder-session prepare-package builder \
      --repo-path . \
      --task "prepare governed builder-II development session" \
      --output-dir .builder/artifacts/prepare-package

Validate the package:

    builder-session validate-prepare-package .builder/artifacts/prepare-package

Summarize the package:

    builder-session summarize-prepare-package .builder/artifacts/prepare-package \
      --output .builder/artifacts/prepare-package/prepare-package-summary.json

## Expected package artifacts

The package directory contains:

- session-workflow.json
- goose-readonly-session.json
- verification-profile-report.json
- handoff-note.json
- deepagents-bridge-readiness.json
- prepare-package.json
- optionally, prepare-package-summary.json

## What validation proves

Validation proves:

- the package manifest is valid
- referenced artifacts exist
- referenced paths do not escape the package directory
- referenced hashes match
- referenced JSON artifacts validate by declared kind

Validation does not prove that planned verification commands have been run.

## What summarization proves

Summarization proves:

- the package was valid before summarization
- the operator has a human-readable inspection record
- the package state and artifact inventory are visible

Summarization does not convert planned verification into completed evidence.

## Runtime boundary

This quickstart lane does not:

- execute shell commands
- import or use subprocess
- activate Goose
- activate or delegate to deepagents
- execute model/runtime work
- write to the target repository
- touch Deephaven
- grant runtime authority
- couple builder-II to CORE Workbench/UI

## Human responsibility

The operator must inspect the package, run planned verification manually where appropriate, and record evidence before making verification claims.

Any future execution or source write remains HITL-gated.
