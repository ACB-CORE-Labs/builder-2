# Prepare Package Summary

The governed prepare package summary command creates a human-readable JSON summary of a valid governed prepare package.

It is intended for operator inspection before handoff, review, or manual verification.

## Command

Print a summary:

    builder-session summarize-prepare-package .builder/artifacts/prepare-package

Write a summary artifact:

    builder-session summarize-prepare-package .builder/artifacts/prepare-package \
      --output .builder/artifacts/prepare-package/prepare-package-summary.json

## Validation-first behavior

The summary command refuses to summarize invalid packages.

Before emitting a summary, it validates:

- the prepare package manifest
- referenced artifact paths
- artifact containment under the package directory
- artifact existence
- SHA-256 hash matches
- referenced artifact JSON validity
- referenced artifact schema validity by declared kind

## What the summary contains

The summary includes:

- target profile
- target repo path
- task
- package state
- validation state
- artifact count
- artifact kinds
- artifact paths and hashes
- operator next actions
- governance boundary

## Runtime boundary

The summary command does not:

- execute shell commands
- import or use subprocess
- activate Goose
- activate or delegate to deepagents
- execute model/runtime work
- write to the target repository
- touch Deephaven
- grant runtime authority
- couple builder-II to CORE Workbench/UI

## Verification boundary

The summary proves package integrity only.

It does not prove that planned verification commands have been run.

It does not convert planned verification into completed evidence.

It does not make the summary artifact authoritative.
