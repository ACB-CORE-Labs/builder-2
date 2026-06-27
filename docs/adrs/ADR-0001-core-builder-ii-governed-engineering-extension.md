# ADR-0001: CORE builder-II as a Governed Engineering Extension

## Status

Accepted

## Context

CORE builder-II is CORE's governed engineering platform for local agent-assisted software development.

It carries CORE's engineering philosophy into the developer-platform layer while remaining architecturally separate from the CORE runtime and CORE Workbench/UI.

The design risk is threefold:

1. builder-II could become weak governance theater: safe-looking artifacts that do not materially improve engineering work.
2. builder-II could become reckless automation: powerful agent execution that hides mutation, shell, verification, promotion, or merge authority.
3. builder-II could collapse into CORE-specific runtime or Workbench concepts instead of remaining a generic-first developer platform.

None of these outcomes is acceptable.

Codename Goose already provides a capable local agent execution platform. builder-II should not compete with Goose. It should supplement and reinforce Goose with target profiles, context packs, model/runtime policy, authority boundaries, evidence artifacts, verification profiles, and handoff continuity.

The governing question is:

```text
How should CORE builder-II become powerful for real engineering design, implementation, verification, and handoff without bypassing human authority or collapsing into CORE runtime identity?
```

## Decision

builder-II shall be designed as CORE's governed engineering control plane for local agent-assisted software development.

It is:

- CORE-born;
- Codename-Goose-reinforcing;
- generic-first;
- engineer-centered;
- governed by the Builder's Signet.

It is not:

- the CORE runtime;
- CORE Workbench/UI;
- a second CORE runtime;
- a replacement for Codename Goose;
- an autonomous execution platform by default;
- a CORE-only development harness.

The product positioning is:

```text
CORE builder-II = governed engineering platform for local agent-assisted development
Codename Goose  = execution-capable local agent platform reinforced by builder-II
deepagents      = optional future orchestration harness
```

builder-II shall make local agent-assisted engineering feel like an extension of the engineer: context-aware, profile-aware, repo-aware, verification-aware, evidence-bearing, resumable, anticipatory, and explicitly bounded by human authority.

## The Builder's Signet

Every architectural decision in builder-II shall be measured against three engineering pillars inherited from CORE.

These are not slogans. They are hard constraints.

### 1. Mechanical Sympathy

builder-II must respect the real substrate of engineering work.

That substrate includes local repositories, Git, branches, diffs, tests, failed checks, human review, PRs, handoffs, constrained hardware, model/runtime boundaries, and existing execution platforms such as Codename Goose.

Mechanical Sympathy requires builder-II to reinforce tools and workflows that already work instead of rebuilding them unnecessarily.

For builder-II, this means:

- Codename Goose remains the primary local execution-capable agent platform.
- Git remains the source of branch, diff, and commit truth.
- Target repositories remain explicit, not ambient.
- Hardware constraints are treated as design inputs.
- Verification commands remain real commands, not vibes.
- The correct engineering path should be easier than the sloppy path.

### 2. Semantic Rigor

builder-II must preserve exact meaning across every artifact, profile, session, command, and claim.

The following distinctions are mandatory:

```text
planned != executed
executed != verified
verified != promoted
schema-valid != engineering-correct
manifest != runtime evidence
handoff != proof of correctness
HITL-required != HITL-approved
verification-planned != verification-passed
```

Semantic Rigor requires builder-II to prevent unverified work from masquerading as verified work.

Every meaningful engineering claim must be backed by explicit evidence, artifact linkage, or an honest status such as `NOT_RUN`, `BLOCKED`, `FAILED`, or `REQUIRES_HITL`.

### 3. The Third Door

builder-II rejects the false choice between weak safety theater and reckless automation.

The unacceptable doors are:

```text
Door 1: safe because useless
Door 2: powerful because ungoverned
```

The Third Door is governed power:

```text
powerful because governed
ambient but not deceptive
automated where appropriate
HITL-gated where authority changes
useful without pretending
```

builder-II should make engineering work feel almost on autopilot for context, preparation, routing, verification planning, and handoff continuity while preserving explicit human authority over mutation, shell execution, runtime activation, verification claims, promotion, merge, and release.

## Scope Boundary

builder-II owns:

- local setup;
- model/runtime policy;
- Codename Goose setup and recipes;
- prompt and lane profiles;
- agent profiles;
- tool registry;
- context packs;
- target repositories;
- target profiles;
- verification profiles;
- git preflight/postflight artifacts;
- session manifests;
- receipt and handoff artifacts;
- optional agent/subagent orchestration boundaries;
- artifact chain verification.

builder-II does not own:

- CORE runtime identity;
- CORE Workbench/UI behavior;
- Codename Goose runtime identity;
- deepagents runtime identity;
- autonomous execution authority by default;
- verification claims without evidence.

## Codename Goose Relationship

Codename Goose is the primary local execution-capable agent platform.

builder-II shall make Goose sessions better by providing:

- resolved target profile;
- resolved agent profile;
- context pack;
- authority mode;
- model/runtime policy;
- verification expectations;
- forbidden actions;
- artifact output expectations;
- handoff requirements;
- evidence boundaries.

