# Codename Goose Convention Layer

builder-II uses Codename Goose as the primary local execution-capable agent platform.

builder-II does not replace Goose. It wraps, reinforces, and governs Goose through a stable builder convention layer.

The goal is practical: give the engineer one consistent builder-II way to configure, prepare, inspect, verify, and hand off local agent work while still using Goose-native execution surfaces underneath.

## Canonical Goose References

Keep these references close during design and implementation:

- Goose docs: <https://goose-docs.ai/>
- Agentic AI Foundation: <https://aaif.io/>
- Goose GitHub: linked from the Goose docs site

As of this document's creation, the Goose docs identify Goose as open source, Apache 2.0, and part of the Agentic AI Foundation. They describe Goose as a native open-source AI agent with desktop, CLI, and API surfaces; MCP extensions; provider flexibility; recipes; MCP Apps; subagents; and security controls.

These docs are not background reading. They are the reference surface for the convention layer. As Goose evolves under AAIF, builder-II should track the public Goose docs closely and prefer native Goose concepts over invented substitutes.

## Core Rule

```text
Use Codename Goose natively underneath.
Expose builder conventions above.
Preserve governance and evidence around the seam.
```

This is the implementation-facing rule from [`ADR-0002`](adrs/ADR-0002-builder-convention-layer-over-codename-goose.md).

## Why This Exists

Raw Goose sessions are powerful, but operators still need to resolve:

- target repository;
- target profile;
- provider;
- model alias;
- model tier;
- agent role;
- future subagent plan;
- context pack;
- authority mode;
- recipe;
- verification profile;
- handoff convention;
- evidence requirements.

builder-II should resolve those consistently before Goose is launched.

## Configuration Layers

builder-II keeps these layers distinct:

```text
.env                 = local machine details and secrets
builder config       = declared engineering policy and defaults
resolved session     = concrete target/provider/model/agent/authority selection
Goose projection     = Goose-native env/recipe/context/session surface
artifact             = reviewable evidence of what was selected, planned, or projected
runtime execution    = actual Goose process/session behavior, requiring explicit authority
```

The distinction matters.

A resolved configuration is not a launched session.
A Goose projection is not Goose execution.
A recipe path is not a completed task.
A handoff is not proof of correctness.

## Configuration Resolution Spine

Every governed session should resolve a single spine:

```text
target repo
-> target profile
-> provider/model policy
-> model alias/tier
-> agent profile
-> subagent plan, if any
-> authority mode
-> context pack
-> Goose recipe/projection
-> verification profile
-> evidence outputs
-> handoff expectation
```

This spine should be reviewable before runtime activation.

## Goose-Native Projection

A resolved builder session may project to Goose-native fields such as:

```text
GOOSE_PROVIDER
OPENAI_HOST / OLLAMA_HOST
GOOSE_MODEL
GOOSE_TEMPERATURE
GOOSE_PLANNER_PROVIDER
GOOSE_PLANNER_MODEL
GOOSE_RECIPE_PATH
GOOSE_MOIM_MESSAGE_FILE
BUILDER_MODEL_TIER
BUILDER_MODEL_ALIAS
BUILDER_SESSION_MODE
working directory
session name
resume flag
built-ins/extensions
```

The projection should be deterministic and inspectable.

## Builder Command Convention

The operator-facing command surface should prefer builder language over raw runtime choreography.

Possible convention families:

```text
builder plan
builder inspect
builder review
builder verify-plan
builder handoff
builder goose plan
builder goose session
builder goose resume
```

The exact CLI names may evolve, but the principle should not: builder-II gives the engineer one coherent convention, and the convention compiles into Goose-native behavior underneath.

## Authority Boundary

The convention layer may prepare, render, validate, and project.

It must not silently:

- launch Goose;
- run shell commands;
- mutate source files;
- approve HITL gates;
- claim verification passed;
- commit or push changes;
- merge work;
- promote runtime capability;
- construct deepagents runtime;
- invoke MCP tools.

Crossing from projection into runtime execution requires explicit capability promotion and operator authority.

## Agent and Subagent Direction

Agent and subagent concepts are builder conventions first.

An agent profile describes role, context needs, authority, forbidden tools, HITL boundaries, and output contract.

A future subagent plan should describe role, task, input context, dependency, authority, expected output, handoff contract, and verification expectation.

Neither an agent profile nor a subagent plan is runtime execution evidence.

## Implementation Order

The convention layer should come alive in this order:

1. scenario test for governed engineering session flow;
2. session configuration artifact;
3. Goose projection artifact;
4. builder command wrapper around projection;
5. agent/subagent orchestration plan artifact;
6. scenario test proving config-to-Goose projection without authority escalation;
7. runtime candidates only after promotion gates are satisfied.

## Product Standard

The intended operator experience:

```text
I use builder commands.
builder-II resolves the correct target, model, profile, context, and authority.
Codename Goose receives the right native session shape.
The work feels ready before it starts.
I still own execution authority.
```

That is the convention layer standard.
