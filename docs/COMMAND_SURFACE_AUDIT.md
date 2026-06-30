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
- `builder onboarding`

Governed setup subcommands:

- `builder-setup plan`
- `builder-setup validate-plan`
- `builder-setup overlay-plan`
- `builder-setup validate-overlay-plan`
- `builder-setup rollback-snapshot`
- `builder-setup validate-rollback-snapshot`
- `builder-setup init`
- `builder-setup wizard`
- `builder-setup validate-onboarding-intent`

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
- setup apply is enabled only for digest-bound explicit approval through `builder-setup apply`
- setup rollback execution is enabled only for digest-bound explicit approval through `builder-setup rollback`; generic/B2 rollback remains disabled
- legacy `builder setup` performs no writes and only redirects to the governed R1 path
- no Goose config writes, `.goosehints` writes, skill copying, or recipe installation writes are enabled by the legacy `builder setup` redirect path
- builder-II is not CORE Workbench/UI
- CORE is only a target profile

## R1.4 Legacy Setup Reconciliation Audit

| Surface | Current behavior | Reconciled behavior | Mode | Authority tier | Write/runtime boundary |
|---|---|---|---|---|---|
| `builder setup` | Legacy compatibility entrypoint | Fails closed and prints governed `builder-setup` sequence | `disabled_redirect` | Tier 1 compatibility redirect | No setup writes, no Goose start, no subprocess/shell, no model/tool/runtime promotion |
| `builder_ii/goose_setup.py` | Passive Goose config and skill-source metadata | Passive-only setup/config-overlay helper | `passive_only` | Tier 1 passive metadata | No direct writes, no recipe validation, no skill copying |
| `builder start` | Operator-managed runtime helper | No longer auto-runs legacy setup writes | `runtime_decoupled` | Tier 2 operator-managed runtime helper | Runtime state only; setup must go through governed artifacts |
| `builder_ii/goose_launcher.py` | Runtime launcher | Runtime-only helper with session-context write | `runtime_only` | Tier 2 operator-managed runtime helper | No Goose setup delegation, no config writes, no skill installs |


## Reconciliation additions

These command surfaces are registered in `pyproject.toml` and remain governed by builder-II's default no-autonomous-execution boundary unless their specific documentation states a narrower read-only or artifact-only behavior.

- `builder-orchestration`

## R1.4 command surface delta

- `builder-setup apply` adds digest-bound governed setup apply from a validated overlay/snapshot pair and requires explicit `--approve-digest` plus explicit receipt `--output`.
- `builder-setup validate-receipt` validates `builder_ii.setup_apply_receipt` artifacts.
- `builder-setup rollback` adds digest-bound governed setup rollback from an applied setup receipt plus matching rollback snapshot.
- Legacy `builder setup` now fails closed and cannot bypass digest-bound governed setup apply/rollback.
- R1.5 adds `builder-setup init`, `builder-setup wizard`, `builder onboarding`, and `builder-setup validate-onboarding-intent` as passive onboarding wrappers.
- R1.5 does not add B1 verification execution, runtime/model/tool/MCP/Goose/deepagents/shell/subprocess/patch authority, or autonomous apply.
