# builder-II full mastery implementation plan

This document defines the complete builder-II platform plan from the governed no-runtime foundation through the full Goose-centered, deepagents-augmented local developer runtime.

## Architecture identity

```text
builder-II = governed platform/control plane
Goose      = preferred local runtime/operator after explicit promotion
deepagents = optional subagent/planning/delegation harness
target repo = generic / builder-II / CORE / research repo / future targets
```

builder-II is not CORE, not CORE Workbench/UI, and not a second CORE runtime. CORE remains a target profile only. deepagents remains optional and must not bypass builder-II governance. Goose is the preferred local runtime/operator that builder-II prepares, constrains, verifies, and audits when a runtime mode is explicitly promoted.

Builder-II governance is the sovereign boundary. Goose and deepagents are subordinate execution/planning mechanisms, not authorities.

## Current baseline

Completed foundation through the read-only audit candidate:

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
DONE  Goose session manifest artifacts
DONE  Goose read-only candidate audit artifacts
```

The artifact foundation is complete. Goose session manifests are a governed artifact-only surface. The read-only candidate now stabilizes the manifest-to-audit path while still denying actual Goose runtime start, repository file reads, git status inspection, linked artifact reads, autonomous writes, shell execution, source mutation, model execution, and runtime authority by default.

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
builder-goose readonly-audit .builder/artifacts/goose-session.json --output .builder/artifacts/goose-runtime-audit.json
builder-goose validate-audit .builder/artifacts/goose-runtime-audit.json
builder-goose start-readonly --manifest .builder/artifacts/goose-session.json
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

The current implemented subset stops before `builder-goose start-readonly`. Commands after that point are future candidates and require explicit promotion.

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

Status: complete through PR #34.

Goose is formally defined as the preferred local runtime/operator under builder-II governance. Runtime modes and promotion requirements are specified, but no runtime is enabled by design docs or manifests.

Implemented artifact-only surfaces:

- `docs/GOOSE_RUNTIME.md`
- `docs/RUNTIME_PROMOTION.md`
- `docs/GOOSE_SESSION.md`
- `builder-goose manifest`
- `builder-goose validate`

Runtime modes:

```text
disabled
read_only
command_proposal
verification_execution
patch_proposal
hitl_write
```

No code execution is enabled by the design docs or manifests alone.

## Phase 3: read-only runtime candidate

Status: candidate audit artifact surface implemented; actual repository inspection remains unpromoted.

Implemented candidate surfaces:

- `docs/GOOSE_READONLY.md`
- `builder_ii/goose_readonly.py`
- `builder-goose readonly-audit`
- `builder-goose validate-audit`
- read-only candidate audit artifact tests

The read-only candidate consumes a valid Goose session manifest with `requested_runtime_mode: read_only` and emits a runtime audit artifact. This first candidate does not yet inspect files, git status, repo tree, docs, or linked target artifacts.

It must not:

- start Goose
- read repository files as runtime behavior
- inspect git status as runtime behavior
- read linked target artifacts as runtime behavior
- edit files
- write source
- execute arbitrary shell
- run tests unless a later approved verification mode permits it
- commit or push
- mutate memory
- open pull requests
- call models
- construct deepagents
- collect sources, run web search, or run MCP tools
- bypass target profiles, verification profiles, quality gates, approvals, or audit artifacts

Required before actual read-only inspection is promoted:

- target-boundary rules or file-read allowlist
- repository file read recording
- git status recording
- linked target artifact read recording
- denied-action tests
- no-write tests
- no-shell tests
- no-command tests
- no-model-call tests
- interruption recovery path
- postflight/handoff behavior

## Phase 4: model routing policy phase

Goal: model routing becomes a governed policy/artifact surface before any automatic routing behavior exists.

A future model routing artifact should bind:

- task class
- target profile
- allowed model lanes
- forbidden model lanes
- local-first preference
- privacy and cost boundary
- frontier escalation rule
- approval requirement for nonlocal calls
- expected evidence from each model lane
- fallback behavior
- audit requirements

Denied by default:

- hidden model calls
- silent cost-bearing execution
- automatic frontier escalation
- treating model output as authority without verification

## Phase 5: deepagents subagent integration

Goal: deepagents becomes an optional planning/subagent harness under builder-II governance.

Add `builder-deepagents render` and `builder-deepagents validate` for read-only planning specs.

Subagents may include repo mapping, context planning, code review, patch planning, verification planning, handoff writing, research planning, source mapping, evidence synthesis, and report review.

deepagents must not directly mutate files, bypass builder-II governance, bypass approvals, bypass audit artifacts, or become a hard dependency. If used within a Goose-governed runtime mode, it also must not bypass that runtime boundary.

## Phase 6: HITL command proposal runtime

Add command proposal, validation, approval, and approved execution artifacts.

Allowed command classes begin with verification/status/read-only commands. Forbidden defaults include destructive filesystem commands, unbounded shell, secret access, `git push`, and reset operations.

Every approved command execution must bind to:

- exact command text
- target profile
- verification profile
- approval artifact
- timeout/failure behavior
- audit output
- rollback or no-mutation statement

## Phase 7: HITL patch proposal runtime

Add patch proposal, validation, approval, and approved apply artifacts.

Patch lifecycle:

```text
plan
→ explicit diff proposal
→ human review
→ approved apply
→ verification
→ postflight
→ handoff
```

No direct autonomous commit or push.

## Phase 8: full Goose + deepagents development loop

Flow:

```text
builder-II chooses target/profile/context
→ target bundle artifact
→ verification profile artifact
→ Goose session manifest
→ read-only audit artifact
→ optional deepagents planning/subagents
→ Goose performs approved read-only inspection
→ agent proposes command or patch artifacts
→ human approves
→ Goose executes approved action
→ verification gate runs
→ postflight artifact
→ handoff artifact
```

Completion requires demos on builder, generic, and CORE targets without making builder-II CORE-specific.

## Phase 9: research agent / open_deep_research adapter

Use `AssetOverflow/open_deep_research` first as a target repo, reference implementation, and adapter source.

Future research runtime candidates require search proposal artifacts, source collection approval, MCP permission artifacts, cost budget artifacts, report artifacts, citation validation, and clear separation between research output and verified claims.

Research plans remain artifact-only until separately promoted.

## Phase 10: performance and efficiency track

See `docs/plan/PERFORMANCE_AND_EFFICIENCY_AMENDMENT.md`.

Performance is first-class but cannot outrank governance.

Candidate surfaces:

- Rust-backed artifact validation and processing, gated by measurement and parity evidence.
- MLX + UMA context compression, restricted to provenance-preserving review artifacts.
- Hybrid local/frontier model routing, introduced first as policy artifacts.

Denied by default:

- hidden model calls
- hidden shell execution
- source mutation
- durable memory mutation
- replacing source truth with lossy summaries
- making performance work a runtime authority bypass

## Phase 11: quality gates and CI-level confidence

Add prompt/profile regression tests, artifact schema tests, runtime denial tests, approval flow tests, Goose recipe tests, deepagents bridge tests, target smoke tests, and cross-layer compatibility tests.

## Phase 12: production polish / operator mastery

Add one-command setup audit, sample target repos, example artifacts, golden demos, operator playbooks, failure recovery docs, upgrade docs, and release checklist.

## Final 100% definition

builder-II is fully complete when all of this is true:

```text
Generic-first platform works across targets.
CORE is only a target profile.
CORE Workbench/UI is not conflated with builder-II.
Builder-II governance remains sovereign.
Goose is the preferred local runtime/operator after promotion.
deepagents is optional and governed.
Every capability has docs/tests/CLI/failure modes/HITL/output artifact/rollback/verification.
Read-only runtime works.
HITL command execution works.
HITL patch application works.
Research agent planning works.
open_deep_research can be used as target/reference/adapter source.
Model routing is policy-bound and auditable.
Rust/MLX performance work is measured and promotion-gated.
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
#34 Goose session manifest                 MERGED
#35 docs reconciliation                    MERGED
#36 Goose read-only candidate audit        CURRENT
#37 actual read-only inspection boundary
#38 deepagents readonly planning spec
#39 model routing policy artifacts
#40 HITL command proposal/approval flow
#41 approved verification command runner
#42 HITL patch proposal flow
#43 approved patch application flow
#44 end-to-end builder target demo
#45 generic target demo
#46 CORE target profile demo
#47 research target/open_deep_research demo
#48 performance candidate benchmarks
#49 production docs/playbooks/release checklist
```

The masterpiece is builder-II-governed, Goose-centered, deepagents-augmented only when useful, target-profile-driven, artifact-audited, model-policy-aware, performance-conscious, and HITL-safe.
