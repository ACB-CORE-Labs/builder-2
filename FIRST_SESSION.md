# Your first builder-II session

This is the single validated path from a clean `git clone` to one complete governed patch
loop — propose, approve, verify, apply, roll back — with a receipt at every step. Budget about
30 minutes. It is not a sales pitch: every command below is real, and the whole sequence is
re-run end to end, from a fresh clone, by `scripts/clean-clone-smoke.sh` (see "Continuously
verified" at the bottom).

For what builder-II is and why it's built this way, read the sections above this one in
`README.md` first. For a **new-builder map** (governance mental model, setup order, and how to
use the STRATUM TUI across the whole platform), see [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md).
For the full reference index, see [`docs/README.md`](docs/README.md).

## Trust boundary — read this first

Treat builder-II as a tool for **trusted local repositories only**. Some verification profiles
(not the ones used in this walkthrough) run a target repository's own test suite — which means
executing that repository's `conftest.py`, plugins, and test modules on your host, with your
user privileges. That is not a sandbox and is never described as one anywhere in this codebase.
This walkthrough only ever runs builder-II's own fixed, non-target-code commands (the
`platform_status` profile), never an untrusted repo's code.

## 0. Prerequisites

- `git` and [`uv`](https://docs.astral.sh/uv/)
- macOS on Apple Silicon if you want the local MLX model lane later — nothing in this walkthrough
  calls a model, so it isn't required here
- `brew install block-goose-cli` is only needed if you plan to use the Goose adapter later — also
  not required here

## 1. Clone and install

```bash
git clone <this repository> builder-II
cd builder-II
uv sync                 # on Apple Silicon, use: uv sync --extra mlx
cp .env.example .env
```

## 2. Confirm the target

`.env.example` defaults to the self-contained `builder` profile with the target repo set to this
clone itself (`BUILDER_TARGET_REPO=.`), so the rest of this walkthrough has no external
dependency and needs no edits. When you later point builder-II at a real project of yours, change
that pair — the commented `core` example in `.env.example` shows the shape:

```bash
BUILDER_TARGET_REPO=.            # this clone; later: path to a real target repo
BUILDER_TARGET_PROFILE=builder   # later: core (or generic) to match that target
BUILDER_ARTIFACT_ROOT=.builder/artifacts
BUILDER_RUNTIME_MODE=passive
```

## 3. Sanity-check the install

```bash
builder doctor
builder models
builder-targets validate
builder-targets list
builder-agent validate
builder-agent profiles
builder-tools check --tier tier1
```

`builder-tools check` is informational only. `scripts/install-tools.sh required` performs real
Homebrew installs against your machine and is a separate, opt-in step — not part of this
walkthrough.

## 4. Look at the platform's own truth state

builder-II's central discipline is that every claim about itself is backed by a machine-checked
artifact, not prose. Before doing anything else, ask it what's actually true:

```bash
uv run builder-release --help  # current v1 release-proof command surface; use its exact-candidate bundle flow
builder-platform matrix                      # every capability, state-labeled: OPERATIONALLY_VERIFIED or not
builder-platform status
builder-platform audit-docs                  # scans README + docs/ for claims the matrix doesn't back
```

## 5. Capability-scoped config/onboarding artifacts

The commands below are planning and validation surfaces; they do not themselves
write Goose config, execute rollback, start a runtime, or call a model. Other setup
surfaces, including the interactive wizard and digest-approved apply/rollback lanes,
have their own capability-scoped states. Use `builder-platform matrix` and
`docs/COMMAND_AUTHORITY.md` for the exact current state of each command.

```bash
builder-config schema
builder-config resolve
builder-config validate

builder-setup plan --output .builder/setup/plan.json
builder-setup validate-plan .builder/setup/plan.json
builder-setup overlay-plan .builder/setup/plan.json --output .builder/setup/overlay.json
builder-setup validate-overlay-plan .builder/setup/overlay.json
builder-setup rollback-snapshot .builder/setup/overlay.json --output .builder/setup/rollback-snapshot.json
builder-setup validate-rollback-snapshot .builder/setup/rollback-snapshot.json
builder-setup init --output-dir .builder/setup-artifacts
builder-setup validate-onboarding-intent .builder/setup-artifacts/onboarding-intent.json

builder-platform r1-closure --output-dir .builder/r1-closure
builder-platform validate-r1-closure .builder/r1-closure/r1-closure-report.json
```

Wiring your own Goose config and skills remains an operator-managed setup step — see
[`docs/CONFIG_ONBOARDING.md`](docs/CONFIG_ONBOARDING.md).

## 6. Prepare a verification plan and a session package

```bash
builder-verify plan --target-profile builder --verification-profile builder_full \
  --output .builder/verification/verification-execution-plan.json
builder-verify validate-plan .builder/verification/verification-execution-plan.json
builder-verify approve-plan .builder/verification/verification-execution-plan.json \
  --profile platform_status --approval-actor "<your name>" \
  --approval-reason "first session walkthrough" \
  --output .builder/verification/verification-execution-approval.json
builder-verify validate-approval .builder/verification/verification-execution-approval.json \
  --plan .builder/verification/verification-execution-plan.json

builder-session prepare-package builder \
  --task "audit the selected target repo and identify the safest next patch" \
  --output-dir .builder/session/
builder-session validate-prepare-package .builder/session/
builder-session summarize-prepare-package .builder/session/
```

`--profile platform_status` approves builder-II's own fixed, non-target-code-executing commands
only — no execution-risk acknowledgment is required for it. Its receipt is what step 7 reuses.

## 7. Run one real governed patch loop

This is the part worth doing by hand once. Do it against a throwaway scratch repository, never
against this checkout or anything you care about:

```bash
git init -q /tmp/builder-ii-scratch
git -C /tmp/builder-ii-scratch checkout -q -b main
printf '# scratch\n' > /tmp/builder-ii-scratch/README.md
git -C /tmp/builder-ii-scratch add README.md
git -C /tmp/builder-ii-scratch commit -q -m "initial commit"

printf '# scratch\n\nfirst governed patch.\n' > /tmp/builder-ii-scratch/README.md
git -C /tmp/builder-ii-scratch diff > /tmp/diff.patch
git -C /tmp/builder-ii-scratch checkout -q -- README.md
```

`propose-patch` targets whatever directory you're standing in by default, so `cd` into the
scratch repo before running it. `--project` tells `uv` where builder-II's own environment lives;
it does not change what gets patched.

```bash
cd /tmp/builder-ii-scratch

git rev-parse HEAD  # copy this exact value as <scratch-head-sha>

uv run --project /path/to/your/builder-II/clone builder-verify plan \
  --target-profile generic --verification-profile platform_status \
  --target-repo . --artifact-root .builder/verification \
  --output .builder/verification/verification-execution-plan.json

uv run --project /path/to/your/builder-II/clone builder-verify approve-plan \
  .builder/verification/verification-execution-plan.json \
  --approval-actor "<your name>" --approval-reason "verify exact scratch target" \
  --profile platform_status \
  --output .builder/verification/verification-execution-approval.json

uv run --project /path/to/your/builder-II/clone builder-verify run-approved \
  --plan .builder/verification/verification-execution-plan.json \
  --approval .builder/verification/verification-execution-approval.json \
  --output .builder/verification/verification-execution-receipt.json \
  --profile platform_status

uv run --project /path/to/your/builder-II/clone builder-hitl propose-patch \
  --diff-file /tmp/diff.patch --output /tmp/proposal.json \
  --description "append a line to scratch README" --reason "first session walkthrough" \
  --target-head-sha <scratch-head-sha> --target-repo . \
  --verification-receipt .builder/verification/verification-execution-receipt.json
```

```bash
uv run --project /path/to/your/builder-II/clone builder-hitl approve-patch \
  --proposal /tmp/proposal.json --output /tmp/approval.json --approved-by "<your name>"
```

`approve-patch` prints the diff and the full patch digest, then prompts `digest prefix:`. Type
the first 4 characters of the digest it just showed you. There is no `--yes` flag by design —
typing the prefix, at the moment of decision, is the approval.

```bash
uv run --project /path/to/your/builder-II/clone builder-hitl apply-patch \
  --proposal /tmp/proposal.json --approval /tmp/approval.json \
  --verification-receipt .builder/verification/verification-execution-receipt.json --output-dir /tmp/apply-out
```

`apply-patch` accepts only a valid, `EXECUTED`, bounded-approved verification
receipt whose approved steps and process results succeeded. It reconstructs and
validates the verification plan/approval/receipt chain, requires clean exact
pre/post Git state, binds the receipt file digest into proposal schema v2, checks
the receipt `target_repo` against the proposal target, and requires the receipt's
target commit to match the target repository's current HEAD. Generate the
verification chain for the scratch target before applying this example patch.

Check `/tmp/builder-ii-scratch/README.md` — the line is there. `/tmp/apply-out/` now holds the
patch-apply receipt, a rollback plan, and a reverse patch.

```bash
uv run --project /path/to/your/builder-II/clone builder-hitl approve-rollback \
  --rollback-plan /tmp/apply-out/rollback_plan.json --output /tmp/rollback-approval.json \
  --approved-by "<your name>"

uv run --project /path/to/your/builder-II/clone builder-hitl rollback \
  --rollback-plan /tmp/apply-out/rollback_plan.json --reverse-patch /tmp/apply-out/rollback.patch \
  --approval /tmp/rollback-approval.json --output-dir /tmp/rollback-out
```

`approve-rollback` is its own TTY gate with its own digest — a rollback is a mutation too, and
gets a separate human decision from the apply. `git -C /tmp/builder-ii-scratch status` should
now report a clean tree: the scratch repo is back to its pre-apply state.

## What you just proved

- A complete propose → approve → verify → apply → rollback cycle, with a receipt at every step
  and a real interactive approval gate — typing a digest prefix, not a `[y/N]` flag — for both
  the apply and the rollback.
- **Artifact is not authority.** Nothing executed because a JSON file happened to exist; every
  mutating step passed through builder-II's own command-authority gate and, for apply and
  rollback, a live human confirmation at the moment of decision.

## What this walkthrough does not do

- It never touches this checkout or a real project of yours — only the scratch repo you created
  in step 7.
- It never runs a target repository's own test suite. `platform_status` only runs builder-II's
  own fixed, non-target-code commands. Approving a code-executing profile (`pytest_full` /
  `builder_full` against a real target) requires an explicit execution-risk acknowledgment and is
  a deliberately separate, heavier decision — see
  [`docs/HITL_EXECUTION_CLI.md`](docs/HITL_EXECUTION_CLI.md) and
  [`docs/VERIFICATION_PROFILES.md`](docs/VERIFICATION_PROFILES.md).
- The config/onboarding artifacts from step 5 are planning and validation only. Run
  `builder-platform matrix` any time to see exactly which capabilities are
  `OPERATIONALLY_VERIFIED` today and which remain foundation-only.
- Goose, deepagents, MCP, and remote model providers are governed adapters with their own,
  independent promotion state — see
  [`docs/CAPABILITY_PROMOTION.md`](docs/CAPABILITY_PROMOTION.md) and
  [`docs/PLATFORM_COMPLETION_AUDIT.md`](docs/PLATFORM_COMPLETION_AUDIT.md) before assuming any of them are live.

## Next

- [`docs/README.md`](docs/README.md) — the reference-tier index of every document, by subsystem
- `docs/OPERATOR_QUICKSTART.md` — the fuller operator golden path, plus the demo-loop entrypoint
  for a recordable walkthrough against a real target repo (`builder-platform demo-loop`)
- [`docs/CAPABILITY_PROMOTION.md`](docs/CAPABILITY_PROMOTION.md) and `builder-platform matrix` —
  read before trusting any capability claim, here or anywhere else
- `scripts/clean-clone-smoke.sh` — run it yourself, or after changing anything this walkthrough
  touches

## Continuously verified

Nothing above is aspirational prose. `scripts/clean-clone-smoke.sh` clones this repository fresh
into a scratch directory, runs steps 1–6 above end to end, then runs one complete governed patch
loop against a throwaway fixture repo — with `swift`/`xcodebuild` shadowed by hard-failing stubs
for the whole run, so a pass also proves there is no Xcode/Swift toolchain dependency anywhere on
this path. It fails the run if the whole sequence exceeds its 30-minute budget.

```bash
bash scripts/clean-clone-smoke.sh
```
