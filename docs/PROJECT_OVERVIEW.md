# builder-II project overview

builder-II is a local development cockpit for building CORE on Apple Silicon.

It combines:

- Codename Goose for local coding sessions;
- MLX-LM model serving for local text models;
- model aliases and runtime policy;
- direct local ask for small questions;
- Goose recipes and slash-command workflows;
- builder-II skills copied into the CORE repo;
- runtime lifecycle helpers;
- verification helpers for CORE test routing;
- docs and guardrails that separate validated use from experimental use.

## Why it exists

CORE development needs a local fallback when cloud coding tools are unavailable or unsuitable. builder-II provides that local path without pretending a small model has frontier-model autonomy.

The intended operating mode is:

```text
operator chooses task
builder-II selects/configures local lane
Goose/direct ask helps plan or review
operator verifies with concrete commands
changes are accepted only after tests and review
```

## Main components

| Component | Purpose |
| --- | --- |
| `builder_ii/cli.py` | Main CLI commands such as setup, doctor, models, ask, start, verify. |
| `builder_ii/goose_setup.py` | Writes Goose config, hints, context, skills, and recipe wiring. |
| `builder_ii/goose_launcher.py` | Starts governed Goose sessions. |
| `builder_ii/backends.py` | MLX-LM backend health and served-model checks. |
| `builder_ii/runtime_control.py` | Runtime status/reset helper for local MLX listener and marker state. |
| `builder_ii/model_policy.py` | Runtime policy for each model alias. |
| `builder_ii/lane_guides.py` | Reusable local prompt lanes. |
| `builder_ii/roles.py` | Read-only persona definitions. |
| `builder_ii/role_gates.py` | Capability boundaries for personas. |
| `recipes/` | Goose platform and coding recipes. |
| `.agents/skills/` | Skills copied into the CORE repo for Goose sessions. |

## Agents, subagents, and tasks

In builder-II, agents and subagents are practical Goose/persona workflows rather than independent autonomous services.

- Personas define how a lane should behave.
- Lane guides provide reusable prompt templates.
- Recipes wire Goose commands such as `/plan`, `/explore`, `/review`, `/verify`, and `/handoff`.
- Skills provide reusable behavioral guidance for Goose sessions.
- Verification commands keep the operator anchored to real test output.

## Tool and connector posture

builder-II currently configures Goose extensions for developer tools, skills, and summon-style workflows where available. Local MLX chat is validated for text responses, but local Goose tool execution is still treated as unvalidated until a dedicated smoke test proves it.

That means builder-II is useful today for setup, planning, review, direct ask, runtime control, and verification discipline. Autonomous local file editing remains a future capability, not a current claim.

## Success criteria

builder-II is successful when another operator can:

1. install it;
2. download or select local models;
3. run `builder doctor`;
4. start a governed Goose session;
5. use the right recipe for a task;
6. ask local models small questions directly;
7. reset/switch local runtimes safely;
8. run verification commands;
9. understand exactly what is and is not validated.
