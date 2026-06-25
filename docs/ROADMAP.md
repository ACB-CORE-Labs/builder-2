# builder-II roadmap

builder-II is the local development cockpit for building CORE. It is not CORE itself.

CORE is the deterministic cognitive system. builder-II is the operator platform around Goose, local MLX models, prompts, recipes, tools, scripts, and verification commands that help develop CORE safely on an M1-class machine.

## North star

builder-II should make it easy to start a governed local CORE development session with the right model, right prompt, right tools, right context, and right verification path.

The product target is:

```text
Goose + local MLX models + task recipes + prompts + setup scripts + safe operator workflow
```

## What builder-II is

- A Goose/local-agent setup and operations layer.
- A local model roster and runtime manager.
- A prompt/task/persona organizer for common CORE development work.
- A helper for direct local ask, review, planning, summarization, and handoff.
- A verification launcher that keeps CORE work tied to concrete commands.
- A practical guardrail layer so unsupported local tool execution is not mistaken for validated autonomous editing.

## What builder-II is not

- It is not a second CORE runtime.
- It is not a deterministic cognitive substrate.
- It is not an autonomous coding agent until tool execution and file mutation are explicitly validated.
- It is not a place to add abstract gates or manifests unless they directly improve Goose, model, tool, task, or operator configuration.

## Why the current guardrails exist

The model roster, lane guides, personas, gates, and offline checks exist for practical platform governance:

- prevent unsupported model/runtime combinations;
- keep Gemma-style sidecars separate from normal `mlx_lm.server` chat lanes;
- keep heavy models explicit opt-in on M1 16GB;
- make prompt/task routing reusable instead of ad hoc;
- avoid pretending local Goose tool execution is validated before it is;
- give the operator clear handoff and review flows.

These are configuration guardrails, not an attempt to recreate CORE inside builder-II.

## Stop condition for governance scaffolding

Do not keep adding gate layers just because they are architecturally neat. Add more only when a concrete platform need demands it, such as:

- a new Goose recipe needs a role or prompt;
- a new local model needs a runtime boundary;
- a tool needs a smoke test before being exposed;
- a task workflow needs a reproducible command;
- an operator action needs a clear failure mode.

## Near-term milestone: usable Goose/local-agent platform

The next work should prioritize usability:

1. Consolidate command docs and startup flow.
2. Wire Goose recipes/personas from the role and lane-guide definitions.
3. Make task templates directly usable from Goose and direct ask.
4. Add read-only local tool smoke tests.
5. Build a repo context/startup briefing flow for CORE sessions.
6. Add a controlled patch workflow only after read-only tool use is proven.

## Promotion rule

A capability can gain more authority only after it has:

1. clear operator docs;
2. a bounded command path;
3. a deterministic smoke test;
4. an explicit failure mode;
5. evidence that it does not bypass human review or CORE verification.

Until then, builder-II should stay conservative: review, plan, summarize, verify, and assist the operator.

## Current phase boundary

The governance scaffolding phase is complete enough. The next phase is platform wiring and usability.
