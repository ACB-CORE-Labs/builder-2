# Runtime Governance Release Audit

**Date:** 2026-06-26
**Branch:** `pr-ab-runtime-governance-release-audit`
**Status:** Foundation complete, all runtime capabilities disabled by default.

---

## 1. Platform Identity and Scope

- **builder-II is a generic governed local agent/developer platform.**
- **builder-II is not CORE, not CORE Workbench/UI/UX, and not a second CORE runtime.**
- **CORE is only a target profile.**

builder-II governs local agent workflows. It provides artifact schemas, CLI surfaces, promotion ladders, and governance contracts. It does not conflate its own governance boundary with CORE Workbench, CORE UI/UX, or any second CORE runtime. The `core` target name is a target profile only; it carries no CORE workbench coupling (`core_workbench_coupling: NONE`).

---

## 2. HITL Command Execution Spec Audit

**Doc:** `docs/HITL_COMMAND_EXECUTION.md`
**Module:** `builder_ii/hitl_command_execution.py`
**Tests:** `tests/test_hitl_command_execution.py`

The HITL command execution spec defines the design-only artifact kind
`builder_ii.hitl_command_execution_spec` for future governed shell command execution.

### Current State

| Field | Value |
|---|---|
| `current_state.mode` | `DESIGN_ONLY` |
| `current_state.runtime` | `DISABLED` |
| `governance.shell_execution` | `DISABLED` |
| `governance.command_execution` | `DISABLED` |
| `governance.model_execution` | `DISABLED` |
| `governance.subprocess_execution` | `DISABLED` |
| `governance.goose_runtime_activation` | `DISABLED` |
| `governance.deepagents_runtime` | `DISABLED` |
| `governance.source_writes` | `DISABLED` |
| `governance.artifact_is_authority` | `false` |
| `governance.core_workbench_coupling` | `NONE` |

### Allowed Future Transitions (not yet enabled)

1. command proposal
2. approval record
3. preflight record
4. explicit execution request
5. execution receipt
6. postflight/handoff

### Required Future Gates (before any promotion)

- docs
- tests
- command surface
- failure mode
- human approval boundary
- output artifact
- rollback path
- verification path

---

## 3. HITL Execution Request/Receipt Artifacts Audit

**Doc:** `docs/HITL_COMMAND_EXECUTION.md`
**Module:** `builder_ii/hitl_command_execution.py`
**Related modules:** `builder_ii/receipt_records.py`, `builder_ii/approval_records.py`, `builder_ii/preflight_records.py`

Execution request and receipt artifacts are **design-only records only**. No execution request is processed, no receipt is generated at runtime, and no subprocess is spawned.

### Current State

- `execution_request` artifact: **design spec only** — not produced by an active runtime
- `execution_receipt` artifact: **design spec only** — not produced by an active runtime
- `approval_record`: schema complete, validated, no authority granted
- `preflight_record`: schema complete, validated, no authority granted
- `receipt_record`: schema complete, validated, no authority granted

### Denied Behaviors (execution request/receipt phase)

- no subprocess
- no shell execution
- no command execution
- no model execution
- no source writes
- no git mutation
- no commit/push
- no network/MCP execution
- no Goose runtime activation
- no deepagents runtime

---

## 4. HITL Patch Application Spec Audit

**Doc:** `docs/HITL_COMMAND_EXECUTION.md`
**Module:** `builder_ii/hitl_command_execution.py`
**Related docs:** `docs/RUNTIME_PROMOTION.md` §patch_proposal, §hitl_write

Patch application is explicitly not promoted. The platform carries the design
specification for a future patch proposal / hitl_write promotion path.

### Current State

| Capability | Status |
|---|---|
| Patch application | `DISABLED` |
| Source writes | `DISABLED` |
| Git mutation | `DISABLED` |
| Commit/push | `DISABLED` |
| Autonomous writes | `DISABLED` |

### Required gates before patch_proposal promotion

- patch proposal artifact
- changed-file list
- risk explanation
- rollback plan
- verification plan
- human approval boundary

### Required gates before hitl_write promotion

- approved patch artifact
- exact patch matching
- apply audit artifact
- verification after apply
- rollback command or revert path
- postflight handoff

