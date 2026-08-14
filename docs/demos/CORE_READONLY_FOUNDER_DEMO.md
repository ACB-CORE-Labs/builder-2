# CORE Read-Only Founder Demo

This document describes the passive read-only founder inspection and planning demo for the `core` target profile.

## Architecture & Passive Governance

`builder-II` is a generic governed local agent and developer platform. It is strictly separated from CORE:
- `builder-II` is **not** CORE.
- `builder-II` is **not** a CORE Workbench, UI, or UX.
- `builder-II` is **not** a CORE runtime execution engine.
- CORE appears in `builder-II` **only** as a target profile and adapter (`TargetName = "core"`).

To guarantee strict architectural separation and safety, the passive founder demo enforces the following forbidden authority boundaries within every generated planning artifact:

```json
{
  "governance": {
    "runtime_authority": "DISABLED",
    "model_execution": "DISABLED",
    "shell_execution": "DISABLED",
    "mcp": "DISABLED",
    "goose_runtime": "DISABLED",
    "deepagents_runtime": "DISABLED",
    "source_writes": "DISABLED",
    "commit_push_automation": "DISABLED",
    "core_workbench_coupling": "NONE"
  }
}
```

No code execution, shell commands, LLM loops, or repository mutations occur during demo generation or inspection planning.

## Generating the Demo

Generate the passive read-only founder demo artifacts using the following command:

```bash
uv run builder-targets readonly-founder-demo core --output .builder/demos/core-readonly --force
```

This command runs `generate_readonly_founder_demo(...)` with the `--force` flag (to ensure clean/idempotent recreation by clearing any stale files in that directory), emits only passive planning artifacts, and authorizes zero runtime, model, shell, Goose, or deepagents execution.

## Generated Artifacts

When generating the read-only founder demo, the following governed sequence of artifacts is produced inside the authorized workspace (`.builder/demos/core-readonly` or the directory specified via `--output`):

1. **Target Profile (`target-profile.json`)**: Resolves target repository path and capabilities.
2. **Workflow Session (`artifacts/workflow-session.json`)**: Tracks session metadata (`wf-<target>-readonly-founder-demo`).
3. **Target Inspection Plan (`CORE_INSPECTION_PLAN_v1.json`)**: Outlines read-only inspection scope (`README.md`, `AGENTS.md`, `GROK.md`, `CLAUDE.md`, `docs`, `tests`) and notes checking deterministic verification gates (`versor_condition(F) < 1e-6`). Requires `target_profile_ref` and `workflow_session_ref`.
4. **Target Patch Proposal (`CORE_PATCH_PROPOSAL_v1.json`)**: Proposes passive documentation and fixture alignments while preserving exact CGA recall and temperature 0 deterministic invariants. Cryptographically references the inspection plan. Requires `target_profile_ref`, `workflow_session_ref`, and `inspection_plan_ref`.
5. **Target Verification Plan (`CORE_VERIFICATION_PLAN_v1.json`)**: Defines pass criteria and verification commands (`builder verify <changed-path>`, `uv run pytest -q focused_suite`). Cryptographically references the patch proposal. Requires `target_profile_ref`, `workflow_session_ref`, and `patch_proposal_ref`.
6. **Event Ledger (`artifacts/event-ledger.json`) & Replay Report (`artifacts/ledger-replay-report.json`)**: The immutable audit spine recording state transitions: `initialized` -> `planned` -> `promoted` -> `candidate`.
7. **Workflow Status (`artifacts/workflow-status.json`)**: Mutable projection derived from replaying the event ledger.

> [!IMPORTANT]
> **Passive Transition Only**: The transition from `planned` to `promoted` (`workflow_promoted`) is a passive workflow-state transition recording the patch proposal only. **No authority promotion occurs at this stage.** All runtime execution, model execution, shell execution, MCP execution, and target repository writes remain completely disabled.

## Verifying Generated Outputs

You can verify the generated outputs using existing `builder-II` verification commands without triggering runtime execution or side effects.

### 1. Replay the Event Ledger
Verify the cryptographic event chain and derive the current stage:
```bash
uv run builder-ledger replay wf-core-readonly-founder-demo --workflows-dir .builder/demos
```

### 2. Verify Artifact Chain Integrity
Verify cryptographic SHA-256 references across the generated artifact chain using the CLI tool:
```bash
uv run builder-workflow verify-chain wf-core-readonly-founder-demo --workflows-dir .builder/demos
```

Alternatively, you can run the validation programmatically:
```bash
uv run python -c "
from pathlib import Path
from builder_ii.core.artifact_chain_verification import verify_artifact_chain

out = Path('.builder/demos/core-readonly')
files = list((out / 'artifacts').glob('*.json')) + list((out / 'events').glob('*.json'))
report = verify_artifact_chain(files)
print('Valid:', report['valid'])
if report['errors']:
    print('Errors:', report['errors'])
"
```
