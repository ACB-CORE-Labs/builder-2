# Operator Quickstart

This guide shows the complete operator golden path lane for builder-II and points to the CORE demo loop used for a real-world recording.

builder-II is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench, not CORE UI/UX, and not a second CORE runtime. CORE is only a target profile.

For the canonical taxonomy of operator commands and governance boundaries, see the [Operator Command Surface Index](COMMAND_AUTHORITY.md) and [Platform Completion Audit](PLATFORM_COMPLETION_AUDIT.md).

## Purpose

The B9 governed operator quickstart (golden path) gives an operator one coherent local demonstration of the platform state, next required sequence, and a deterministic map of the setup closure without parsing the underlying truth matrices manually.

This lane is artifact-first and human-governed. It derives entirely from the truth matrix, command authority, and actual local evidence.

## Golden Path

The golden path operates without starting runtimes, calling models, modifying the target repository, or claiming authority.

```bash
builder-platform status
builder-platform operator-status --output .builder/artifacts/operator-status.json
builder-platform next --output .builder/artifacts/operator-next.json
builder-platform golden-path --target builder --output-dir .builder/artifacts/b9-golden-path
builder-platform validate-golden-path .builder/artifacts/b9-golden-path/golden-path-report.json
```

## Clean-Clone Onboarding Smoke Gate

`scripts/clean-clone-smoke.sh` is the repeatable gate for the "clone the repo, onboard in ≤30 minutes" claim. It clones the repo fresh into a scratch directory, runs the README "First run" golden path end to end, then runs one complete generic governed patch loop (propose → approve → verify → apply → rollback) against a throwaway fixture repo — with `swift`/`xcodebuild` shadowed by hard-failing stubs for the whole run, so a pass also proves there is no Xcode/Swift toolchain dependency on the onboarding path.

```bash
bash scripts/clean-clone-smoke.sh
```

Use `--keep` to preserve the scratch workdir and per-step logs for inspection, `--workdir DIR` to pick a fixed location, `--source PATH_OR_URL` to smoke-test a different remote or tag, and `--budget-seconds N` to change the onboarding-claim ceiling (default 1800s / 30 minutes). Run this before and after any change to onboarding docs, config defaults, or the CLI surfaces it exercises — it is the only defense against onboarding regressions between releases.

## CORE Demo Loop

For a recordable real-world walkthrough against AssetOverflow/core, use the CORE demo loop instead of a fixture:

```bash
uv run builder-platform demo-loop --core-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --phase prepare --force
uv run builder-platform demo-loop --core-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --phase approve --approve
uv run builder-platform demo-loop --core-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --phase apply
uv run builder-platform demo-loop --core-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --phase verify
uv run builder-platform demo-loop --core-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --phase rollback
uv run builder-platform demo-loop --core-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --phase finalize
uv run builder-platform validate-demo-loop /tmp/builder-ii-core-demo/core-demo-loop-report.json
```

The same loop can be run as a one-command recording pass:

```bash
uv run builder-platform wow --core-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --approve --force
```

See [CORE Demo Walkthrough](CORE_DEMO_WALKTHROUGH.md) for the narrated flow, artifact map, and evidence-showing script.

## Read-Only Founder Demo

For a passive, read-only inspection/planning demo scoped to the `core` target profile (no runtime,
model, shell, Goose, or deepagents execution, no target-repository writes), run:

```bash
uv run builder-targets readonly-founder-demo core --output .builder/demos/core-readonly --force
```

See [CORE Read-Only Founder Demo](demos/CORE_READONLY_FOUNDER_DEMO.md) for the full artifact map and
event-ledger/chain verification walkthrough.

## What the Golden Path Report Proves

The golden path report explicitly categorizes every platform capability as:
- `exercised`
- `validated_only`
- `skipped_disabled`
- `skipped_missing_evidence`
- `unavailable`
- `not_applicable`

It provides a no-mutation proof and an explicit summary of all disabled runtime authorities, ensuring complete operator transparency.

## Runtime Boundary

This quickstart lane does not:
- execute shell commands
- import or use subprocess
- activate Goose
- activate or delegate to deepagents
- execute model/runtime work
- write to the target repository
- touch Deephaven
- grant runtime authority
- claim autonomous writes
- invoke MCP or external tools
- use hidden memory or vector stores

The CORE demo loop is a separate governed execution lane. It may apply and roll back one digest-approved temporary documentation marker inside a detached CORE worktree only; it does not mutate the source CORE checkout, commit, push, call models, activate Goose, invoke MCP, or write hidden memory.

## Human Responsibility

The operator must inspect the generated JSON artifacts, read the next suggested action, and manually initiate any subsequent execution layers or governed setup flows using the exact explicit commands recommended by the `operator-next` primitive.

Any future execution or source write remains strictly HITL-gated by the B1-B8 execution primitives.