---

## 5. Rollback Plan/Receipt Artifacts Audit

**Doc:** `docs/RUNTIME_PROMOTION.md` §Rollback requirement

Every future promoted runtime mode must define rollback behavior before it can run.
No runtime mode is currently promoted; therefore no rollback path is active.

### Defined rollback shapes (spec-only, not active)

| Mode | Rollback |
|---|---|
| read-only audit | delete emitted audit artifact; no source rollback |
| bounded inspection | delete emitted inspection artifact; no source rollback |
| command proposal | discard proposal artifact |
| verification execution | record command output and failure state; no source rollback expected |
| patch proposal | discard proposal artifact |
| hitl write | revert patch or restore pre-apply state |
| model routing | discard routing artifact; record no execution if no model call approved |

### Rollback receipt artifacts

Rollback receipts are design artifacts only. No rollback is executed or recorded
at runtime in the current foundation state.

---

## 6. Command Surface Audit

**Doc:** `docs/COMMAND_SURFACE_AUDIT.md`
**Tests:** `tests/test_command_surface_audit.py`
**Source:** `pyproject.toml [project.scripts]`

All registered CLI entry points are governance-aware read/inspect/plan surfaces.
None of the registered commands enable shell execution, model execution, patch
application, autonomous writes, Goose runtime activation, or deepagents runtime.

### Registered command surfaces

#### Platform Setup / Runtime Policy
- `builder`
- `builder-runtime`
- `builder-lanes`
- `builder-tools`
- `builder-git-state`

#### Target / Profile / Context
- `builder-context`
- `builder-targets`

#### Artifact Chain / Governance Records
- `builder-records`
- `builder-receipt`
- `builder-chain`
- `builder-index`
- `builder-state-index`
- `builder-snapshot`

#### Promotion / Readiness / Decision
- `builder-preflight`
- `builder-promotion`
- `builder-promotion-decision`

#### Inspection / Read-Only Candidate
- `builder-readonly`

#### Research / Performance / Verification
- `builder-agent`
- `builder-bundle`
- `builder-quality`
- `builder-research`
- `builder-performance`
- `builder-verification`

#### Notes / Handoff / Intake
- `builder-handoff`
- `builder-intake`
- `builder-notes`

#### Deepagents / Goose Optional Bridge Surfaces
- `builder-bridge`
- `builder-goose`
- `builder-deepagents`

### Command Surface Invariants

- no shell execution is enabled
- no model execution is enabled
- no patch application is enabled
- no autonomous writes are enabled
- no Goose runtime activation is enabled
- no deepagents runtime is enabled
- builder-II is not CORE Workbench/UI
- CORE is only a target profile
- rollback execution is not enabled
- voice/TTS/STT runtime is not enabled

---

## 7. Registry Closure Audit

**Tests:** `tests/test_registry_closure.py`
**Modules:** `builder_ii/artifact_index_records.py`, `builder_ii/artifact_chain_verification.py`

The artifact index registry (`_VALIDATORS`) and the chain verification registry
(`VALIDATORS`) are kept in strict parity. Every governed artifact kind registered
in one registry must be registered in the other.

### Registered and verified kinds (both registries)

- `builder_ii.target_profile`
- `builder_ii.verification_profile`
- `builder_ii.context_pack_record`
- `builder_ii.agent_profile_record`
- `builder_ii.git_state_record`
- `builder_ii.research_plan`
- `builder_ii.research_adapter`
- `builder_ii.performance_measurement`
- `builder_ii.readonly_inspection_promotion_spec`
- `builder_ii.readonly_inspection_report`

### Registry Closure Invariant

No artifact kind may appear in the index registry but not the chain registry,
and vice versa. Tests in `tests/test_registry_closure.py` enforce this invariant
on every CI run.

---

## 8. No-Runtime / No-Authority Claims

### No-Runtime Claims

The following capabilities are **not enabled** in the current foundation release:

