# Config + Onboarding Kernel

R1.1 establishes passive configuration and setup-planning artifacts for builder-II. It is not an onboarding wizard, setup apply path, rollback path, runtime launcher, model gateway, Goose runtime, deepagents runtime, MCP/tool bridge, patch authority, or autonomous write mechanism.

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

The R1.1 schema models:

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

## Path Safety

R1.1 canonicalizes local paths. An artifact root inside a target source tree is rejected unless it is under the platform artifact convention `.builder/artifacts` or an explicit path policy opt-in is supplied. This prevents accidental source-tree mutation from being hidden inside setup planning.

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
```

These commands are Tier 1 artifact-only or validation-only surfaces in `docs/COMMAND_AUTHORITY.md`.

## Non-Goals

R1.1 does not implement:

- interactive setup wizard;
- setup apply;
- setup rollback;
- setup receipt;
- Goose overlay writes;
- skill installation changes;
- B1 verification execution runner;
- runtime/model/tool/MCP/deepagents/Goose/patch authority;
- autonomous writes.

Existing `builder setup` remains a legacy/operator-managed helper until later R1 slices reconcile setup apply, setup receipts, rollback artifacts, and governed write boundaries.
