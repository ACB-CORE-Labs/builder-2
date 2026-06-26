# builder-II full mastery implementation plan

This document defines the complete builder-II platform plan from the current governed foundation through the full Goose-centered, deepagents-augmented local developer runtime.

## Architecture identity

```text
builder-II = governed platform/control plane
Goose      = primary local runtime/operator
deepagents = optional subagent/planning/delegation harness
target repo = generic / builder-II / CORE / research repo / future targets
```

builder-II is not CORE, not CORE Workbench/UI, and not a second CORE runtime. CORE remains a target profile only. deepagents remains optional and must not bypass builder-II governance. Goose is the primary runtime that builder-II prepares, constrains, verifies, and audits.

## Current baseline

Completed foundation through PR #33:

```text
DONE  target profiles
DONE  agent profiles
DONE  deepagents bridge specs
DONE  optional deepagents smoke/readiness
DONE  readiness artifacts
DONE  dry-run bridge spec artifacts
DONE  artifact validation
DONE  capability promotion registry
DONE  target bundle artifacts
DONE  verification profile registry
DONE  handoff artifacts
DONE  quality gate artifacts
DONE  research planning artifacts
DONE  Goose runtime design spec
DONE  runtime promotion contract
```

The artifact foundation is complete. The current work is Goose session manifests, still with no runtime activation.

## North Star operating loop

```bash
builder setup
builder doctor
builder-targets validate
builder-agent validate
builder-verification validate
builder-context pack --target builder --changed --task "..."
builder-bundle create --target builder --agent patch_planner --task "..." --output .builder/artifacts/target-bundle.json
builder-bundle validate .builder/artifacts/target-bundle.json
builder-research plan --target generic --profile research_planner --task "..." --output .builder/artifacts/research-plan.json
builder-research validate .builder/artifacts/research-plan.json
builder-notes handoff --target builder --agent handoff_scribe --task "..." --summary "..." --output .builder/artifacts/handoff.json
builder-notes validate .builder/artifacts/handoff.json
builder-quality plan --target builder --profile builder_full --task "..." --output .builder/artifacts/quality-gate.json
builder-quality validate .builder/artifacts/quality-gate.json
builder-goose manifest --target builder --mode read_only --bundle .builder/artifacts/target-bundle.json --output .builder/artifacts/goose-session.json
builder-goose validate .builder/artifacts/goose-session.json
builder-goose start-readonly --target builder --bundle .builder/artifacts/target-bundle.json
builder-deepagents render --target builder --agent patch_planner --mode readonly --output .builder/artifacts/deepagents-runtime-spec.json
builder-deepagents validate .builder/artifacts/deepagents-runtime-spec.json
builder-approval propose-command --target builder --command "uv run pytest"
builder-approval approve .builder/artifacts/command-proposal.json
builder-run approved .builder/artifacts/command-proposal.json
builder-approval propose-patch --target builder --task "..."
builder-approval approve .builder/artifacts/patch-proposal.json
builder-apply approved .builder/artifacts/patch-proposal.json
builder-postflight --target builder
builder-notes handoff --target builder --summary "..."
```

## Phase 1: artifact foundation

Status: complete through PR #32.

builder-II can package pre-runtime work into validated artifacts:

- target bundles
- verification profiles
- handoff artifacts
- quality gates
- research plans

These artifacts remain evidence and review objects. They are not runtime authority.

## Phase 2: Goose runtime design layer

Status: complete through PR #33.

Goose is formally defined as the primary local runtime/operator under builder-II governance. Runtime modes and promotion requirements are specified, but no runtime is enabled by design docs.

Runtime modes:

```text
disabled
read_only
command_proposal
verification_execution
patch_proposal
hitl_write
```

No code execution is enabled by the design docs alone.

## Phase 3: read-only runtime candidate

Add `builder-goose manifest`, `builder-goose validate`, and later `builder-goose start-readonly`.

The manifest step is artifact-only. It may describe a requested future mode, link target/verification/quality/handoff/context artifacts, and name an expected audit artifact. It must not start Goose.

