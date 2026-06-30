# Config + Onboarding Kernel

R1.2 extends passive configuration and setup-planning artifacts for builder-II with setup overlay plans and rollback snapshot plans. It is not an onboarding wizard, setup apply path, rollback execution path, runtime launcher, model gateway, Goose runtime, deepagents runtime, MCP/tool bridge, patch authority, or autonomous write mechanism.

builder-II remains a generic governed local agent/developer platform. CORE is only a target profile/adapter. Generic `BUILDER_*` names are the preferred configuration vocabulary; legacy `CORE_*` names are accepted only as backwards-compatible aliases and are recorded as such in the source resolution artifact.

## Source Precedence

Config resolution is deterministic. The winning source order is:

1. explicit CLI override values passed to the resolver;
2. process environment;
3. `.env`;
4. builder config file, when present;
5. target/profile defaults;
6. built-in defaults.

Every resolved field records the source kind, source key or config path, whether a legacy alias supplied the value, warnings, errors, redacted value, and digest-bound artifact state. Raw token-like values are redacted in artifacts.

## Canonical Fields

The R1 schema models:

- schema version;
- platform artifact root;
- default target id;
- target repo entries;
- active target profile;
- active agent profile;
- active verification profile;
- model/backend defaults;
- Goose config path;
- Goose recipe path;
- Goose skills source path and destination policy;
- deepagents mode;
- disabled/passive/operational capability defaults;
- legacy compatibility metadata.

Preferred environment names include:

```bash
BUILDER_TARGET_REPO
BUILDER_TARGET_PROFILE
BUILDER_ARTIFACT_ROOT
BUILDER_MODEL_BACKEND
BUILDER_MODEL_ALIAS
BUILDER_RUNTIME_MODE
```

Legacy aliases such as `CORE_REPO_PATH`, `CORE_AGENT_BACKEND`, and `CORE_AGENT_MODEL_ALIAS` remain compatibility inputs only.

## Passive Setup Plan

`builder-setup plan` creates a passive setup plan artifact with:

- canonical target repo path;
- canonical artifact root path;
- config source resolution digest;
- selected target, agent, and verification profiles;
- selected model/backend metadata;
- Goose config target path;
- Goose recipe path;
- skills source path;
- skills destination policy;
- deepagents mode;
- disabled/passive/operational capability map;
- planned writes if a later apply flow exists;
- no-mutation proof;
- plan digest;
- next-step recommendation.

The setup plan has `artifact_is_authority=false`. Planned writes are descriptive only. No setup plan can mutate a target repository, write Goose config, copy skills, start Goose, call a model, construct deepagents, invoke MCP/tools, run shell commands, apply patches, or authorize future writes.

## Passive Setup Overlay Plan

`builder-setup overlay-plan` consumes a valid setup plan artifact and emits `builder_ii.setup_overlay_plan`. The overlay plan describes exact future setup overlays without applying them. It includes planned-only changes for:

- builder config file candidate materialization;
- `.env` recommendation;
- Goose config overlay candidate;
- `.goosehints` candidate;
- MOIM/session context candidate;
- recipe path registration candidate;
- skill install plan candidate;
- target/profile reference materialization candidate.

Every planned change has a change id, change kind, target path, scope classification, builder/target/user-config/artifact-root booleans, operation type, digest, redacted preview, conflict classification, future-approval requirement, rollback requirement, safety notes, and `planned_only=true`.

The Goose overlay candidate records the config target path, expected prior config path, overlay keys, slash-command recipe paths, extension policy, recipe path, conflict warnings, secrets-preservation policy, and rollback requirement. It does not copy credentials or secrets into the artifact.

Skill install planning records source directory, destination directory, skill id, manifest/source digests, destination path, create/replace/no-op classification, conflict notes, and rollback requirements. It does not copy skill files.

## Passive Rollback Snapshot Plan

`builder-setup rollback-snapshot` consumes a valid setup overlay plan and emits `builder_ii.setup_rollback_snapshot`. The snapshot is a prior-state description for future apply/rollback safety. It includes:

- setup plan digest and overlay plan digest;
- deterministic snapshot id and snapshot digest;
- target paths covered;
- prior existence state for each path;
- prior content digest and size when a file exists;
- redacted preview only when safe;
- missing-file, directory, symlink, and unsupported-path markers;
- secret redaction state;
- future rollback operation needed;
- `snapshot_only=true`;
- `artifact_is_authority=false`.

Normal JSON rollback snapshot artifacts do not store raw secrets or raw prior file content. They record digest, size, redacted preview, and a policy requiring future secure prior-content storage before any apply command can mutate a path.

## Path Safety

R1.2 canonicalizes local paths and classifies setup targets as builder repo, target repo, user config dir, artifact root, or outside declared setup scopes. Path traversal, symlink targets, directory/file conflicts, parent conflicts, missing parents, and unmanaged existing files are classified before any future apply exists. No planned write outside declared setup scopes validates.

## Commands

Passive config commands:

```bash
builder-config schema
builder-config resolve
builder-config validate
```

Passive setup commands:

```bash
builder-setup plan --output /tmp/builder-ii-setup-plan.json
builder-setup validate-plan /tmp/builder-ii-setup-plan.json
builder-setup overlay-plan /tmp/builder-ii-setup-plan.json --output /tmp/builder-ii-setup-overlay.json
builder-setup validate-overlay-plan /tmp/builder-ii-setup-overlay.json
builder-setup rollback-snapshot /tmp/builder-ii-setup-overlay.json --output /tmp/builder-ii-setup-rollback-snapshot.json
builder-setup validate-rollback-snapshot /tmp/builder-ii-setup-rollback-snapshot.json
```

These commands are Tier 1 artifact-only or validation-only surfaces in `docs/COMMAND_AUTHORITY.md`.

## Non-Goals

R1.3A still does not implement:

- interactive setup wizard;
- setup rollback execution;
- Goose config writes;
- `.goosehints` writes;
- skill copying or installation writes;
- recipe installation writes;
- B1 verification execution runner;
- runtime/model/tool/MCP/deepagents/Goose/patch authority;
- autonomous writes.

Existing `builder setup` remains a legacy/operator-managed helper until later R1 slices reconcile legacy setup and rollback execution with governed write boundaries. R1.3A implements apply receipts only; R1.3B may implement rollback execution using these artifacts.

## R1.3A governed setup apply receipt

R1.3A adds `builder-setup apply` as a narrowly scoped governed setup-write command. It consumes a validated setup overlay plan and a validated rollback snapshot, requires `--approve-digest` to exactly match `overlay_plan_digest`, and writes a required setup receipt to the explicit `--output` path. The apply path writes only declared setup targets from the overlay plan and supports only create, replace, mkdir, and no-op operations. Unsupported merge/copy operations fail closed unless a later PR explicitly reconciles and tests them.

Rollback execution is not implemented in R1.3A; it is reserved for R1.3B. Setup apply does not grant shell, subprocess, model/provider, runtime, MCP/tool, Goose runtime, deepagents runtime, B1 verification runner, patch, autonomous apply, or arbitrary source-code mutation authority. Existing legacy `builder setup` remains operator-managed legacy behavior until an explicit R1.4 reconciliation PR.

```bash
builder-setup apply SETUP_OVERLAY.json \
  --rollback-snapshot SETUP_ROLLBACK_SNAPSHOT.json \
  --approve-digest <overlay_plan_digest> \
  --output SETUP_RECEIPT.json
builder-setup validate-receipt SETUP_RECEIPT.json
```
