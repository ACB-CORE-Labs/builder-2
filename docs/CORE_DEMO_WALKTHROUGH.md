# CORE Demo Walkthrough

This walkthrough is the recordable builder-II demonstration against the real AssetOverflow/core repository. It is designed for an operator who wants to show real governed engineering flow, not a fixture or staged screenshot.

The demo lane itself is generic (plan item 1.8 / B4.9): `builder-platform demo-loop` runs against a temporary detached worktree of any operator-designated local git repository. This walkthrough uses the CORE target profile (`--target-name core`), which adds the AssetOverflow/core identity check and the CORE sensitive-module policy. See "Generic Targets" at the end for the non-CORE form.

## What This Shows

The demo loop creates a detached temporary Git worktree from the current CORE `HEAD`, builds real CORE context artifacts, proposes one low-risk documentation marker patch, requires an explicit governed approval artifact (`builder_ii.hitl_patch_approval`), applies the approved patch inside the temporary worktree, verifies the changed state, rolls it back through the governed rollback lane, and emits a final evidence bundle.

Boundary:

- Source CORE checkout: read-only for the demo.
- Temporary demo worktree: may receive one digest-approved documentation marker patch.
- Sensitive CORE runtime modules: untouched (checked explicitly; verification also requires that nothing but the marker changed at all).
- Commit/push: disabled.
- Model execution, Goose activation, MCP calls, hidden memory, and CORE Workbench/UI coupling: disabled.

This is the product claim the recording should make: builder-II is not a chatbot. It is a governed engineering control plane that binds context, approval, execution, verification, rollback, and evidence.

## Prerequisites

Default CORE checkout:

```bash
/Users/you/Projects/core
```

If CORE is elsewhere, replace the `--target-repo` path. The source checkout may already have local untracked or modified files; the demo creates and mutates only `/tmp/builder-ii-core-demo/demo-worktree`.

Use a fresh evidence directory for a clean recording:

```bash
rm -rf /tmp/builder-ii-core-demo
```

## Interactive Recording Flow

Run each command, pause, and open the named artifacts before moving to the next phase.

### 1. Prepare

```bash
uv run builder-platform demo-loop --target-name core --target-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --phase prepare --force
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
uv run builder-platform demo-loop --target-name core --target-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --phase approve --approve
```

Show:

- `/tmp/builder-ii-core-demo/hitl-patch-approval.json`
- `patch_digest` in the approval and proposal artifacts.

Talk track:

- Model output is not approval.
- The operator approves the exact digest of the patch proposal; the artifact minted here is the same generic `builder_ii.hitl_patch_approval` the hardened apply lane validates everywhere else.
- Without `--approve`, no approval artifact is minted at all — the absence of a valid approval is the unapproved state.
- Approval grants action only for the temporary demo worktree, not for the source checkout, commits, pushes, models, tools, or Goose.

### 3. Apply

```bash
uv run builder-platform demo-loop --target-name core --target-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --phase apply
```

Show:

- `/tmp/builder-ii-core-demo/pre-apply-verification-receipt.json`
- `/tmp/builder-ii-core-demo/patch-apply/patch_apply_receipt.json`
- `/tmp/builder-ii-core-demo/patch-apply/postflight_record.json`
- `/tmp/builder-ii-core-demo/patch-apply/rollback_plan.json`

Optional terminal proof:

```bash
git -C /tmp/builder-ii-core-demo/demo-worktree status --short
```

Talk track:

- Apply is a separate phase from approval.
- The patch application writes a receipt and a rollback plan.
- The temporary worktree now shows the controlled marker change.

### 4. Verify

```bash
uv run builder-platform demo-loop --target-name core --target-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --phase verify
```

Show:

- `/tmp/builder-ii-core-demo/post-apply-verification-receipt.json`

Talk track:

- Executed is not verified.
- The verification receipt checks the marker exists after apply, that nothing except the marker changed, and that sensitive CORE runtime modules remain untouched.
- This is bounded verification, not a broad claim that CORE itself has been certified.

### 5. Roll Back

```bash
uv run builder-platform demo-loop --target-name core --target-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --phase rollback
```

Show:

- `/tmp/builder-ii-core-demo/hitl-rollback-approval.json`
- `/tmp/builder-ii-core-demo/rollback/rollback_receipt.json`
- `/tmp/builder-ii-core-demo/final-postflight.json`

Terminal proof:

```bash
git -C /tmp/builder-ii-core-demo/demo-worktree status --short
```

Talk track:

- Every forward operator has a corrective counterpart.
- Rollback requires its own distinct governed approval bound to the rollback plan.
- The rollback receipt records the pre-rollback and post-rollback Git status.
- The final postflight proves the temporary demo worktree is clean.

### 6. Finalize

```bash
uv run builder-platform demo-loop --target-name core --target-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --phase finalize
uv run builder-platform validate-demo-loop /tmp/builder-ii-core-demo/demo-loop-report.json
```

Show:

- `/tmp/builder-ii-core-demo/demo-loop-report.json`
- `/tmp/builder-ii-core-demo/chain-verification-report.json`
- `/tmp/builder-ii-core-demo/artifact-index.json`
- `/tmp/builder-ii-core-demo/DEMO_EVIDENCE.md`

Terminal proof:

```bash
git -C /Users/you/Projects/core status --short
git -C /tmp/builder-ii-core-demo/demo-worktree status --short
```

Talk track:

- The report links the artifacts by kind and digest.
- Chain verification and artifact indexing make the run reviewable after the recording — the chain includes both governing approvals.
- The source CORE status is independent of the demo; the demo mutation target is clean after rollback.

## One-Command Recording Pass

Once the interactive flow is familiar, use the alias:

```bash
uv run builder-platform wow --target-name core --target-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --approve --force
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
- `hitl-patch-approval.json`
- `pre-apply-verification-receipt.json`
- `patch-apply/patch_apply_receipt.json`
- `patch-apply/postflight_record.json`
- `patch-apply/rollback_plan.json`
- `post-apply-verification-receipt.json`
- `hitl-rollback-approval.json`
- `rollback/rollback_receipt.json`
- `final-postflight.json`
- `chain-verification-report.json`
- `artifact-index.json`
- `demo-loop-report.json`

The cleanest close for the recording is to show `DEMO_EVIDENCE.md`, then the final two status commands: source CORE unchanged by the demo path, temporary demo worktree clean after rollback.

## Generic Targets

The same governed loop runs against any local git checkout — no CORE identity required:

```bash
uv run builder-platform demo-loop --target-name my-project --target-repo /path/to/my-project --output-dir /tmp/builder-ii-demo --phase prepare --force
```

Differences from the CORE profile:

- No repository identity check (the generic spec requires only an existing local git checkout).
- No sensitive-module prefix list; verification still requires that nothing except the demo marker changed in the worktree.
- The marker defaults to `docs/builder_ii_demo_marker.md` and can be relocated with `--marker-path` (relative paths only; traversal, `.git/`, and sensitive-prefix locations are refused).

Everything else is identical: detached worktree, digest-bound proposal, governed approval, receipted apply, bounded verification, approved rollback, final clean postflight, chain-verified evidence bundle.
