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

R1.4 still does not implement:

- interactive setup wizard;
- Goose config writes;
- `.goosehints` writes;
- skill copying or installation writes;
- recipe installation writes;
- B1 verification execution runner;
- runtime/model/tool/MCP/deepagents/Goose/patch authority;
- autonomous writes.

Legacy `builder setup` no longer performs unmanaged writes. R1.4 converts it into a fail-closed compatibility wrapper that prints the governed `builder-setup` command sequence only. R1.3A implements digest-bound apply receipts; R1.3B implements digest-bound governed setup rollback execution using those receipts and R1.2 rollback snapshots.

## R1.3A governed setup apply receipt

R1.3A adds `builder-setup apply` as a narrowly scoped governed setup-write command. It consumes a validated setup overlay plan and a validated rollback snapshot, requires a digest-bound approval that exactly matches `overlay_plan_digest`, and writes a required setup receipt to the explicit `--output` path. The approval takes one of three forms, and the receipt records which was used in `approval_mode`: `--approve-digest <overlay_plan_digest>` for scripted flows (`explicit_digest_bound_cli_flag`); an interactive confirmation in which apply prints the full overlay plan digest and the operator types its first 4 characters back (`interactive_digest_prefix_confirmation`, the same confirmation grammar as the HITL patch approvals); or a standing ratification grant the operator previously minted for the `setup.apply.overlay_digest` point (`standing_ratification_grant`, see [`RATIFICATION_GRANTS.md`](RATIFICATION_GRANTS.md)). The three are never conflated: a receipt saying `interactive_digest_prefix_confirmation` means a human typed the prefix, and one saying `standing_ratification_grant` means a grant satisfied it and names that grant in stdout. A wrong prefix refuses with no writes and no receipt. The apply path writes only declared setup targets from the overlay plan and supports only create, replace, mkdir, and no-op operations. Unsupported merge/copy operations fail closed unless a later PR explicitly reconciles and tests them.

Setup apply does not grant shell, subprocess, model/provider, runtime, MCP/tool, Goose runtime, deepagents runtime, B1 verification runner, patch, autonomous apply, generic rollback, git rollback, B2 patch rollback, or arbitrary source-code mutation authority. Legacy `builder setup` is now only a redirect surface and cannot bypass this digest-bound lane.

```bash
builder-setup apply SETUP_OVERLAY.json \
  --rollback-snapshot SETUP_ROLLBACK_SNAPSHOT.json \
  --approve-digest <overlay_plan_digest> \
  --output SETUP_RECEIPT.json
builder-setup validate-receipt SETUP_RECEIPT.json
```


## R1.3B governed setup rollback receipt

R1.3B adds `builder-setup rollback` and `builder-setup validate-rollback-receipt` as a narrowly scoped setup rollback lane. The rollback executor consumes an R1.3A setup apply receipt plus an R1.2 rollback snapshot, requires a digest-bound approval that exactly matches the setup receipt digest, and writes a setup rollback receipt to the explicit `--output` path. As with apply, the approval is `--approve-digest <setup_receipt_digest>` (scripted; `approval_mode` `explicit_digest_bound_cli_flag`), an interactive typed digest-prefix confirmation against the printed receipt digest (`interactive_digest_prefix_confirmation`), or a standing ratification grant for the `setup.rollback.receipt_digest` point (`standing_ratification_grant`); a wrong prefix refuses with no writes. It touches only `changed_paths` from an applied setup receipt when every changed path is covered by the supplied snapshot. Skipped setup paths are recorded as no-op only.

The executor preflights deterministic rollback denials before any mutation. Missing prior state deletes future-created files or empty directories. Prior directories are ensured to exist or treated as no-op. Prior files require safely available raw prior content and otherwise fail closed with `manual_restore_required`; redacted previews are never used as restore material. Prior symlinks and unsupported states fail closed. Rollback never invokes git, shell, subprocesses, models, MCP/tools, Goose, deepagents, patch authority, B1 verification execution, B2 patch rollback, generic repository rollback, or autonomous rollback.

```bash
builder-setup rollback SETUP_RECEIPT.json \
  --rollback-snapshot SETUP_ROLLBACK_SNAPSHOT.json \
  --approve-digest <setup_receipt_digest> \
  --output SETUP_ROLLBACK_RECEIPT.json
builder-setup validate-rollback-receipt SETUP_ROLLBACK_RECEIPT.json
```