| Capability | Status |
|---|---|
| Shell execution | **NOT ENABLED** |
| Model execution | **NOT ENABLED** |
| Patch application | **NOT ENABLED** |
| Autonomous writes | **NOT ENABLED** |
| Goose runtime activation | **NOT ENABLED** |
| deepagents runtime | **NOT ENABLED** |
| Rollback execution | **NOT ENABLED** |
| Voice/TTS/STT runtime | **NOT ENABLED** |
| Commit/push automation | **NOT ENABLED** |
| MCP execution | **NOT ENABLED** |
| CORE Workbench/UI coupling | **NONE** |

### No-Authority Claims

- Artifact validity does not grant runtime authority.
- `artifact_is_authority` is `false` on every governed artifact.
- `core_workbench_coupling` is `NONE` on every governed artifact.
- Promotion state is tracked; no capability is promoted to `enabled` at this time.
- Design-only artifacts describe future governance contracts; they do not activate those contracts.

### Cross-artifact governance invariants

Every governed artifact surface enforces:

```text
model_execution       = DISABLED
agent_construction    = DISABLED
shell_execution       = DISABLED
command_execution     = DISABLED
source_writes         = DISABLED
memory_mutation       = DISABLED
artifact_is_authority = false
core_workbench_coupling = NONE
```

See `docs/GOVERNANCE_INVARIANTS.md` for the full cross-artifact invariant definition.

---

## 9. Future Promotion Ladder

**Doc:** `docs/RUNTIME_PROMOTION.md`
**Doc:** `docs/CAPABILITY_PROMOTION.md`

### Promotion States

```text
unavailable
spec_only
smoke_only
artifact_only
validation_only
read_only_runtime_candidate
hitl_runtime_candidate
enabled
```

### Current Position of Each Runtime Capability

| Capability | Current State |
|---|---|
| bounded read-only inspection | `read_only_runtime_candidate` |
| command proposal | `spec_only` |
| HITL command execution | `spec_only` |
| HITL patch application | `spec_only` |
| verification execution | `spec_only` |
| model routing | `spec_only` |
| Goose runtime | `spec_only` |
| deepagents runtime | `spec_only` |
| voice/TTS/STT | `spec_only` |
| rollback execution | `spec_only` |

### Required Gates Before Any Promotion to `enabled`

Every capability must accumulate all of the following before it may be promoted:

1. **docs** — specification document in `docs/`
2. **tests** — automated test coverage, including denied-action tests
3. **command surface** — CLI entry point in `pyproject.toml`
4. **failure mode** — defined failure behavior and recovery path
5. **human approval boundary** — explicit HITL gate
6. **output artifact** — governed artifact capturing execution result
7. **rollback path** — defined rollback behavior
8. **verification path** — defined post-execution verification

### Next Promotion Candidates

- HITL command execution spec → `artifact_only`
- Rollback artifact schema → `artifact_only`
- HITL patch spec → `artifact_only`

---

## 10. Release Verification Checklist

Run the following commands to verify the current foundation state:

```bash
# Run full test suite
uv run pytest -q

# Run this release audit test specifically
uv run pytest tests/test_runtime_governance_release_audit.py -q

# Run with CORE_REPO_PATH set
CORE_REPO_PATH=. uv run pytest -q

# Verify no trailing whitespace
git diff --check

# Validate artifact index
builder-index validate <artifact-index>

# Verify artifact chain
builder-chain verify <artifact-path>...

# Validate promotion readiness
builder-promotion record --capability-name <name> --target <target>

# Record promotion decision
builder-promotion-decision record <promotion-readiness>

# Validate state index
builder-state-index validate <state-index>

# Validate snapshot
builder-snapshot validate <snapshot>

# Run bounded read-only inspection
builder-readonly report --target <target> --purpose review --path <explicit-file> --output <inspection-report>
builder-readonly validate <inspection-report>
```

---

## 11. Summary

builder-II is a generic governed local agent/developer platform. The current
foundation release is **complete and disabled-by-default**:

- All runtime capabilities are gated by docs, tests, command surface, failure
  mode, human approval boundary, output artifact, rollback path, and
  verification path.
- No capability has been promoted to `enabled`.
- Every governed artifact carries `artifact_is_authority: false` and
  `core_workbench_coupling: NONE`.
- builder-II is not CORE, not CORE Workbench/UI/UX, and not a second CORE
  runtime. CORE is only a target profile.
