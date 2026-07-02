# ADR-0002: Builder Convention Layer over Codename Goose

## Status

Accepted. Identity language refined by ADR-0003.

## Context

builder-II is intended to make local agent-assisted engineering feel coherent, governed, and natural for the operator.

Codename Goose already provides the primary local execution-capable agent platform. It can be configured through provider/model settings, recipes, environment variables, session options, built-ins, extensions, and local context. builder-II should not rebuild this runtime layer or become a competing agent runtime.

At the same time, directly operating raw Goose surfaces can force the engineer to manually remember target profiles, model aliases, provider details, recipe choices, authority mode, verification requirements, context files, handoff conventions, and artifact obligations.

The risk is a false choice:

1. too much decoupling, where builder-II creates pristine artifacts that Goose does not naturally consume;
2. too much runtime coupling, where builder-II silently becomes an ungoverned launcher for Goose execution;
3. too little product convention, where users must manually translate between builder-II artifacts and Goose sessions.

The platform needs a Third Door: a stable builder convention layer that compiles into Goose-native surfaces while preserving builder-II governance.

## Decision

builder-II shall expose a stable builder convention layer over Codename Goose.

Builder commands, configuration files, profiles, and artifacts may wrap Goose-native capabilities, but they must compile down to Goose-compatible environment, recipe, context, and session surfaces while preserving explicit authority and evidence boundaries.

The governing rule is:

```text
Use Codename Goose natively underneath.
Expose builder conventions above.
Preserve governance and evidence around the seam.
```

## Convention Layer Responsibilities

The builder convention layer shall provide a consistent operator-facing vocabulary for:

- target repository selection;
- target profile resolution;
- provider and model policy;
- model alias and model tier selection;
- agent profile selection;
- future subagent orchestration planning;
- authority mode;
- context pack selection;
- Codename Goose recipe selection or rendering;
- Codename Goose environment projection;
- verification profile selection;
- evidence and handoff expectations.

The operator should not need to manually reconstruct these relationships for every session.

## Goose-Native Projection

Every builder-II abstraction that claims to prepare a Goose session must eventually project to Goose-native surfaces.

These surfaces include, where applicable:

- `GOOSE_PROVIDER`;
- provider host variables such as `OPENAI_HOST` or `OLLAMA_HOST`;
- `GOOSE_MODEL`;
- `GOOSE_TEMPERATURE`;
- planner provider/model settings;
- recipe path or recipe selection;
- session name;
- resume behavior;
- context or MOIM message file;
- allowed built-ins/extensions;
- working directory;
- task prompt or session instruction;
- artifact output expectations.

A builder-II artifact may describe this projection before runtime launch, but the artifact is not proof that Goose executed.

## Configuration Resolution Spine

builder-II shall maintain a resolved configuration spine for each governed engineering session.

The spine answers:

```text
Which target repo?
Which target profile?
Which provider?
Which model alias?
Which model tier?
Which Goose recipe?
Which agent profile?
Which subagents, if any?
Which context pack?
Which authority mode?
Which verification profile?
Which tool/MCP surfaces?
Which evidence outputs are required?
```

The spine should be renderable as a reviewable artifact before runtime activation.

The spine should also be projectable into Codename Goose session inputs when, and only when, operator authority permits.

## Environment, Config, Projection, Artifact

builder-II shall keep the following meanings distinct:

```text
.env                 = local machine details and secrets
builder config       = declared engineering policy and defaults
resolved session     = concrete target/provider/model/agent/authority selection
Goose projection     = Goose-native env/recipe/context/session surface
artifact             = reviewable evidence of what was selected, planned, or projected
runtime execution    = actual Goose process/session behavior, requiring explicit authority
```

Semantic Rigor requires these layers not to be collapsed.

## Command Surface Direction

The product may expose stable builder commands that wrap Goose conventions, such as:

```text
builder plan
builder tui
builder review
builder verify-plan
builder handoff
builder goose plan
builder goose session
builder goose resume
```

The exact names remain implementation details, but the principle is fixed: builder commands should provide consistency for the engineer while compiling to Goose-native behavior underneath.

## Authority Boundary

The convention layer must not hide authority.

A builder command may render configuration, prepare context, select a recipe, generate an artifact, or propose a Goose session without granting runtime authority.

A builder command must not silently:

- launch Goose;
- run shell commands;
- mutate source files;
- approve HITL gates;
- claim verification passed;
- commit or push changes;
- promote a capability;
- merge or release work.

Any command that crosses from planning/projection into execution must have an explicit capability state, docs, tests, failure mode, human approval boundary, output artifact, rollback path, and verification path.

## Agent and Subagent Direction

Agent and subagent concepts in builder-II are convention-layer roles before they are runtime actors.

Base agent profiles remain generic:

```text
repo_mapper
context_planner
code_reviewer
patch_planner
verification_planner
handoff_scribe
```

Future subagent orchestration must first appear as a plan artifact that describes:

- role;
- task;
- input context;
- authority;
- dependencies;
- expected output;
- handoff contract;
- verification expectation.

No subagent plan may imply deepagents construction, Goose runtime activation, source mutation, shell execution, or verification success by itself.

## Mechanical Sympathy

The convention layer exists because Codename Goose is useful.

builder-II should reinforce Goose rather than obscure it. Where Goose already has a native capability, builder-II should prefer projection, wrapping, documentation, or policy enforcement over rebuilding that capability.

## Semantic Rigor

The convention layer must preserve exact claims:

```text
resolved config != launched session
Goose projection != Goose execution
recipe selected != recipe run
agent profile != autonomous agent
subagent plan != subagent runtime
verification plan != verification evidence
handoff != proof of correctness
Notion plan != repository source of truth
```

## The Third Door

The convention layer rejects both raw runtime exposure and disconnected governance ceremony.

The Third Door is a governed wrapper that makes Goose sessions easier, safer, more consistent, and more useful without pretending to own the runtime or silently exercising authority.

## Acceptance Criteria

This ADR is satisfied when builder-II can:

1. resolve target/provider/model/agent/authority/session settings into a single reviewable configuration spine;
2. project that spine into Goose-native environment, recipe, context, and session fields;
3. prove through tests that projection does not imply execution;
4. prove through tests that generic target behavior does not inherit CORE-specific assumptions;
5. provide a consistent builder command vocabulary over Goose workflows;
6. preserve evidence and handoff expectations across the seam;
7. require explicit promotion before runtime-launching or mutation-capable behavior.

## Consequences

Implementation should proceed in thin layers:

1. scenario tests for governed engineering session flow;
2. session configuration artifact;
3. Goose projection artifact;
4. builder command wrapper around projection;
5. agent/subagent orchestration plan artifact;
6. scenario tests proving config-to-Goose projection without authority escalation;
7. runtime candidates only after promotion gates are satisfied.

This keeps builder-II close enough to Codename Goose to be useful and seamless while preserving the governance boundary that makes it trustworthy.