## R1.4 legacy setup reconciliation

R1.4 reconciles legacy setup surfaces into the governed R1 path:

- `builder setup` is a fail-closed compatibility wrapper that prints the governed `builder-setup` sequence and exits non-zero.
- `builder_ii/adapters/goose/goose_setup.py` remains setup-artifact/config-overlay oriented and does not perform direct writes, skill copying, or recipe validation.
- Goose setup remains represented as passive overlay candidates until the operator explicitly uses digest-bound `builder-setup apply`.
- Skills, recipes, Goose config, and `.goosehints` are not installed through unmanaged writes.

## R1.5 governed onboarding UX

R1.5 adds a governed onboarding UX layer over the existing R1 setup chain:

- `builder-setup init` provides a non-interactive wrapper around configuration resolution, setup planning, overlay planning, rollback snapshot generation, and intent reporting.
- `builder-setup wizard` provides an interactive guided onboarding flow using safe `typer.prompt` dry-run inputs.
- `builder onboarding` provides a clean root CLI delegation to `builder-setup wizard`.
- `builder-setup validate-onboarding-intent` validates passive onboarding intent report artifacts (`builder_ii.onboarding_intent_report`).

The onboarding intent report records onboarding inputs, target and agent profiles, planned files, and the setup plan/overlay/rollback snapshot digests. It explicitly asserts that `artifact_is_authority` is `false` and that runtime, model, shell, subprocess, Goose, deepagents, and patch execution remain disabled.

```bash
builder-setup init --output-dir .builder/setup-artifacts
builder-setup validate-onboarding-intent .builder/setup-artifacts/onboarding-intent.json
builder-setup wizard
builder onboarding
```

Onboarding commands do not perform mutation or write setup receipts directly. To apply setup writes, run the printed `builder-setup apply` command after reviewing the overlay plan digest.

## 2.2 unified `builder init` orchestrator

`builder init` is the single onboarding entrypoint for new operators. It composes the same governed onboarding pipeline as `builder-setup init`/`wizard` (setup plan → overlay plan → rollback snapshot → onboarding intent report) and, like them, is a Tier 1 artifact-only surface: it **never applies**.

It splits the nine onboarding decisions into two groups:

**Four prompted decisions** — asked interactively when not provided by flag, with the resolved configuration value offered as the default. Every answer, typed or flag-provided, is validated against the live registry for that decision (never accepted as free text); an invalid interactive answer re-prompts up to 3 attempts, an invalid flag answer exits immediately.

| Decision | Flag | Validated against |
|---|---|---|
| Output directory | `--output-dir` (default `.builder/setup-artifacts`) | non-empty path |
| Target profile | `--target-profile` | target profile registry (`generic`, `builder`, `core`) |
| Model backend | `--model-backend` | backend registry |
| Model alias | `--model-alias` | model alias registry |

**Five defaulted decisions** — resolved through the standard config source precedence (defaults → `.env` → config file → CLI override), echoed in the init summary together with the flag that overrides each, and never prompted:

| Decision | Documented default | Override flag |
|---|---|---|
| Agent profile | `patch_planner` | `--agent-profile` |
| Verification profile | `builder_full` | `--verification-profile` |
| Artifact root | `<root>/.builder/artifacts` | `--artifact-root` |
| Runtime mode | `passive` | `--runtime-mode` |
| Artifact root inside target | `false` | `--allow-artifact-root-inside-target` |

`--non-interactive` disables prompting entirely: missing prompted decisions fall back to their resolved defaults, still registry-validated.

The init summary ends with the exact `builder-setup apply` command to run next — printed **without** an inline `--approve-digest`. Approval happens only in the separately invoked apply step, via the interactive digest-prefix confirmation (or `--approve-digest` for scripted flows). The process that renders a digest never harvests its own confirmation.

```bash
builder init                       # prompt for all nine onboarding decisions
builder init --target-profile generic --model-backend mlx-lm --model-alias qwen-coder --non-interactive
```

## R1.6 closure report and golden-path proof

R1.6 completes R1 by providing a single canonical golden path that aggregates all passive configuration, setup planning, overlay, rollback snapshot, and onboarding intent artifacts into an `r1-closure-report.json`:

