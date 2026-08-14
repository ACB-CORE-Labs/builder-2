# Validate Prepare Package

The governed prepare package validator checks a package created by:

    builder-session prepare-package

It validates both the package manifest and every referenced artifact.

## Command

Validate by directory:

    builder-session validate-prepare-package .builder/artifacts/prepare-package

Validate by manifest:

    builder-session validate-prepare-package .builder/artifacts/prepare-package/prepare-package.json

## What it checks

The validator checks:

- `prepare-package.json` exists
- the package manifest has the expected governed prepare package shape
- every artifact reference has a non-empty kind, path, hash, and name
- referenced artifact paths are relative
- referenced artifact paths do not escape the package directory
- referenced artifact files exist
- referenced artifact files are regular files
- each referenced artifact SHA-256 matches the manifest
- each referenced artifact is valid JSON
- each referenced artifact validates according to its declared kind

## Runtime boundary

The validator does not:

- execute shell commands
- import or use subprocess
- activate Goose
- activate or delegate to deepagents
- execute model/runtime work
- write to the target repository
- touch Deephaven
- grant runtime authority
- couple builder-II to CORE Workbench/UI

## Operator use

Use this after creating a package and before handing it to another human or agent context.

The validator proves package integrity. It does not prove that planned verification commands have been run.