A governed Goose session shall make clear:

```text
what Goose is being asked to do
what Goose is allowed to do
what Goose is forbidden to do
what context Goose receives
what artifacts should be produced
what evidence is required
what remains planned-only
what requires human approval
```

builder-II must not falsely imply that Goose ran, changed files, executed commands, passed tests, or completed verification unless corresponding evidence exists.

## Target Profiles

builder-II remains generic-first even though it is CORE-born.

Initial target profiles are:

```text
generic
builder
core
```

The `generic` profile must be useful for ordinary software repositories.

The `builder` profile is for builder-II self-development.

The `core` profile may include CORE-specific principles, axioms, verification expectations, and repository conventions, but these must not leak into builder-II globally.

CORE-specific behavior must be implemented as target-profile behavior, not as the platform identity.

## Agent Profiles

Base agent profiles remain generic:

```text
repo_mapper
context_planner
code_reviewer
patch_planner
verification_planner
handoff_scribe
```

CORE-specific profiles may extend them later:

```text
core.invariant_auditor
core.patch_planner
core.verification_planner
```

The base platform must stay useful without CORE-specific assumptions.

## deepagents Relationship

deepagents is optional.

builder-II may later integrate deepagents for planning, subagent routing, HITL workflows, memory routes, LangGraph patterns, backend abstractions, or MCP wiring.

deepagents must not bypass builder-II governance.

Before any deepagents capability is promoted from disabled to enabled, it must have:

- docs;
- tests;
- command surface;
- failure mode;
- human approval boundary;
- output artifact;
- rollback path;
- verification path.

Initial deepagents work should remain generic-first and limited to:

- bridge specs;
- profile rendering;
- dry-run output;
- read-only planning;
- dependency smoke checks.

## Authority Model

builder-II capabilities begin disabled or planned-only unless explicitly promoted.

No capability may silently grant:

- autonomous file writes;
- shell execution;
- live Goose activation;
- live deepagents activation;
- hidden model calls;
- git mutation;
- PR creation;
- merge authority;
- verification-passed claims;
- HITL approval;
- release promotion.

Authority must be explicit, profile-aware, evidence-bearing, and test-covered.

## Scenario Testing Requirement

Unit tests prove that individual records and modules are valid.

Scenario tests must prove that governed engineering workflows behave.

builder-II shall include scenario tests that exercise complete engineering flows across module boundaries.

A minimal governed engineering scenario should prove that a target repo can move through:

```text
target/profile resolution
-> context/session preparation
-> governed Goose session manifest
-> planned verification profile report
-> receipt or handoff artifact
-> artifact chain verification
```

without granting false execution authority, false shell authority, false verification claims, or false HITL approval.

Scenario tests should cover:

- happy-path generic engineering sessions;
- broken digest rejection;
- missing HITL approval;
- planned verification that cannot claim passed;
- partial chains reported as incomplete rather than schema-invalid;
- target-profile isolation across `generic`, `builder`, and `core`.

The goal is to prevent seam blindness: local correctness without end-to-end workflow coherence.

## Acceptance Criteria

This ADR is satisfied when builder-II consistently demonstrates the following properties.

### Engineering Usefulness

builder-II improves real development workflows by producing useful context, plans, verification expectations, and handoffs.

### Goose Reinforcement

builder-II supplements Codename Goose rather than replacing it.

### Product Lineage

builder-II clearly presents itself as CORE's developer-platform product while remaining separate from CORE runtime and CORE Workbench/UI.

### Profile Discipline

Generic behavior remains generic. CORE behavior is isolated to the CORE target profile.

### Explicit Authority

Mutation, shell execution, runtime activation, promotion, merge, and completion claims require explicit authority and evidence.

### Evidence Discipline

Planned, attempted, executed, verified, failed, blocked, and promoted states remain distinct.

### Session Continuity

Work can be resumed by another human, model, or agent without losing governing context.

### Scenario Coverage

Scenario tests prove governed engineering flows across artifact boundaries, not merely schema validity.

## Consequences

This decision prioritizes engineering usefulness over platform expansion.

builder-II should invest first in:

- context pack quality;
- profile rendering;
- Goose manifest quality;
- repo state awareness;
- verification planning;
- handoff quality;
- artifact linkage;
- HITL boundary enforcement;
- scenario-level workflow coverage.

builder-II should not prioritize:

- becoming a replacement agent runtime;
- autonomous writes by default;
- shell execution by default;
- CORE runtime identity;
- CORE Workbench/UI behavior;
- deepagents hard dependency;
- governance artifacts that do not improve engineering execution.

The system should become powerful, but only in ways that preserve responsibility, evidence, and human authority.

## Summary

CORE builder-II is the developer-platform expression of CORE's engineering philosophy: mechanically sympathetic to real development work, semantically rigorous about every claim and artifact, and committed to the Third Door of governed power.

It exists to make governed engineering feel ambient: the right context, profile, verification path, and handoff structure should come to the engineer before the engineer has to reconstruct them manually.

It is an extension of the engineer's workshop: disciplined, powerful, context-rich, evidence-bearing, and honest about what has and has not been done.
