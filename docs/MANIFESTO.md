# CORE builder-II Manifesto

CORE builder-II is CORE's governed engineering platform for local agent-assisted software development.

It is CORE-born, Codename-Goose-reinforcing, generic-first, engineer-centered, and governed by the Builder's Signet.

Its purpose is not to produce governance ceremony. Its purpose is to make engineering design, implementation, verification, and handoff more reliable, more repeatable, more context-aware, and more worthy of trust.

A system that cannot help build correct software is not useful. A system that builds software by hiding authority is not trustworthy. builder-II exists for the Third Door: governed power.

## Product Positioning

CORE builder-II is a CORE product and brand extension.

It carries CORE's engineering philosophy into the developer-platform layer while remaining generic enough to improve many software repositories, not only CORE-targeted work.

The positioning is simple:

```text
CORE builder-II  = governed engineering platform for local agent-assisted development
Codename Goose   = execution-capable local agent platform reinforced by builder-II
deepagents       = optional future orchestration harness
```

The brand supplies the philosophy. The architecture preserves generality.

## The Promise

builder-II should feel like an extension of the engineer.

The operator should experience the platform as if the work already knows where it is supposed to go:

```text
The current repo state is visible.
The target profile is resolved.
The relevant context is assembled.
The agent role is clear.
The authority boundary is explicit.
The verification path is ready.
The risks are surfaced.
The next responsible engineering move is obvious.
The handoff can be resumed without context fog.
```

This should feel almost ambient, but never deceptive.

Autopilot is appropriate for context, preparation, routing, reminders, verification planning, and handoff continuity.

Autonomous authority is not implied.

## The Builder's Signet

Every architectural decision in builder-II is measured against three engineering pillars inherited from CORE.

These are not slogans. They are hard constraints.

### I. Mechanical Sympathy

builder-II must respect the real substrate of engineering work.

That substrate includes local repositories, Git branches, diffs, tests, failed checks, human review, PRs, handoffs, constrained hardware, model/runtime boundaries, and the existing tools that engineers already depend on.

Codename Goose already provides a capable local execution platform. builder-II should not rebuild Goose. It should reinforce Goose by preparing better context, stricter profiles, clearer authority, stronger evidence, and better handoffs.

Mechanical Sympathy means builder-II makes the correct engineering path natural:

- use tools that already work;
- preserve local repo reality;
- respect hardware limits;
- do not hide Git state;
- do not invent fake verification;
- do not abstract away the operator's actual workflow;
- make the fast path safe;
- make the safe path efficient;
- make the correct path easier than the sloppy path.

### II. Semantic Rigor

builder-II must preserve exact meaning across every artifact, profile, session, command, and claim.

A plan is not execution.
Execution is not verification.
Verification is not promotion.
A valid schema is not proof of correct work.
A Goose session manifest is not evidence that Goose ran.
A handoff is not proof that the implementation is correct.
A required HITL gate is not an approved HITL gate.
A planned verification command is not a passed verification command.

Semantic Rigor means builder-II refuses to let ambiguous, incomplete, or unverified work masquerade as completed engineering truth.

Every meaningful engineering claim must be backed by explicit evidence, artifact linkage, or an honest status such as `NOT_RUN`, `BLOCKED`, `FAILED`, or `REQUIRES_HITL`.

### III. The Third Door

builder-II rejects the false choice between weak safety theater and reckless automation.

The obvious bad options are:

```text
Door 1: safe because useless
Door 2: powerful because ungoverned
```

The Third Door is:

```text
powerful because governed
ambient but not deceptive
automated where appropriate
HITL-gated where authority changes
useful without pretending
```

builder-II should make local agent-assisted engineering feel almost on autopilot while preserving explicit human authority over mutation, shell execution, runtime activation, verification claims, promotion, merge, and release.

## Codename Goose Relationship

Codename Goose is the primary local execution-capable agent platform.

builder-II is the governed engineering control plane and convention layer around local agent work.

A governed Goose session should make clear:

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

builder-II should improve Goose through:

- target/profile discipline;
- high-signal context packs;
- model/runtime policy;
- authority modes;
- verification expectations;
- forbidden-action boundaries;
- artifact output contracts;
- evidence capture;
- handoff continuity.

Goose is the muscle. builder-II is the governed engineering convention layer that keeps the work coherent, honest, and resumable.

## Generic-First Architecture

builder-II is a CORE product, but it must not be CORE-locked.

The first target profiles are:

```text
generic
builder
core
```

The `generic` profile must remain useful for ordinary software repositories.

The `builder` profile is for builder-II self-development.

The `core` profile is for AssetOverflow/core and may include CORE-specific principles, axioms, and verification conventions.

CORE-specific behavior must stay target-profile-scoped. It must not leak into builder-II globally.

## Authority Doctrine

builder-II must never silently grant:

- autonomous source writes;
- shell execution;
- live Goose activation;
- live deepagents activation;
- model calls outside declared policy;
- memory mutation;
- git mutation;
- PR creation;
- merge authority;
- verification-passed claims;
- HITL approval;
- release promotion.

Authority must be explicit, profile-aware, evidence-bearing, and test-covered.

## Engineering Value Before Governance Ceremony

Governance is not the product. Correct software is the product.

Every builder-II artifact, profile, command, scenario, and record must serve real engineering work:

- understanding a repository;
- selecting the right seam;
- planning a patch;
- preserving context;
- reducing bad changes;
- surfacing failure modes;
- preparing verification;
- recording evidence;
- enabling reliable handoff.

A governance artifact that does not improve engineering execution is ceremony and should be questioned.

builder-II must never become a beautiful artifact registry around a hollow engineering center.

## The Product Standard

builder-II succeeds when a serious engineer can say:

```text
The work is organized around me.
The right context is already loaded.
The next engineering move is obvious.
The risks are visible.
The verification path is ready.
The system remembers where we left off.
I can approve, steer, reject, or resume with confidence.
```

That is the standard.

Not noise. Not theater. Not reckless autonomy.

A governed extension of the engineer.

## Summary

CORE builder-II is the developer-platform expression of CORE's engineering philosophy: mechanically sympathetic to real development work, semantically rigorous about every claim and artifact, and committed to the Third Door of governed power.
