# Platform Completion Audit

This document is the human mirror of the R0 truth machine. The machine-readable source is:

```bash
builder-platform matrix
builder-platform status
builder-platform audit-docs
```

## Truth State

builder-II is a generic governed local agent/developer platform. CORE is a target profile, not the platform identity, not a second runtime, and not CORE Workbench/UI.

Current platform truth:

- passive foundation state: `PASSIVE_FOUNDATION`
- runtime authority state: not `OPERATIONALLY_VERIFIED`
- setup/config kernel state: R1.4 passive schema, source resolution, setup plan, overlay plan, rollback snapshot, digest-bound apply/rollback, and legacy setup-surface reconciliation exist; generic rollback remains non-operational
- next sequence: `R0 -> R1 -> B1`

R1.4 keeps the setup/config kernel non-operational beyond the governed artifact chain. Legacy `builder setup` now fails closed and redirects to `builder-setup`, while runtime execution, Goose runtime promotion, model/provider calls, MCP/tool invocation, deepagents runtime, patch application, autonomous writes, and commit/push automation remain unpromoted.

## State Labels

Allowed labels:

- `NOT_STARTED`
- `DESIGN_ONLY`
- `ARTIFACT_ONLY`
- `PASSIVE_FOUNDATION`
- `IMPLEMENTED_ON_BRANCH`
- `PR_OPEN`
- `MERGED_BUT_NOT_OPERATIONAL`
- `OPERATIONALLY_VERIFIED`

Every row has exactly one label. A valid artifact is not authority. Approval is not execution. Execution is not verification. Verification is not promotion unless receipt, postflight, rollback/no-mutation proof, ledger, and replay/audit close the loop.

## Capability Matrix

| Capability | State | Next PR |
|---|---|---|
| generic platform identity | `PASSIVE_FOUNDATION` | R0 |
| target profiles | `PASSIVE_FOUNDATION` | B3 |
| agent profiles | `PASSIVE_FOUNDATION` | B5 |
| verification profiles | `PASSIVE_FOUNDATION` | B1 |
| context packs | `PASSIVE_FOUNDATION` | B3 |
| profile packs | `PASSIVE_FOUNDATION` | defer runtime materialization |
| config schema | `PASSIVE_FOUNDATION` | R1 |
| config source precedence | `PASSIVE_FOUNDATION` | R1 |
| interactive setup wizard | `NOT_STARTED` | R1 |
| non-interactive setup/apply/validate | `MERGED_BUT_NOT_OPERATIONAL` | R1 |
| Goose config overlay/rollback | `PASSIVE_FOUNDATION` | R1 |
| recipe generator/wizard | `ARTIFACT_ONLY` | R1 |
| skill generator/installer/validator | `MERGED_BUT_NOT_OPERATIONAL` | R1 |
| target profile wizard | `NOT_STARTED` | R1 |
| agent profile wizard | `NOT_STARTED` | R1 |
| verification profile wizard | `NOT_STARTED` | R1 |
| deepagents/researcher setup wizard | `NOT_STARTED` | R1 |
| setup receipt + rollback artifact | `PASSIVE_FOUNDATION` | R1 |
| model registry | `PASSIVE_FOUNDATION` | B6 |
| model routing | `PASSIVE_FOUNDATION` | B6 |
| model/provider execution | `MERGED_BUT_NOT_OPERATIONAL` | B6 |
| tool registry | `PASSIVE_FOUNDATION` | B7 |
| MCP/tool invocation | `DESIGN_ONLY` | B7 |
| passive orchestration assignment | `PASSIVE_FOUNDATION` | B5 |
| workflow/event ledger | `PASSIVE_FOUNDATION` | B1 then B6/B7/B8 |
| replay/audit | `PASSIVE_FOUNDATION` | B1 |
| readonly founder demo | `PASSIVE_FOUNDATION` | defer after R0 |
| orchestration founder demo wrapper | `PASSIVE_FOUNDATION` | B9 |
| HITL promotion bridge | `PASSIVE_FOUNDATION` | B1 |
| execution candidate manifests | `PASSIVE_FOUNDATION` | B1 |
| HITL-approved verification execution | `PASSIVE_FOUNDATION` | B1.3B |
| HITL patch proposal | `DESIGN_ONLY` | B2 |
| HITL patch application | `DESIGN_ONLY` | B2 after B1 |
| rollback execution | `ARTIFACT_ONLY` | B2 |
| postflight verification | `ARTIFACT_ONLY` | B1 |
| Goose setup | `MERGED_BUT_NOT_OPERATIONAL` | B4 after R0/B3 |
| Goose readonly runtime | `MERGED_BUT_NOT_OPERATIONAL` | B4 |
| Goose command proposals | `PASSIVE_FOUNDATION` | B1/B4 |
| deepagents policy/readiness | `PASSIVE_FOUNDATION` | B5 |
| deepagents passive work artifacts | `PASSIVE_FOUNDATION` | B5 |
| deepagents runtime/subagents | `DESIGN_ONLY` | B5 |
| notes/handoff artifacts | `PASSIVE_FOUNDATION` | B8 |
| artifact memory | `DESIGN_ONLY` | B8 |
| operator quickstart/golden path | `PASSIVE_FOUNDATION` | B9 |
| platform doctor/status/audit | `PASSIVE_FOUNDATION` | R1 then B1 |
| release proof/quality gates | `PASSIVE_FOUNDATION` | B1 |
| command authority as runtime gate | `MERGED_BUT_NOT_OPERATIONAL` | B1/B6/B7 |
| docs truth enforcement | `PASSIVE_FOUNDATION` | R1 then B1 |

