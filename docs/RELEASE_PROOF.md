# Builder-II V0 Release Proof Harness

## Purpose

The **v0 release proof harness** (`scripts/verify_v0_release.py`) is an anti-handwave verification script that proves `builder-II` operates as a governed, passive, artifact-only platform spine. It proves that canonical session preparation, workflow planning, read-only inspection boundaries, platform spine composition, and chain verification can be executed end-to-end without granting runtime authority or altering target repository code.

## Canonical Release Identity

- **Repository**: `AssetOverflow/builder-II`
- **Lineage**: `v0 release lineage`
- **Target Profile**: `generic`
- **Primary Task**: `prove canonical governed session lane e2e`

## 15-Step Proof Workflow

When invoked by an operator, `scripts/verify_v0_release.py` executes the following deterministic 15-step proof:

1. Creates an isolated release output directory (default: `dist/v0-release-proof`).
2. Creates an isolated fixture target repository (or targets a user-specified repo via `--repo-path`) and takes a cryptographic byte snapshot of all working tree files.
3. Runs `create_governed_prepare_package` targeting the repository to generate the 8 canonical session artifacts:
   - `prepare-package.json` (`builder_ii.governed_prepare_package`)
   - `session-workflow.json` (`builder_ii.session_workflow_plan`)
   - `goose-readonly-session.json` (`builder_ii.goose_readonly_session_plan`)
   - `verification-profile-report.json` (`builder_ii.verification_profile_report`)
   - `repo-map.json` (`builder_ii.repo_map`)
   - `context-pack.json` (`builder_ii.context_pack`)
   - `handoff-note.json` (`builder_ii.handoff_note`)
   - `deepagents-bridge-readiness.json` (`builder_ii.deepagents_bridge_readiness_report`)
4. Runs `ConventionKernel().prepare_platform_spine` targeting the repository to produce `platform-spine.json` (`builder_ii.convention_kernel_platform_bundle`).
5. Validates the emitted prepare package directory and platform spine bundle against their native schema validators.
6. Generates a prepare package summary (`prepare-package-summary.json`).
7. Runs `verify_artifact_chain` across emitted files, validating all native schemas and internal reference integrity, writing the output to `chain-verification-report.json`.
8. Computes cryptographic SHA256 digests for all prior stage artifacts.
9. Generates `release-manifest.json` (`builder_ii.v0_release_manifest`), recording exact paths and digests for all session proof artifacts, the platform spine, and verification audits.
10. Validates `release-manifest.json` against its fail-closed native validator.
11. Runs `create_artifact_index_record` across all emitted files in the output directory and writes `artifact-index.json`.
12. Re-runs `verify_artifact_chain` across all emitted files (including the manifest and index) to confirm 0 broken links and 0 native errors.
13. Verifies that the target repository working tree and git state match the initial byte snapshot 100%.
14. Asserts fail-closed governance invariants across all records.
15. Prints an explicit proof summary to stdout.

## Strict Governance Non-Negotiables

The v0 release proof harness strictly enforces the following boundaries:

- **No Goose runtime**: Goose execution loops and subprocess activations remain completely disabled.
- **No deepagents runtime**: Deepagents delegation and autonomous agent authority remain disabled.
- **No shell execution**: Autonomous terminal commands and bash scripts are forbidden.
- **No model execution loops**: LLM execution loops are disabled.
- **No source patch application**: Code edits and target repository modifications are disabled.
- **No Deephaven touch**: Deephaven integrations are not triggered or modified.
- **Proof-of-capability only**: The emitted `release-manifest.json` is a declarative capability proof, not an executable runtime trigger.

## Operator Instructions

To execute the release proof harness:

```bash
uv run python scripts/verify_v0_release.py
```

To specify a custom output directory or run against a specific repository:

```bash
uv run python scripts/verify_v0_release.py --output-dir dist/my-release --repo-path /path/to/repo
```

To run the automated verification test suite:

```bash
uv run pytest tests/test_v0_release_proof_harness.py -q
```

## Circular Index Reference Handling

To prevent circular dependency issues during artifact index generation (since the `artifact-index.json` indexes `release-manifest.json`, while `release-manifest.json` references `artifact-index.json`), the `artifact_index_ref` reference's `sha256` field is modeled as intentionally empty. The release manifest validator explicitly permits an empty SHA-256 hash *only* for the `artifact_index_ref` key, while requiring non-empty SHA-256 hashes for all other session proof artifacts.
