# Command Surface Audit

This document lists current CLI command surfaces from `pyproject.toml`, grouped by category.

## Platform Setup / Runtime Policy
- `builder`
- `builder-runtime`
- `builder-lanes`
- `builder-tools`
- `builder-git-state`
- `builder-platform`
- `builder-config`
- `builder-setup`

R1.2 passive setup subcommands:

- `builder-setup plan`
- `builder-setup validate-plan`
- `builder-setup overlay-plan`
- `builder-setup validate-overlay-plan`
- `builder-setup rollback-snapshot`
- `builder-setup validate-rollback-snapshot`

## Target/Profile/Context
- `builder-context`
- `builder-profile-pack`
- `builder-model-policy`
- `builder-targets`
- `builder-session`
- `builder-workflow`
- `builder-ledger`

## Artifact Chain / Governance Records
- `builder-records`
- `builder-receipt`
- `builder-chain`
- `builder-index`
- `builder-state-index`
- `builder-snapshot`
- `builder-hitl`

## Promotion/Readiness/Decision
- `builder-preflight`
- `builder-promotion`
- `builder-promotion-decision`

## Inspection/Read-Only Candidate
- `builder-readonly`

## Research/Performance/Verification
- `builder-agent`
- `builder-bundle`
- `builder-quality`
- `builder-research`
- `builder-performance`
- `builder-verification`

## Notes/Handoff/Intake
- `builder-handoff`
- `builder-intake`
- `builder-notes`

## Deepagents/Goose Optional Bridge Surfaces
- `builder-bridge`
- `builder-goose`
- `builder-deepagents`

## Runtime Policy & Architectural Invariants

- no shell execution is enabled
- no model execution is enabled
- no patch application is enabled
- no autonomous writes are enabled
- no Goose runtime activation is enabled
- no deepagents runtime is enabled
- no setup apply is enabled
- setup rollback execution is enabled only for digest-bound explicit approval; generic/B2 rollback remains disabled
- no Goose config writes, `.goosehints` writes, skill copying, or recipe installation writes are enabled by `builder-setup`
- builder-II is not CORE Workbench/UI
- CORE is only a target profile


## Reconciliation additions

These command surfaces are registered in `pyproject.toml` and remain governed by builder-II's default no-autonomous-execution boundary unless their specific documentation states a narrower read-only or artifact-only behavior.

- `builder-orchestration`

## R1.3A command surface delta

- `builder-setup apply` adds digest-bound governed setup apply from a validated overlay/snapshot pair and requires explicit `--approve-digest` plus explicit receipt `--output`.
- `builder-setup validate-receipt` validates `builder_ii.setup_apply_receipt` artifacts.
- R1.3B adds setup rollback only and does not add B1 verification execution, runtime/model/tool/MCP/Goose/deepagents/shell/subprocess/patch authority, autonomous apply, or legacy setup reconciliation.