## Corrections

- Passive model routing exists through `builder-model-policy`; provider execution remains unpromoted.
- Legacy operator-managed helpers such as `builder start`, `builder ask`, `builder doctor`, and `builder status` are separate from canonical governed passive lanes.
- Legacy `builder setup` is no longer operator-managed setup execution; it is a fail-closed redirect to the governed `builder-setup` path.
- Canonical governed passive lanes include `builder-config`, `builder-setup plan`, `builder-setup overlay-plan`, `builder-setup rollback-snapshot`, `builder-session`, `builder-profile-pack`, `builder-model-policy`, `builder-orchestration`, `builder-workflow`, `builder-ledger`, and `builder-platform`.
- R1 Config + Onboarding Kernel must precede B1 verification execution because execution authority depends on canonical target roots, artifact roots, config source precedence, setup receipts, rollback artifacts, and auditable capability defaults.
- `builder-setup plan`, `builder-setup overlay-plan`, and `builder-setup rollback-snapshot` are passive setup planning only. They record future planned overlays and prior-state snapshot metadata but cannot write Goose config, write `.goosehints`, copy skills, install recipes, apply setup, execute rollback, start models, start Goose, construct deepagents, call MCP/tools, or apply patches.

## Validation

Use:

```bash
CORE_REPO_PATH=. uv run pytest -q
CORE_REPO_PATH=. uv run python scripts/verify_v0_release.py --output-dir /tmp/builder-ii-v0-proof-r1-4
uv run builder-platform matrix
uv run builder-platform status
uv run builder-platform audit-docs
uv run builder-config schema
uv run builder-config resolve
uv run builder-setup plan --output /tmp/builder-ii-setup-plan-r1-4.json
uv run builder-setup validate-plan /tmp/builder-ii-setup-plan-r1-4.json
uv run builder-setup overlay-plan /tmp/builder-ii-setup-plan-r1-4.json --output /tmp/builder-ii-setup-overlay-r1-4.json
uv run builder-setup validate-overlay-plan /tmp/builder-ii-setup-overlay-r1-4.json
uv run builder-setup rollback-snapshot /tmp/builder-ii-setup-overlay-r1-4.json --output /tmp/builder-ii-setup-rollback-snapshot-r1-4.json
uv run builder-setup validate-rollback-snapshot /tmp/builder-ii-setup-rollback-snapshot-r1-4.json
uv run builder-platform r1-closure --output-dir /tmp/builder-ii-r1-6-proof
uv run builder-platform validate-r1-closure /tmp/builder-ii-r1-6-proof/r1-closure-report.json
```

## R1.4 update

R1.4 leaves the governed setup apply and rollback slices intact and reconciles the remaining legacy bypass: `builder setup` now fails closed and prints the governed `builder-setup` sequence instead of writing Goose config, `.goosehints`, skills, or recipes. B1, B2, B3, runtime, model/provider, MCP/tool, Goose runtime, deepagents runtime, shell/subprocess execution in the setup path, patch, and autonomous write authority remain unpromoted.

## R1.5 update

R1.5 adds `builder-setup init`, `builder-setup wizard`, `builder onboarding`, and `builder-setup validate-onboarding-intent` to provide a governed onboarding UX over the R1 setup chain. It generates passive onboarding intent reports and prints deferred apply commands only. Setup mutation remains exclusively owned by existing `builder-setup apply --approve-digest`. B1, B2, B3, runtime, model/provider, MCP/tool, Goose runtime, deepagents runtime, shell/subprocess execution in the setup path, patch, and autonomous write authority remain unpromoted.

## R1.6 update

R1.6 completes R1 by introducing `builder-platform r1-closure` and `builder-platform validate-r1-closure`. These commands execute the entire passive config/setup/onboarding chain and emit a canonical, auditable `r1-closure-report.json` alongside the full evidence artifact chain (`config-schema.json`, `config-resolution.json`, `setup-plan.json`, `setup-overlay.json`, `setup-rollback-snapshot.json`, and `onboarding-intent.json`). This proves the R1 golden path while ensuring that setup apply/rollback execution remains explicit and B1/B2/runtime/model/tool/MCP/Goose/deepagents/patch authority remain unpromoted.

B1.1 adds `builder_ii.verification_execution_plan` plus `builder-verify plan` and `builder-verify validate-plan` as a passive verification execution planning surface. B1.2 adds `builder_ii.verification_execution_approval` plus `builder-verify approve-plan` and `builder-verify validate-approval` as a digest-bound HITL approval binding surface. Both artifacts remain passive and non-authoritative: they do not run tests, execute shell/subprocess, call models/tools, invoke MCP, start Goose/deepagents, apply patches, or promote actual verification execution. B1.3A adds a passive receipt contract only. B1.3B is still required before any approved verification can run.
