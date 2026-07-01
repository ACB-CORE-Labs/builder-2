# CORE Demo Walkthrough

This walkthrough is the recordable builder-II demonstration against the real AssetOverflow/core repository. It is designed for an operator who wants to show real governed engineering flow, not a fixture or staged screenshot.

## What This Shows

The demo loop creates a detached temporary Git worktree from the current CORE `HEAD`, builds real CORE context artifacts, proposes one low-risk documentation marker patch, requires an explicit approval artifact, applies the approved patch inside the temporary worktree, verifies the changed state, rolls it back, and emits a final evidence bundle.

Boundary:

- Source CORE checkout: read-only for the demo.
- Temporary CORE worktree: may receive one digest-approved documentation marker patch.
- Sensitive CORE runtime modules: untouched.
- Commit/push: disabled.
- Model execution, Goose activation, MCP calls, hidden memory, and CORE Workbench/UI coupling: disabled.

This is the product claim the recording should make: builder-II is not a chatbot. It is a governed engineering control plane that binds context, approval, execution, verification, rollback, and evidence.

## Prerequisites

Default CORE checkout:

```bash
/Users/kaizenpro/Projects/core
```

If CORE is elsewhere, replace the `--core-repo` path. The source checkout may already have local untracked or modified files; the demo creates and mutates only `/tmp/builder-ii-core-demo/core-worktree`.

Use a fresh evidence directory for a clean recording:

```bash
rm -rf /tmp/builder-ii-core-demo
```

## Interactive Recording Flow

Run each command, pause, and open the named artifacts before moving to the next phase.

### 1. Prepare

```bash
uv run builder-platform demo-loop --core-repo /Users/kaizenpro/Projects/core --output-dir /tmp/builder-ii-core-demo --phase prepare --force
```

Show:

- `/tmp/builder-ii-core-demo/preflight.json`
- `/tmp/builder-ii-core-demo/repo-map.json`
- `/tmp/builder-ii-core-demo/context-pack.json`
- `/tmp/builder-ii-core-demo/deterministic-planner.json`
- `/tmp/builder-ii-core-demo/hitl-patch-proposal.json`
- `/tmp/builder-ii-core-demo/DEMO_EVIDENCE.md`

Talk track:

- This is real CORE `HEAD`, cloned into a detached worktree for governed mutation.
- The source checkout is not being used as the mutation target.
- The proposed change is visible before approval.
- The approval digest is the boundary between proposal and action.

### 2. Approve

```bash
uv run builder-platform demo-loop --core-repo /Users/kaizenpro/Projects/core --output-dir /tmp/builder-ii-core-demo --phase approve --approve
```

Show:

- `/tmp/builder-ii-core-demo/core-demo-approval.json`
- `patch_digest` in the approval and proposal artifacts.

Talk track:

- Model output is not approval.
- The operator approves the exact digest of the patch proposal.
- Approval grants action only for the temporary CORE worktree, not for the source checkout, commits, pushes, models, tools, or Goose.

### 3. Apply

```bash
uv run builder-platform demo-loop --core-repo /Users/kaizenpro/Projects/core --output-dir /tmp/builder-ii-core-demo --phase apply
```

Show:

- `/tmp/builder-ii-core-demo/pre-apply-verification-receipt.json`
- `/tmp/builder-ii-core-demo/patch-apply/patch_apply_receipt.json`
- `/tmp/builder-ii-core-demo/patch-apply/postflight_record.json`
- `/tmp/builder-ii-core-demo/patch-apply/rollback_plan.json`

Optional terminal proof:

```bash
git -C /tmp/builder-ii-core-demo/core-worktree status --short
```

Talk track:

- Apply is a separate phase from approval.
- The patch application writes a receipt and a rollback plan.
- The temporary worktree now shows the controlled marker change.

### 4. Verify

```bash
uv run builder-platform demo-loop --core-repo /Users/kaizenpro/Projects/core --output-dir /tmp/builder-ii-core-demo --phase verify
```

Show:

- `/tmp/builder-ii-core-demo/post-apply-verification-receipt.json`

Talk track:

- Executed is not verified.
- The verification receipt checks the marker exists after apply and that sensitive CORE runtime modules remain untouched.
- This is bounded verification, not a broad claim that CORE itself has been certified.

### 5. Roll Back

```bash
uv run builder-platform demo-loop --core-repo /Users/kaizenpro/Projects/core --output-dir /tmp/builder-ii-core-demo --phase rollback
```

Show:

- `/tmp/builder-ii-core-demo/rollback/rollback_receipt.json`
- `/tmp/builder-ii-core-demo/final-postflight.json`

Terminal proof:

```bash
git -C /tmp/builder-ii-core-demo/core-worktree status --short
```

Talk track:

- Every forward operator has a corrective counterpart.
- The rollback receipt records the pre-rollback and post-rollback Git status.
- The final postflight proves the temporary CORE worktree is clean.

### 6. Finalize

```bash
uv run builder-platform demo-loop --core-repo /Users/kaizenpro/Projects/core --output-dir /tmp/builder-ii-core-demo --phase finalize
uv run builder-platform validate-demo-loop /tmp/builder-ii-core-demo/core-demo-loop-report.json
```

Show:

- `/tmp/builder-ii-core-demo/core-demo-loop-report.json`
- `/tmp/builder-ii-core-demo/chain-verification-report.json`
- `/tmp/builder-ii-core-demo/artifact-index.json`
- `/tmp/builder-ii-core-demo/DEMO_EVIDENCE.md`

Terminal proof:

```bash
git -C /Users/kaizenpro/Projects/core status --short
git -C /tmp/builder-ii-core-demo/core-worktree status --short
```

Talk track:

- The report links the artifacts by kind and digest.
- Chain verification and artifact indexing make the run reviewable after the recording.
- The source CORE status is independent of the demo; the demo mutation target is clean after rollback.

## One-Command Recording Pass

Once the interactive flow is familiar, use the alias:

```bash
uv run builder-platform wow --core-repo /Users/kaizenpro/Projects/core --output-dir /tmp/builder-ii-core-demo --approve --force
```

This runs prepare, approval, apply, verification, rollback, and finalize in one pass. Use it when the screen recording needs one continuous terminal narrative rather than phase-by-phase inspection.

## Evidence Bundle

The key output is:

```bash
/tmp/builder-ii-core-demo/DEMO_EVIDENCE.md
```

It lists each JSON artifact and digest. The core proof files are:

- `preflight.json`
- `repo-map.json`
- `context-pack.json`
- `deterministic-planner.json`
- `hitl-patch-proposal.json`
- `core-demo-approval.json`
- `pre-apply-verification-receipt.json`
- `patch-apply/patch_apply_receipt.json`
- `patch-apply/postflight_record.json`
- `patch-apply/rollback_plan.json`
- `post-apply-verification-receipt.json`
- `rollback/rollback_receipt.json`
- `final-postflight.json`
- `chain-verification-report.json`
- `artifact-index.json`
- `core-demo-loop-report.json`

The cleanest close for the recording is to show `DEMO_EVIDENCE.md`, then the final two status commands: source CORE unchanged by the demo path, temporary CORE worktree clean after rollback.
