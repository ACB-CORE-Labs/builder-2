# deepagents Forge

deepagents Forge is the governed creation surface for defining new deepagents inside builder-II. Instead of asking operators to write raw profile YAML from scratch, Forge walks them through a structured wizard flow and validates the result against builder-II's Capability Promotion Rule before anything is emitted.

## What it does

Forge builds a `DeepAgentSpec` through an interactive TUI wizard or headless CLI module flow, then:

- validates all required fields are present,
- rejects unsafe slugs before any file path is constructed,
- runs the governance checklist against the Capability Promotion Rule,
- renders a full dry-run preview (YAML, profile diff, bridge spec, governance check, warnings),
- writes the agent YAML to `profiles/deepagents/{slug}.yaml`,
- attempts optional additive registration in `agent_profiles` and `deepagents_bridge` when those extension points exist,
- writes a forge handoff note artifact when that extension point exists,
- logs the emit event to the event ledger when that extension point exists.

Forge is additive. It wraps existing builder-II profile and bridge surfaces — it does not replace them.

## Why it exists

Forge solves three recurring problems:

1. **Blank-slate configuration fatigue.** Operators should not stare at an empty YAML file trying to remember what fields a deepagent needs.
2. **Unsafe capability assignment.** Write and shell capabilities require HITL gates. Without a guided flow, those gates are easily forgotten.
3. **Poor emit visibility.** The operator should see the exact YAML, governance result, and profile diff before any file is written.

The design principle is progressive disclosure: collect only the next needed decision, keep a live spec preview always visible, and make governance checks understandable as part of the product flow rather than as post-hoc documentation.

## Design boundaries

Forge follows builder-II platform rules:

- builder-II remains a generic local agent/developer platform.
- CORE is a target profile, not platform identity. Forge modules must not import CORE-specific modules.
- deepagents integration is optional and governed.
- No autonomous shell execution by default — shell capabilities require a `before_shell` HITL gate.
- No autonomous file writes by default — emit is constrained to `profiles/deepagents/{slug}.yaml` and the optional Forge handoff note under `profiles/deepagents/`.
- Editable slugs must match `^[a-z0-9]+(?:_[a-z0-9]+)*$`; path traversal and nested paths are rejected.
- Verification and HITL boundaries must remain explicit.
- `emit_agent(dry_run=True)` must always be safe to call with zero side effects.

## Wizard steps

Forge uses nine steps:

| Step | Id | Notes |
|---|---|---|
| 1 | `identity` | Name + auto-derived slug |
| 2 | `persona` | Multi-line system prompt seed |
| 3 | `target_profile` | Single select: `generic` / `builder` / `core` |
| 4 | `capabilities` | Multi-select from capability registry |
| 5 | `hitl_gates` | Multi-select; auto-required if write/shell caps selected |
| 6 | `context_pack` | Optional single select |
| 7 | `mcp_tools` | Optional multi-select from approved MCP tools |
| 8 | `governance` | `verification_profile`, `output_artifact`, `rollback_path` |
| 9 | `preview` | Full governance checklist + YAML preview + confirm |

Step 5 (`hitl_gates`) is automatically skipped if no write or shell-like capabilities are selected in step 4.

## Governance model

Before emit, Forge checks seven conditions against builder-II's Capability Promotion Rule:

| Check | Condition |
|---|---|
| `has_docs` | `description` is non-empty |
| `has_output_artifact` | `output_artifact` is non-empty |
| `has_rollback_path` | `rollback_path` is non-empty |
| `has_verification_profile` | `verification_profile` is non-empty |
| `hitl_for_write` | No write cap, or `before_write` in `hitl_gates` |
| `hitl_for_shell` | No shell cap, or `before_shell` in `hitl_gates` |
| `approval_boundary` | `approval_required` is `True` |

If any check fails, emit is blocked. The operator sees a checklist in the preview step before they can proceed. In dry-run mode the governance check is shown but no write happens.

## CLI usage

Forge is available as the registered `builder-deepagents forge` command. It is represented in command authority as Tier 1 artifact-only. It may preview or emit bounded profile/handoff artifacts; it does not construct native deepagents, start Goose, run models, invoke MCP/tools, execute shell commands, grant promotion, or authorize runtime use.

### Interactive TUI

```bash
# Launch the full Textual TUI wizard
builder-deepagents forge

# Pre-seed name and target profile
builder-deepagents forge --name pr_reviewer --profile core

# Preview only — governance check + YAML rendered, nothing written
builder-deepagents forge --dry-run
```

### Headless / CI mode

```bash
builder-deepagents forge \
  --non-interactive \
  --name test_writer \
  --profile generic \
  --persona "You are an agent that writes and updates tests under operator supervision." \
  --description "Creates and updates tests; requires HITL before any file writes." \
  --capabilities read_files,run_tests,write_files \
  --hitl-gates before_write,before_shell,on_error \
  --output-artifact artifacts/test_writer/ \
  --rollback-path rollback/test_writer/ \
  --verification-profile default
```

All `--non-interactive` flags map directly onto `DeepAgentSpec` fields. If required fields are missing, the command exits non-zero with a clear error.

## Emit pipeline

When the operator confirms on the preview step, `emit_agent()` runs this sequence:

```text
1. spec.is_emit_ready()          -> block if required fields are missing or unsafe
2. check_governance(spec)        -> block if Capability Promotion Rule fails
3. spec.stamp_created_at()       -> UTC ISO timestamp
4. write_agent_profile(spec)     -> profiles/deepagents/{slug}.yaml
5. register_agent_profile(spec)  -> optional additive extension point
6. register_bridge_spec(spec)    -> optional additive extension point
7. write_forge_handoff(spec)     -> optional handoff extension point
8. log_forge_event(spec)         -> optional event ledger extension point
9. return EmitResult             -> dry-run flag, exact paths, write flags, hook results, warnings, blockers, next review action
```