Read-only mode may later inspect files, git status, repo tree, and docs, and may produce plans and handoffs. It must not edit files, write source, execute arbitrary shell, commit, push, mutate memory, or open PRs.

Every runtime session must emit a runtime audit artifact recording mode, target, task, files read, requested actions, denied actions, approval events, and handoff summary.

## Phase 4: deepagents subagent integration

Goal: deepagents becomes an optional subagent/planning harness under builder-II governance.

Add `builder-deepagents render` and `builder-deepagents validate` for read-only runtime specs.

Subagents may include repo mapping, context planning, code review, patch planning, verification planning, handoff writing, research planning, source mapping, evidence synthesis, and report review.

deepagents must not directly mutate files, bypass Goose, bypass builder-II approvals, or become a hard dependency.

## Phase 5: HITL command proposal runtime

Add command proposal, validation, approval, and approved execution artifacts.

Allowed command classes begin with verification/status/read-only commands. Forbidden defaults include destructive filesystem commands, unbounded shell, secret access, `git push`, and reset operations.

## Phase 6: HITL patch proposal runtime

Add patch proposal, validation, approval, and approved apply artifacts.

Patch lifecycle: plan, explicit diff proposal, human review, apply, verify, postflight, handoff.

No direct autonomous commit or push.

## Phase 7: full Goose + deepagents development loop

Flow:

```text
builder-II chooses target/profile/context
→ target bundle artifact
→ verification profile artifact
→ Goose session manifest
→ optional deepagents planning/subagents
→ Goose runs approved read-only inspection
→ agent proposes patch
→ human approves
→ Goose applies patch
→ verification gate runs
→ postflight artifact
→ handoff artifact
```

Completion requires demos on builder, generic, and CORE targets without making builder-II CORE-specific.

## Phase 8: research agent / open_deep_research adapter

Use `AssetOverflow/open_deep_research` first as a target repo, reference implementation, and adapter source.

Future research runtime candidates require search proposal artifacts, source collection approval, MCP permission artifacts, cost budget artifacts, report artifacts, citation validation, and clear separation between research output and verified claims.

## Phase 9: quality gates and CI-level confidence

Add prompt/profile regression tests, artifact schema tests, runtime denial tests, approval flow tests, Goose recipe tests, deepagents bridge tests, and target smoke tests.

## Phase 10: production polish / operator mastery

Add one-command setup audit, sample target repos, example artifacts, golden demos, operator playbooks, failure recovery docs, upgrade docs, and release checklist.

## Final 100% definition

builder-II is fully complete when all of this is true:

```text
Generic-first platform works across targets.
CORE is only a target profile.
CORE Workbench/UI is not conflated with builder-II.
Goose is the primary runtime.
deepagents is optional and governed.
Every capability has docs/tests/CLI/failure modes/HITL/output artifact/rollback/verification.
Read-only runtime works.
HITL command execution works.
HITL patch application works.
Research agent planning works.
open_deep_research can be used as target/reference/adapter source.
Quality gates are enforced.
Handoffs are captured.
Runtime sessions are auditable.
No hidden agent authority exists.
No autonomous writes happen by default.
No shell execution happens without explicit approval.
No commit/push happens without explicit approval.
Deephaven remains untouched.
```

## Updated PR roadmap

```text
#29 verification profile registry          MERGED
#30 handoff artifacts                      MERGED
#31 quality gate artifacts                 MERGED
#32 research planning profiles/artifacts   MERGED
#33 Goose runtime ADR/spec                 MERGED
#34 Goose session manifest                 CURRENT
#35 Goose read-only runtime candidate
#36 deepagents readonly runtime spec
#37 deepagents planning harness
#38 HITL command proposal/approval flow
#39 approved verification command runner
#40 HITL patch proposal flow
#41 approved patch application flow
#42 runtime audit artifacts
#43 end-to-end builder target demo
#44 generic target demo
#45 CORE target profile demo
#46 research target/open_deep_research demo
#47 production docs/playbooks/release checklist
```

The masterpiece is Goose-centered, builder-II-governed, deepagents-augmented, target-profile-driven, artifact-audited, and HITL-safe.
