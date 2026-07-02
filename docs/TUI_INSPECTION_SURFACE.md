# TUI Inspection Surface

builder-II ships a **read-only terminal inspection surface** across six Python
modules. Together they let an operator inspect every governed artifact kind
without writing, executing, or promoting anything.

> **Governance contract** — every module in this surface is read-only by
> design. None of them write artifacts, start runtimes, apply patches, or
> mutate state. All governed mutations route through the HITL CLI
> (`hitl_promotion_cli.py`, `hitl_execution_cli.py`) and require explicit
> operator invocation.

---

## Overview

| Module | Command prefix | Artifact kinds covered |
|---|---|---|
| `hitl_tui.py` | `builder hitl` | HITL execution records, verification candidates, promotion artifacts, patch proposals |
| `profile_tui.py` | `builder profile` | Target profiles, agent profiles, verification profiles, profile packs |
| `model_tui.py` | `builder model` | Model routing tables, model role matrix, model operating policy |
| `promote_tui.py` | `builder promote` | Promotion readiness, HITL promotion artifacts, promotion decisions, compatibility |
| `postflight_tui.py` | `builder postflight` | Execution postflight records, execution verification records |
| `goose_tui.py` | `builder goose` | Goose session manifests |

All six modules share the same **palette contract** and **exit code
semantics** described in the [Palette and Glyphs](#palette-and-glyphs)
and [Exit Codes](#exit-codes) sections below.

---

## Design Principles

### Read-only without exception

No TUI command writes a file, starts a process, triggers a model call, or
mutates any artifact. The `--verbose` / `-v` flag expands output only; it
never changes behaviour.

### Every command is a gate

Every command returns a meaningful exit code. `0` means the inspected
artifacts are in a healthy, expected state. `1` means something requires
operator attention — a missing artifact, a failed gate, an invalid schema,
an unexpected governance value. This makes every command directly usable in
CI preflight scripts, Makefiles, and shell pipelines.

### Schema authority stays in the records module

Each TUI module delegates validation to the corresponding records module:

| TUI module | Validation source |
|---|---|
| `hitl_tui.py` | `hitl_execution_records`, `hitl_verification_candidate`, `hitl_promotion_artifacts`, `hitl_patch_proposal` |
| `profile_tui.py` | `target_profiles`, `agent_profiles`, `verification_profiles`, `profile_packs` |
| `model_tui.py` | `model_routing`, `model_role_matrix` |
| `promote_tui.py` | `promotion_readiness_records`, `hitl_promotion_artifacts`, `promotion_decision_records`, `promotion_compatibility` |
| `postflight_tui.py` | `execution_postflight_records` |
| `goose_tui.py` | `goose_session` |

The TUI never re-implements validation logic. If the records module is
unavailable (e.g., import error in a stripped environment), the TUI reports
the import failure as a validation error rather than silently skipping checks.

### Artifact discovery

All modules discover artifacts from `$BUILDER_DIR` (defaults to `.builder/`)
by globbing for JSON files containing the expected `kind` field. Explicit
file paths or IDs can be passed as positional arguments to filter results.
No module requires a database, index, or registry — the filesystem is the
source of truth.

### Graceful degradation

If no artifacts are found, the command prints a dim hint line and exits `0`.
If an artifact exists but is unreadable or invalid JSON, the error is
reported per-file without crashing the whole command.

---

## Palette and Glyphs

All six modules share the same colour contract. Colours are applied only
when stdout is a TTY (`sys.stdout.isatty()`). When piped or redirected,
output is plain text with no ANSI codes.

Theme colours are loaded from `builder_ii.tui_theme.theme_palette()` if
available, otherwise the following hex fallback palette is used:

| Role | Hex | Usage |
|---|---|---|
| `pass` | `#4ade80` | Passing gates, clean states, valid artifacts |
| `warn` | `#fbbf24` | Pending states, unexpected-but-non-fatal values, amber conditions |
| `fail` | `#f87171` | Failing gates, errors, invalid values, DISABLED violations |
| `hint` | `#94a3b8` | Supplementary info, rationale text, summaries |
| `active` | `#38bdf8` | Refs, links, active selections, Powder Blue highlights |
| `dim` | `#475569` | Keys, labels, dividers, empty slots |
| `bold` | `#f1f5f9` | Primary entity names, section titles |
| `accent` | `#818cf8` | Section headers, agent names, decorative accents |

### Standard glyph set

| Glyph | Meaning |
|---|---|
| `✔` (pass green) | Gate passes / artifact valid / state clean |
| `✘` (fail red) | Gate fails / error / invalid |
| `⚠` (warn amber) | Pending / unexpected value / non-fatal warning |
| `–` (dim) | Skipped / not applicable / empty |
| `■` (dim) | Governance cap: DISABLED |
| `▷` (pass green) | Allowed action |
| `◁` (fail red) | Denied action |
| `↳` (active blue) | Ref chain link / slot filled |
| `◉` (amber) | HITL state: PENDING |
| `▲` (green) | HITL state: APPROVED / PROMOTED |
| `▣` (active) | HITL state: AUTHORIZED |
| `▼` (red) | HITL state: REJECTED |
| `●` (dim) | HITL state: DEFERRED / performed action bullet |
| `◆` (accent) | Agent profile |

---

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | All inspected artifacts are in expected state (or no artifacts found) |
| `1` | One or more artifacts require attention: failed gate, invalid schema, unexpected governance value, wrong state |

All `status` and `validate` commands are designed to be used as CI gates:

```sh
builder hitl status || exit 1
builder promote gates || exit 1
builder postflight validate || exit 1
builder goose status || exit 1
```

---

## `builder hitl` — HITL Inspection

**Module:** `builder_ii/hitl_tui.py`  
**Artifact kinds:** `builder_ii.hitl_execution_record`, `builder_ii.hitl_verification_candidate`,
`builder_ii.hitl_promotion_artifact`, `builder_ii.hitl_patch_proposal`

### Commands

#### `builder hitl status`

Full HITL pipeline overview. Shows four panels: execution records, verification
candidates, promotion artifacts, and patch proposals. Each row shows artifact
name/target, state glyph, and timestamp. A **Pipeline Bar** at the bottom
shows the four stages: `Execution → Verification → Promotion → Patch`. Completed
stages render in pass-green; pending stages are dim.

Flags: `-v` / `--verbose` — show governance block and rationale fields.

Exit `1` if any required artifact is missing, in a failed state, or has
validation errors.

#### `builder hitl record [id]`

Renders HITL execution record detail. Shows state, target, refs, governance
block, and validation errors. The `[id]` argument filters by filename or
target name.

#### `builder hitl candidate [id]`

Renders HITL verification candidate detail. Shows candidate state, quality
gates, evidence refs, and the ref chain linking to the execution record.

#### `builder hitl promotion [id]`

Renders HITL promotion artifact detail. Shows promotion state with five-glyph
traffic light (`▲ APPROVED`, `▣ AUTHORIZED`, `◉ PENDING`, `▼ REJECTED`,
`● DEFERRED`), required gates with individual pass/fail glyphs, and the
governing ref chain.

Under `--verbose`: governance block and `subject_ref.sha256` digest.

Exit `1` if no artifact is in an approved/authorized state.

#### `builder hitl patch [id]`

Renders HITL patch proposal detail. Shows patch state, target, diff summary,
review notes, and the ref chain. Under `--verbose`: full governance block.

#### `builder hitl governance`

Full governance block audit across all HITL artifact kinds found in
`.builder/`. Reports every capability per artifact, flagging any non-DISABLED
value in red. Exit `1` if any violations found.

#### `builder hitl validate`

Schema validation against all HITL artifact kinds. Delegates to each kind's
`validate_*()` function. Reports errors per artifact with red `✘` lines.
Exit `1` if any validation errors.

---

## `builder profile` — Profile Pack Inspection

**Module:** `builder_ii/profile_tui.py`  
**Artifact kinds / data sources:** Target profiles (from `target_profiles.py`),
agent profiles (from `agent_profiles.py`), verification profiles (from
`verification_profiles.py`), profile packs (from `profile_packs.py`)

### Commands

#### `builder profile status`

Overview of all configured profiles: target profiles (generic / builder /
core), agent profiles (repo_mapper, context_planner, code_reviewer,
patch_planner, verification_planner, handoff_scribe), and any profile pack
artifacts found in `.builder/`.

Flags: `-v` / `--verbose` — show description and authority fields.

#### `builder profile target [name]`

Renders a specific target profile. Shows name, repo path, description, and
whether the repo exists on disk. Valid names: `generic`, `builder`, `core`.
Without an argument, shows all three.

#### `builder profile agent [name]`

Renders agent profile detail: name, description, authority string. Valid
names: `repo_mapper`, `context_planner`, `code_reviewer`, `patch_planner`,
`verification_planner`, `handoff_scribe`. CORE-extension profiles
(`core.invariant_auditor`, `core.patch_planner`, `core.verification_planner`)
are shown if registered.

#### `builder profile verification [target]`

Renders the default verification profile for a given target. Shows profile
kind, state, and the full artifact dict under `--verbose`.

#### `builder profile pack [id]`

Renders profile pack artifacts discovered in `.builder/`. Shows pack name,
target, agent profile binding, and linked artifact refs. Under `--verbose`:
full context pack content and verification profile binding.

#### `builder profile validate`

Schema validation across all profile artifact kinds. Reports per-profile
errors. Exit `1` if any errors.

---

## `builder model` — Model Routing Inspection

**Module:** `builder_ii/model_tui.py`  
**Data sources:** `model_routing.py` (routing table), `model_role_matrix.py`
(role matrix), `model_operating_policy.md` / policy artifacts

### Commands

#### `builder model status`

Overview of the model routing table: each lane (planning, execution, review,
verification, etc.) with its assigned model, provider, and context window.
Shows policy compliance state and whether any lanes have unresolved models.

Flags: `-v` / `--verbose` — show full model metadata per lane.

#### `builder model route [lane]`

Renders a specific lane's routing entry. Shows model name, provider, context
window, temperature policy, and any lane-specific constraints. Without a lane
argument, shows all lanes.

#### `builder model matrix`

Renders the full model role matrix as a table: rows are roles/lanes, columns
are models, cells show assignment state. Useful for spotting gaps or
unexpected assignments.

#### `builder model policy`

Renders the model operating policy artifact or policy document. Shows
governance constraints on model usage: which models are permitted for which
purposes, context window limits, and call authority boundaries.

#### `builder model validate`

Validates routing table and role matrix for internal consistency: all
referenced models exist, all lanes have assignments, no conflicting policies.
Exit `1` if any errors.

---

## `builder promote` — Promotion Pipeline Inspection

**Module:** `builder_ii/promote_tui.py`  
**Artifact kinds:** `promotion_readiness_record`, `hitl_promotion_artifact`,
`promotion_decision_record`, `promotion_compatibility` report

The promotion pipeline is a strictly ordered five-layer stack. An artifact
can only be promoted after clearing all five layers in sequence.

```
Readiness → HITL Gate → Decision → Compatibility → Promoted
```

### Commands

#### `builder promote status`

Full pipeline overview. Three panels — **Readiness** (gate grid), **HITL
Promotion Artifacts** (one row per artifact with state glyph and timestamp),
**Latest Decision** (most recent decision with operator and rationale under
`--verbose`) — followed by a **Pipeline Bar** showing four stages.

Completed stages render in pass-green; pending stages are dim.

Exit `1` if readiness gates are failing.

#### `builder promote readiness`

Loads `promotion_readiness.json` (or calls `evaluate_promotion_readiness()`
live if no artifact is present) and renders every gate by name with a
pass/fail glyph.

Under `--verbose`: the `gate_details` block renders with per-gate
explanations — this is where an operator reads *why* a specific gate is
failing.

Supports both the `gates` dict format (key/bool) and the `gates` list format
(objects with `name`/`passed` fields).

#### `builder promote artifact [id]`

Renders HITL promotion artifacts. Five-state traffic light:

| Glyph | State |
|---|---|
| `▲` | APPROVED / PROMOTED |
| `▣` | AUTHORIZED |
| `◉` | PENDING |
| `▼` | REJECTED |
| `●` | DEFERRED |

The `required_gates` list renders with individual pass/fail glyphs.

Under `--verbose`: governance block and `subject_ref.sha256` digest.

Exit `1` if no artifact is in an approved/authorized state.

#### `builder promote decision [id]`

Renders promotion decision records — the permanent human-written record of
what was decided, by whom, when, and why. The `rationale` field renders in
hint colour (`#94a3b8`). Constraints attached to the approval render in amber
under `--verbose`. The `promotion_ref.sha256` digest provides the
cryptographic link back to the HITL artifact that was approved.

#### `builder promote compatibility [id]`

Tries `promotion_compatibility.check_promotion_compatibility()` first (live
module), then falls back to reading a `promotion_compatibility.json` artifact.

Issues render in red; warnings in amber; a clean report shows one green pass
line. Under `--verbose`: individual `checks` entries with names and pass/fail
glyphs.

#### `builder promote gates`

Fast CI-gate command. Loads readiness, checks `all_gates_passed`/`ready`.

- Clean: one green line, exit `0`.
- Failing: renders **only** the failing gates, exit `1`.

Designed to be the single command in a `make promote-check` target.

---

## `builder postflight` — Execution Postflight Inspection

**Module:** `builder_ii/postflight_tui.py`  
**Artifact kinds:**

| Kind | States | Ref chain |
|---|---|---|
| `builder_ii.execution_postflight_record` | `NOT_RUN` → `RUN_COMPLETE` | `request_ref → receipt_ref → preflight_ref → approval_ref` |
| `builder_ii.execution_verification_record` | `NOT_RUN` → `PASS` / `FAIL` | `request_ref → receipt_ref → postflight_ref` |

### Governance caps (9, all must be DISABLED)

```
runtime_execution    shell_execution      command_execution
model_execution      source_writes        git_mutation
network_access       goose_runtime_activation   deepagents_runtime
```

### Commands

#### `builder postflight status`

Two panels — **Postflight Records** and **Verification Records** — each with
one row per artifact showing state glyph, target name, action count, and
timestamp. A **Pipeline Bar** shows: `Postflight → Verification`.

Exit `1` if neither a `RUN_COMPLETE` postflight nor a `PASS` verification is
present.

#### `builder postflight record [id]`

Full postflight record detail: state, target, refs, governance block, and
validation errors. Governance compact by default; full under `--verbose`.

Exit `1` if `postflight_state` is not `RUN_COMPLETE` or validation errors
exist.

#### `builder postflight verify [id]`

Verification record detail: state, summary (truncated 72 chars), evidence
refs list, ref chain.

Exit `1` if `verification_state` is not `PASS` or validation errors exist.

#### `builder postflight governance`

Full governance block audit across both artifact kinds. All nine caps render
per artifact. Enabled caps or a non-`false` `artifact_is_authority` sets
exit `1`.

#### `builder postflight actions [id]`

Renders the `performed_actions` list from a postflight record.

- String actions: plain `●` bullet
- Dict actions: index, name (48 chars), result label (green for OK/PASS/SUCCESS,
  amber for other), timestamp
- Under `--verbose`: all extra action dict keys as indented hint lines
- `NOT_RUN` state: labels the empty list as expected, not an error

#### `builder postflight refs [id]`

Full ref chain for both artifact kinds in one view. Each ref key renders
with a `↳` connector and its value (or dim `—` if empty).

#### `builder postflight validate`

Delegates to `validate_execution_postflight_record()` and
`validate_execution_verification_record()` from
`execution_postflight_records.py`. Reports each error as a red `✘` line.
Exit `1` if any errors.

---

## `builder goose` — Goose Session Manifest Inspection

**Module:** `builder_ii/goose_tui.py`  
**Artifact kind:** `builder_ii.goose_session_manifest`

### Schema highlights

| Field | Expected value / constraint |
|---|---|
| `current_runtime_state` | Always `DISABLED` |
| `manifest_starts_goose` | Always `false` |
| `requested_runtime_mode` | `"disabled"` or `"read_only"` |
| `agent_profile.name` | Must be a registered agent profile name |
| `allowed_actions` | 3 items (render, validate, link) |
| `denied_actions` | 12 items (all execution / write / mutation actions) |
| `approval_requirements` | 4 items |

### Governance caps

**9 hard-DISABLED caps:**
```
runtime_execution    goose_runtime_start   model_execution
agent_construction   shell_execution       command_execution
source_writes        memory_mutation       commit_push
```

**Special cap (not simply DISABLED):**
```
file_writes = DISABLED_EXCEPT_EXPLICIT_ARTIFACT_OUTPUT_PATH
```

### Links (6 slots)

```
target_bundle    verification_profile    quality_gate
research_plan    handoff                 context_pack
```

### Commands

#### `builder goose status`

Fast operator read: one row per manifest showing agent name, target name,
task summary (72 chars), `current_runtime_state`, link fill ratio (`n/6`),
governance summary, and validation state.

Governance summary: count of non-DISABLED caps with hint to run
`builder goose governance` for detail. Does not list caps in status output.

Exit `1` if `current_runtime_state ≠ DISABLED` or `manifest_starts_goose ≠ false`.

#### `builder goose manifest [id]`

Full manifest detail across seven sections:

1. Task (hint colour, 80 chars)
2. Target (name, repo, description)
3. Agent Profile (name, description, authority)
4. Runtime (state, requested mode, starts_goose flag, audit artifact path)
5. Verification Profile (kind, state — under `--verbose`)
6. Governance compact (enabled caps only; clean = one green line)
7. Validation errors

#### `builder goose links [id]`

Six-slot link table. Filled slots: `↳` arrow + path (50 chars). Empty slots:
`·` bullet + dim `— (empty)`. Header shows fill ratio (`n/6`).

Useful for verifying that all required context artifacts are wired before
attempting runtime activation.

#### `builder goose actions [id]`

Three panels:

1. **Allowed actions** (3) — green `▷` glyphs
2. **Denied actions** (12) — red `◁` glyphs
3. **Approval requirements** (4) — amber `⚠` items

After rendering, imports `_DENIED_ACTIONS` from `goose_session.py` and
checks the manifest's `denied_actions` list against the canonical set.
Any missing required denial renders as amber warning, exit `1`.

#### `builder goose governance`

Full governance block audit. Renders all 9 hard-DISABLED caps, then the
`file_writes` special value with dim lock glyph, then `capability_state`,
`artifact_is_authority`, and `core_workbench_coupling`.

The `file_writes` special value is intentionally distinct from `DISABLED`
and renders with its full value in hint colour rather than a red fail
glyph — it is the governed exception, not a violation.

Exit `1` if any cap deviates from its expected value.

#### `builder goose validate`

Delegates to `validate_goose_session_manifest()` from `goose_session.py`.
Reports errors per manifest. Exit `1` if any errors.

#### `builder goose approval`

Renders the `approval_requirements` list from each manifest — the four
conditions that must be cleared before Goose runtime can be activated.
Shows `current_runtime_state` and `requested_runtime_mode` for context.

This is an informational command; it does not check whether requirements
have been cleared (that is a HITL gate concern).

---

## CI Integration Patterns

### Pre-flight gate chain

```sh
#!/usr/bin/env bash
# Run before any governed execution
set -e
builder promote gates
builder hitl status
builder postflight validate
builder goose status
```

### Makefile targets

```makefile
.PHONY: inspect-all promote-check postflight-check goose-check

inspect-all:
	builder hitl status
	builder profile status
	builder model status
	builder promote status
	builder postflight status
	builder goose status

promote-check:
	builder promote gates

postflight-check:
	builder postflight validate
	builder postflight governance

goose-check:
	builder goose validate
	builder goose governance
```

### Governance audit (all surfaces)

```sh
builder hitl governance
builder postflight governance
builder goose governance
```

All three commands exit `1` on any governance violation, making them
composable into a single governance sweep.

---

## Cross-Module Patterns

### The `--verbose` / `-v` flag

Every command in every module accepts `-v` or `--verbose`. It never changes
behaviour — it expands output only:

- Governance blocks: compact → full (all caps listed)
- Rationale / summary text: hidden → shown
- Verification profile: hidden → shown
- Per-gate explanations: hidden → shown
- Extra action dict keys: hidden → shown
- Digest fields: hidden → shown

### The `[id]` positional argument

Every `record`, `artifact`, `manifest`, `verify`, `links`, `actions`, and
`refs` command accepts an optional `[id]` argument. It is matched against:

- Filename (stem or full)
- `target.name` field
- `agent_profile.name` field (where applicable)

If no match is found, the command falls back to showing all discovered
artifacts of that kind.

### Governance block structure (cross-module)

Every governed artifact in builder-II carries a `governance` block. The
TUI surface enforces a consistent rendering rule:

- A cap with value `DISABLED` renders with dim `■` glyph (pass)
- A cap with any other value renders with amber `⚠` or red `✘` glyph (fail/warn)
- `artifact_is_authority: false` renders with green `✔`
- `artifact_is_authority: <anything else>` renders with red `✘`
- `core_workbench_coupling: NONE` renders with pass lock glyph
- The `file_writes` special value in Goose manifests is the governed exception
  and renders with a distinct dim lock glyph + hint colour, not as a violation

### Ref chain conventions

| Artifact | Ref chain |
|---|---|
| Postflight record | `request_ref → receipt_ref → preflight_ref → approval_ref` |
| Verification record | `request_ref → receipt_ref → postflight_ref` |
| Promotion decision | `promotion_ref` (SHA256 link to HITL promotion artifact) |
| HITL execution record | `request_ref → receipt_ref` |

Ref chain commands (`builder postflight refs`) display the full chain for
both artifact kinds in one view, making cross-artifact traceability visible
at a glance.

---

## What the Surface Deliberately Omits

The TUI inspection surface does **not** provide commands to:

- Write or create any artifact
- Start, stop, or modify Goose sessions
- Promote runtime modes
- Apply patches
- Trigger model calls
- Execute shell commands
- Modify governance caps
- Mutate memory or commit history

All of these require explicit HITL invocation through the governed execution
pipeline. The TUI surface is an observation instrument, not a control surface.

---

## Related Docs

| Doc | Covers |
|---|---|
| [`HITL_EXECUTION_RECORDS.md`](HITL_EXECUTION_RECORDS.md) | HITL execution record schema |
| [`HITL_PROMOTION_ARTIFACTS.md`](HITL_PROMOTION_ARTIFACTS.md) | HITL promotion artifact schema |
| [`EXECUTION_POSTFLIGHT_RECORDS.md`](EXECUTION_POSTFLIGHT_RECORDS.md) | Postflight and verification record schemas |
| [`GOOSE_SESSION.md`](GOOSE_SESSION.md) | Goose session manifest schema |
| [`PROMOTION_READINESS.md`](PROMOTION_READINESS.md) | Promotion readiness gates |
| [`PROMOTION_DECISIONS.md`](PROMOTION_DECISIONS.md) | Promotion decision records |
| [`GOVERNANCE_INVARIANTS.md`](GOVERNANCE_INVARIANTS.md) | Governance block invariants |
| [`OPERATOR_COMMAND_SURFACE.md`](OPERATOR_COMMAND_SURFACE.md) | Full operator command reference |
| [`OPERATOR_GUIDE.md`](OPERATOR_GUIDE.md) | Operator guide and onboarding |
| [`CAPABILITY_PROMOTION.md`](CAPABILITY_PROMOTION.md) | Capability promotion rules |
