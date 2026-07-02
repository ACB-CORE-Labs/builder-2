# deepagents Forge

deepagents Forge is the governed creation surface for defining new deepagents inside builder-II. Instead of asking operators to write raw profile YAML from scratch, Forge walks them through a structured wizard flow and validates the result against builder-II's Capability Promotion Rule before anything is emitted.

## What it does

Forge builds a `DeepAgentSpec` through an interactive TUI wizard or headless CLI flow, then:

- validates all required fields are present,
- runs the governance checklist against the Capability Promotion Rule,
- renders a full dry-run preview (YAML, profile diff, bridge spec, governance check, warnings),
- writes the agent YAML to `profiles/deepagents/{slug}.yaml`,
- registers the agent additively in `agent_profiles` and `deepagents_bridge`,
- writes a forge handoff note artifact,
- logs the emit event to the event ledger.

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
- No autonomous file writes by default — emit is constrained to `profiles/deepagents/{slug}.yaml`.
- Verification and HITL boundaries must remain explicit.
- `emit_agent(dry_run=True)` must always be safe to call with zero side effects.

## Wizard steps

Forge uses nine steps:

| Step | Id | Notes |
|---|---|---|
| 1 | `identity` | Name + auto-derived slug (editable) |
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

If any check fails, emit is blocked. The operator sees a ✅/❌ checklist in the preview step before they can proceed. In dry-run mode the governance check is shown but emit is not blocked.

## CLI usage

### Interactive TUI

```bash
# Launch the full Textual TUI wizard
bii deepagents forge

# Pre-seed name and target profile
bii deepagents forge --name pr_reviewer --profile core

# Preview only — governance check + YAML rendered, nothing written
bii deepagents forge --dry-run
```

### Headless / CI mode