Each registration/logging call is additive and represented in `EmitResult.hook_results` as `succeeded`, `skipped`, or `failed`. Optional hook failure is reported as a warning; the core profile write remains the hard success/failure boundary.

## DeepAgentSpec fields

| Field | Required | Default | Notes |
|---|---|---|---|
| `name` | yes | `""` | Human display name |
| `slug` | yes | auto | Derived from name; must be a safe flat slug |
| `description` | governance | `""` | Needed for `has_docs` governance check |
| `target_profile` | yes | `"generic"` | `generic` / `builder` / `core` |
| `persona` | yes | `""` | System prompt seed |
| `lane` | no | `"default"` | Maps to lane_guides |
| `capabilities` | no | `[]` | See capability registry |
| `mcp_tools` | no | `[]` | Approved MCP tools only |
| `goose_recipe` | no | `None` | Optional Goose recipe name |
| `subagent_of` | no | `None` | Parent agent slug if nested |
| `hitl_gates` | no | `[]` | Required if write/shell caps selected |
| `context_pack` | no | `None` | Context pack slug |
| `memory_routes` | no | `[]` | Memory route identifiers |
| `verification_profile` | yes | `"default"` | Must be non-empty at emit |
| `approval_required` | governance | `True` | Must be `True` for governance check |
| `rollback_path` | yes | `""` | Path for rollback artifacts |
| `output_artifact` | yes | `""` | Where agent writes its work |
| `author` | no | `""` | Set automatically or by operator |
| `created_at` | no | `""` | Stamped at emit time |
| `schema_version` | no | `"1.0"` | Forge schema version |

## Write and shell capability rules

Write capabilities: `write_files`, `write_memory`, `write_artifacts`.

Shell capabilities: `run_shell`, `run_commands`, `run_tests`.

If any write capability is selected, `before_write` must appear in `hitl_gates` for the governance check to pass.

If any shell capability is selected, `before_shell` must appear in `hitl_gates` for the governance check to pass.

Forge enforces these rules at the preview step before emit and at emit time. They are not advisory.

## Safety guarantees

- `emit_agent(dry_run=True)` is always safe — no files written, no registrations, no events.
- Real emission is constrained to `profiles/deepagents/` — Forge writes `profiles/deepagents/{slug}.yaml` and may write `profiles/deepagents/forge_{slug}.handoff.json`; it never writes outside this directory.
- Slugs cannot contain path separators, `..`, leading/trailing separators, uppercase, or shell-like punctuation.
- `output_artifact` and `rollback_path` must be safe relative declarations and must not point at approval, promotion, or authority artifacts.
- Bridge and profile registration is additive and truth-reported — missing hooks are `skipped`, hook exceptions are `failed`, and neither state is presented as runtime promotion.
- Shell execution is never triggered by Forge — it is a pure data construction and bounded file-write surface.

## Files

### New modules

| File | Role |
|---|---|
| `builder_ii/adapters/deepagents/deepagents_forge_schema.py` | `DeepAgentSpec` dataclass, `derive_slug()`, `is_valid_slug()`, `is_emit_ready()`, `to_yaml()` |
| `builder_ii/adapters/deepagents/deepagents_forge_wizard.py` | `ForgeStep`, `ForgeWizard`, `FORGE_STEPS`, `ValidationResult` |
| `builder_ii/adapters/deepagents/deepagents_forge_preview.py` | `check_governance()`, `render_preview()`, `GovernanceCheck`, `ForgePreview` |
| `builder_ii/adapters/deepagents/deepagents_forge_emit.py` | `emit_agent()`, `EmitResult`, bounded write/register helpers |
| `builder_ii/adapters/deepagents/deepagents_forge_tui.py` | Textual TUI wizard, `ForgeApp`, `ForgeScreen`, widget set |
| `builder_ii/deepagents_forge_cli.py` | Typer CLI module, `forge_agent()`, `run_headless_forge()` |
| `profiles/deepagents/*.yaml` | Curated passive Forge templates; examples only, not runtime authority |

### Output

| Path | Contents |
|---|---|
| `profiles/deepagents/{slug}.yaml` | Emitted agent profile YAML |
| `profiles/deepagents/forge_{slug}.handoff.json` | Optional governed handoff note if the handoff API is available |

### Tests

| File | Coverage |
|---|---|
| `tests/test_deepagents_forge_schema.py` | `DeepAgentSpec`, slug derivation/validation, `is_emit_ready()`, YAML, summaries |
| `tests/test_deepagents_forge_preview.py` | `check_governance()`, `collect_warnings()`, `render_bridge_spec()`, `render_preview()` |
| `tests/test_deepagents_forge_emit.py` | dry-run no-side-effect guarantee, bounded profile write, path traversal rejection |
| `tests/test_deepagents_forge_cli.py` | registered command behavior, non-interactive dry-run, invalid-spec exits, TUI result semantics |

## Related docs

- [`docs/DEEPAGENTS_POLICY.md`](DEEPAGENTS_POLICY.md) — governed deepagents policy artifacts
- [`docs/DEEPAGENTS_READINESS.md`](DEEPAGENTS_READINESS.md) — deepagents bridge readiness reports
- [`docs/CAPABILITY_PROMOTION.md`](CAPABILITY_PROMOTION.md) — full Capability Promotion Rule
- [`docs/AGENTS.md`](AGENTS.md) — generic agent profiles and authority contracts
- [`docs/TARGETS.md`](TARGETS.md) — target profiles: generic, builder, core
- [`docs/VERIFICATION_PROFILES.md`](VERIFICATION_PROFILES.md) — verification profile artifacts