- `builder-platform r1-closure` runs the complete passive R1 chain and writes `r1-closure-report.json` along with its underlying evidence files to `--output-dir`.
- `builder-platform validate-r1-closure` verifies schema, digests, status labels, and referenced evidence files for any closure report on disk.

```bash
builder-platform r1-closure --output-dir .builder/r1-closure
builder-platform validate-r1-closure .builder/r1-closure/r1-closure-report.json
```

This establishes an end-to-end auditable proof for operator configuration and setup intent without executing setup mutation or promoting B1/B2/runtime/model/tool/MCP/Goose/deepagents/patch authority.

## R1.7 Goose config and skills — manual step (beta)

`builder-setup apply` never writes a real Goose config or copies skills, by design:

- The `goose_config_overlay_candidate` planned change is always `no-op` — the overlay only describes the keys builder-II would add; it never merges them into an existing config file.
- The `skill_install_plan_candidate` planned change resolves to a `copy` operation, and `copy` is not one of `setup_apply.py`'s `SUPPORTED_OPERATIONS` (`create`, `replace`, `mkdir`, `no-op`). `builder-setup apply` denies it with `unsupported operation: copy` rather than silently skip it.

This is not an oversight. A real Goose config almost always carries provider credentials and other unrelated extensions that builder-II must never overwrite, so a safe automated merge is its own secrets-handling promotion path (post-beta, full 8-gate). Automated skill copying is a stretch goal, not a beta commitment. For beta, wiring Goose is an explicit **manual, operator-performed step** — builder-II reads and describes your Goose config; it does not write to `~/.config/goose/config.yaml` or your skills directory itself.

### Steps

1. Generate the overlay plan (R1.2 above) if you have not already:

   ```bash
   builder-setup overlay-plan /tmp/builder-ii-setup-plan.json --output /tmp/builder-ii-setup-overlay.json
   ```

2. Read the `goose_overlay_candidate` object inside the overlay JSON. For your machine, it names:
   - `config_target_path` — the Goose config file to edit (typically `~/.config/goose/config.yaml`).
   - `overlay_keys` — exactly which top-level dotted keys to add: `extensions.builder_ii`, `recipes.builder_ii.path`, `slash_commands.builder_ii.recipe_path`.
   - `recipe_path` / `slash_command_recipe_paths` — the resolved recipe file path(s) for this checkout.
   - `secrets_preservation_policy` and `conflict_warnings` — the two rules this manual step exists to honor: never drop unknown keys, never touch existing credentials.

3. Back up the file before touching it — there is no governed rollback for a hand edit: `cp ~/.config/goose/config.yaml ~/.config/goose/config.yaml.bak`.

4. Add only the `builder_ii` keys named in `overlay_keys`, leaving every existing key (providers, credentials, other extensions) untouched. `overlay_keys` is the authoritative list of *where* to add content; `builder_ii/adapters/goose/goose_setup.py:build_goose_config()` is the best available reference for *what* content belongs in the extensions block. The two are maintained independently and are not yet unified into one schema — read both source references above rather than trusting a doc snippet that could drift; the shape below is illustrative:

   ```yaml
   extensions:
     builder_ii:
       developer: {bundled: true, enabled: true, type: builtin, timeout: 600}
       skills: {bundled: true, enabled: true, type: platform, timeout: 300}
       summon: {bundled: true, enabled: true, type: platform, timeout: 300}
   recipes:
     builder_ii:
       path: <recipe_path from step 2>
   slash_commands:
     builder_ii:
       recipe_path: <recipe_path from step 2>
   ```

   If your Goose config already has a top-level `extensions`, `recipes`, or `slash_commands` key, add `builder_ii` as a sibling entry under it — do not replace the existing block.

5. Skills: the overlay's `skill_install_plan.entries` lists each skill under `.agents/skills/` with a `source_directory` and `destination_directory`. Copy (or symlink) each entry by hand — `builder-setup apply` will not do this for you in beta:

   ```bash
   cp -r .agents/skills/core-governed-coding <target-repo>/.agents/skills/core-governed-coding
   ```

6. There is no receipt and no digest-bound rollback for this manual step; it is intentionally outside the `builder-setup apply`/`rollback` lane. To review what changed, diff the edited file against the `.bak` copy from step 3.