```bash
bii deepagents forge \
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

## TUI layout

```
┌─────────────────────────────────────────────────────┐
│  🛠  deepagents Forge — Name your agent  [Step 1/9]  │
│  ▓▓░░░░░░░░░░░░░░░░░░░                               │
│─────────────────────────────────────────────────────│
│  What should this agent be called?                  │
│                                                     │
│  > pr_reviewer_                                     │
│                                                     │
│  💡 Use snake_case. Slug is auto-derived.            │
│─────────────────────────────────────────────────────│
│  Spec so far:                                       │
│    (no fields set yet)                              │
│─────────────────────────────────────────────────────│
│  [← Back]  [Skip]  [Next →]          [✗ Abort]     │
└─────────────────────────────────────────────────────┘
```

The bottom pane shows the accumulating spec summary on every keystroke. The preview step (step 9) replaces the input area with the full governance checklist and rendered YAML.

## Emit pipeline

When the operator confirms on the preview step, `emit_agent()` runs this sequence:

```
1. spec.is_emit_ready()          → block if required fields missing
2. check_governance(spec)        → block if Capability Promotion Rule fails
3. spec.stamp_created_at()       → UTC ISO timestamp
4. write_agent_profile(spec)     → profiles/deepagents/{slug}.yaml
5. register_agent_profile(spec)  → agent_profiles registry (additive)
6. register_bridge_spec(spec)    → deepagents_bridge (additive)
7. write_forge_handoff(spec)     → handoff_notes artifact
8. log_forge_event(spec)         → event_ledger
9. return EmitResult             → ok=True, profile_path, slug, next_command
```

Each registration call is additive and gracefully skips if the target function is not yet wired.

## DeepAgentSpec fields

| Field | Required | Default | Notes |
|---|---|---|---|
| `name` | ✅ | `""` | Human display name |
| `slug` | ✅ | auto | Derived from name; editable |
| `description` | — | `""` | Needed for `has_docs` governance check |
| `target_profile` | — | `"generic"` | `generic` / `builder` / `core` |
| `persona` | ✅ | `""` | System prompt seed |
| `lane` | — | `"default"` | Maps to lane_guides |
| `capabilities` | — | `[]` | See capability registry |
| `mcp_tools` | — | `[]` | Approved MCP tools only |
| `goose_recipe` | — | `None` | Optional Goose recipe name |
| `subagent_of` | — | `None` | Parent agent slug if nested |
| `hitl_gates` | — | `[]` | Required if write/shell caps selected |
| `context_pack` | — | `None` | Context pack slug |
| `memory_routes` | — | `[]` | Memory route identifiers |
| `verification_profile` | ✅ | `"default"` | Must be non-empty at emit |
| `approval_required` | — | `True` | Must be `True` for governance check |
| `rollback_path` | ✅ | `""` | Path for rollback artifacts |
| `output_artifact` | ✅ | `""` | Where agent writes its work |
| `author` | — | `""` | Set automatically or by operator |
| `created_at` | — | `""` | Stamped at emit time |
| `schema_version` | — | `"1.0"` | Forge schema version |

## Write and shell capability rules

Write capabilities: `write_files`, `write_memory`, `write_artifacts`.

Shell capabilities: `run_shell`, `run_commands`, `run_tests`.

If any write capability is selected, `before_write` must appear in `hitl_gates` for the governance check to pass.

If any shell capability is selected, `before_shell` must appear in `hitl_gates` for the governance check to pass.

Forge enforces these rules at the preview step before emit and at emit time. They are not advisory.

## Safety guarantees

- `emit_agent(dry_run=True)` is always safe — no files written, no registrations, no events.
- Profile emission is constrained to `profiles/deepagents/` — Forge never writes outside this directory.
- Bridge and profile registration is additive — existing profiles and bridge entries are not modified.
- Shell execution is never triggered by Forge — it is a pure data construction and file-write surface.

## Files

### New modules

| File | Role |
|---|---|
| `builder_ii/deepagents_forge_schema.py` | `DeepAgentSpec` dataclass, `derive_slug()`, `is_emit_ready()`, `to_yaml()` |
| `builder_ii/deepagents_forge_wizard.py` | `ForgeStep`, `ForgeWizard`, `FORGE_STEPS`, `ValidationResult` |
| `builder_ii/deepagents_forge_preview.py` | `check_governance()`, `render_preview()`, `GovernanceCheck`, `ForgePreview` |
| `builder_ii/deepagents_forge_emit.py` | `emit_agent()`, `EmitResult`, write/register helpers |
| `builder_ii/deepagents_forge_tui.py` | Textual TUI wizard, `ForgeApp`, `ForgeScreen`, widget set |
| `builder_ii/deepagents_forge_cli.py` | Typer CLI, `forge_agent()`, `run_headless_forge()` |

### Output

| Path | Contents |
|---|---|
| `profiles/deepagents/{slug}.yaml` | Emitted agent profile YAML |

### Tests

| File | Coverage |
|---|---|
| `tests/test_deepagents_forge_schema.py` | `DeepAgentSpec`, `derive_slug()`, `is_emit_ready()`, `to_yaml()`, `summary_lines()` |
| `tests/test_deepagents_forge_preview.py` | `check_governance()`, `collect_warnings()`, `render_bridge_spec()`, `render_preview()` |

## Related docs

- [`docs/DEEPAGENTS_POLICY.md`](DEEPAGENTS_POLICY.md) — governed deepagents policy artifacts
- [`docs/DEEPAGENTS_READINESS.md`](DEEPAGENTS_READINESS.md) — deepagents bridge readiness reports
- [`docs/CAPABILITY_PROMOTION.md`](CAPABILITY_PROMOTION.md) — full Capability Promotion Rule
- [`docs/AGENTS.md`](AGENTS.md) — generic agent profiles and authority contracts
- [`docs/TARGETS.md`](TARGETS.md) — target profiles: generic, builder, core
- [`docs/VERIFICATION_PROFILES.md`](VERIFICATION_PROFILES.md) — verification profile artifacts
