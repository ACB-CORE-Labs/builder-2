# builder-II Operator Playbook

This playbook documents the standard development loop and governance boundaries for operators running `builder-II`. 

## Core Governance Philosophy (No-Runtime Boundary)

`builder-II` operates strictly as a **no-runtime, artifact-only governance control plane** by default. None of the commands in the active operating loop trigger autonomous execution or mutate the target repository.

> [!IMPORTANT]
> **Strict Action Denials**:
> The active operating loop explicitly denies and does not perform:
> - **Shell Execution**: No arbitrary commands or scripts are run on the system.
> - **Source Writes**: No source code files in the target repository are mutated.
> - **Model Execution**: No direct LLM/model calls are made.
> - **Goose Runtime Activation**: No active Goose runtime sessions are started.
> - **Deepagents Construction**: No autonomous planning subagents are built or executed.
> - **Memory Mutation**: No persistent agent memory graph mutation is performed.
> - **Commit/Push Automation**: No git commits or pushes are automated.
> - **CORE Workbench Coupling**: No integration or execution dependency on CORE Workbench/UI.

---

## Active Operator Loop (Artifact-Only)

Operators compose the following sequence of commands to inspect configuration, package context, generate readiness plans, and validate artifacts. All generated artifacts are located in `.builder/artifacts/` or custom paths:

### 1. Doctor & Verification Checks
Validate system configuration and dependencies without changing files.
```bash
builder-setup plan --output .builder/artifacts/setup-plan.json
builder-setup validate-plan .builder/artifacts/setup-plan.json
builder doctor
builder-targets validate
builder-agent validate
builder-verification validate
```

### 2. Context & Target Bundling
Package relevant changed files and generate target-specific bundles.
```bash
builder-context pack --target builder --changed --task "..."
builder-verification artifact builder_full --target builder --task "..." --output .builder/artifacts/verification-profile.json
builder-verification validate .builder/artifacts/verification-profile.json
builder-bundle create --target builder --agent patch_planner --task "..." --output .builder/artifacts/target-bundle.json
builder-bundle validate .builder/artifacts/target-bundle.json
```

### 3. Planning & Quality Gates
Construct plans for research, verification quality gates, and handoffs.
```bash
builder-research plan --target generic --profile research_planner --task "..." --output .builder/artifacts/research-plan.json
builder-research validate .builder/artifacts/research-plan.json
builder-quality plan --target builder --profile builder_full --task "..." --output .builder/artifacts/quality-gate.json
builder-quality validate .builder/artifacts/quality-gate.json
builder-notes handoff --target builder --agent handoff_scribe --task "..." --summary "..." --output .builder/artifacts/handoff.json
builder-notes validate .builder/artifacts/handoff.json
```

### 4. Goose manifest and dry-run audits
Specify read-only inspection sessions and run static policy compliance checks.
```bash
builder-goose manifest --target builder --agent patch_planner --mode read_only --task "..." --output .builder/artifacts/goose-session.json
builder-goose validate .builder/artifacts/goose-session.json
builder-goose readonly-audit .builder/artifacts/goose-session.json --output .builder/artifacts/goose-readonly-audit.json
builder-goose validate-audit .builder/artifacts/goose-readonly-audit.json
builder-goose inspect-readonly .builder/artifacts/goose-session.json --read-file README.md --output .builder/artifacts/goose-readonly-inspection.json
builder-goose validate-inspection .builder/artifacts/goose-readonly-inspection.json
```

### 5. Policy rendering and readiness audits
Produce policy and readiness specs for optional deepagents planning bridge.
```bash
builder-deepagents policy --target builder --task "..." --output .builder/artifacts/deepagents-policy.json
builder-deepagents validate .builder/artifacts/deepagents-policy.json
builder-deepagents readiness --mode metadata_only --output .builder/artifacts/deepagents-readiness.json
builder-deepagents validate-readiness .builder/artifacts/deepagents-readiness.json
builder-bridge render patch_planner --target builder --format json --output .builder/artifacts/bridge-spec.json
builder-bridge validate-artifact .builder/artifacts/bridge-spec.json
```

---

## Future Runtime Capabilities (NOT Enabled / Design Only)

The following commands are specified as future capabilities under the `MASTERPIECE_PLAN.md` roadmap. They are **not enabled** in the current release and require formal capability promotion gates to be satisfied before use:

```bash
# Future Read-Only Runtime Start
builder-goose start-readonly --manifest .builder/artifacts/goose-session.json

# Future Command Proposal & HITL Verification Execution
builder-approval propose-command --target builder --command "uv run pytest"
builder-approval approve .builder/artifacts/command-proposal.json
builder-run approved .builder/artifacts/command-proposal.json

# Future Patch Proposal & HITL Patch Application
builder-approval propose-patch --target builder --task "..."
builder-approval approve .builder/artifacts/patch-proposal.json
builder-apply approved .builder/artifacts/patch-proposal.json

# Future Push Automation
git push
```
These runtime operations will remain disabled and run-blocked until proper state indexes, git-state tracking, and promotion decisions are integrated.
