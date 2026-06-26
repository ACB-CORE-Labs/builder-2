# builder-II project overview

builder-II is a generic governed local agent/developer platform for working with target repositories through explicit profiles, artifacts, model policy, verification guidance, and operator-controlled workflows.

It can target CORE through the `core` target profile, but builder-II is not CORE, not CORE Workbench/UI, and not a second CORE runtime.

## What it combines

builder-II currently combines:

- target profiles for `generic`, `builder`, and `core` repositories;
- generic agent profiles and authority contracts;
- context pack and target bundle artifacts;
- verification profile artifacts;
- quality gate artifacts;
- handoff artifacts;
- research planning artifacts;
- Goose configuration, recipes, and session manifest artifacts;
- optional deepagents bridge/readiness specifications;
- MLX-LM local model policy and direct local ask support;
- runtime controls for local model serving and operator-managed sessions;
- documentation and guardrails that separate validated use from future runtime candidates.

## Why it exists

Modern coding agents are powerful but often blur planning, execution, mutation, model calls, and authority. builder-II exists to make local development assistance governable.

The platform should help an operator:

```text
choose target repo and profile
→ package context and intent into artifacts
→ bind agent and verification profiles
→ review plans and quality gates
→ optionally prepare a Goose session manifest
→ approve any future runtime action explicitly
→ verify concrete outputs
→ preserve audit and handoff records
```

The current implementation deliberately stops before autonomous runtime authority. Artifacts are evidence and review objects; they are not permission to execute commands, mutate files, call models, or start agents.

## Main components

| Component | Purpose |
| --- | --- |
| `builder_ii/cli.py` | Main CLI commands such as setup, doctor, models, ask, start, and verify. |
| `builder_ii/target_profiles.py` | Explicit target definitions for generic repos, builder-II itself, and AssetOverflow/core. |
| `builder_ii/agent_profiles.py` | Generic agent profile definitions and authority descriptions. |
| `builder_ii/context_cli.py` | Context packaging for target-scoped review. |
| `builder_ii/bundle_cli.py` | Governed target bundle artifact creation and validation. |
| `builder_ii/verification_cli.py` | Verification profile rendering and validation. |
| `builder_ii/quality_cli.py` | Quality gate artifact planning and validation. |
| `builder_ii/notes_cli.py` | Handoff artifact creation and validation. |
| `builder_ii/research_cli.py` | Artifact-only research planning. |
| `builder_ii/goose_session.py` | Goose session manifest creation and validation. |
| `builder_ii/goose_setup.py` | Goose config, hints, context, skills, and recipe wiring. |
| `builder_ii/goose_launcher.py` | Operator-started Goose session helper. |
| `builder_ii/backends.py` | MLX-LM backend health and served-model checks. |
| `builder_ii/runtime_control.py` | Runtime status/reset helper for local MLX listener and marker state. |
| `builder_ii/model_policy.py` | Runtime policy for each model alias. |
| `builder_ii/lane_guides.py` | Reusable local prompt lanes. |
| `builder_ii/roles.py` | Read-only persona definitions. |
| `builder_ii/role_gates.py` | Capability boundaries for personas. |
| `recipes/` | Goose platform and coding recipes. |
| `.agents/skills/` | Skills copied into the selected target repo by setup flows. |

## Agents, subagents, and tasks

In builder-II, agents and subagents are governed workflow roles, recipes, or future planning harnesses. They are not hidden autonomous authorities.

- Agent profiles define expected behavior and authority boundaries.
- Lane guides provide reusable prompt templates.
- Recipes wire Goose commands such as `/plan`, `/explore`, `/review`, `/verify`, and `/handoff`.
- Skills provide reusable behavioral guidance for Goose sessions.
- Verification profiles keep work anchored to real target-specific checks.
- Future deepagents integration remains optional and subordinate to builder-II governance.

## Tool and connector posture

builder-II configures local developer workflows and optional tool bridges, but runtime authority remains promotion-gated.

Current validated use is setup, planning, review, direct ask, artifact rendering, artifact validation, runtime control, and verification discipline. Autonomous local file editing, hidden model routing, shell execution, source mutation, memory mutation, commit/push automation, and pull request creation remain future capabilities unless explicitly promoted.

## Success criteria

builder-II is successful when an operator can:

1. install it;
2. configure local model and Goose support;
3. validate platform setup with `builder doctor`;
4. select a target profile;
5. package context and intent into reviewable artifacts;
6. bind agent and verification profiles;
7. create quality gate, research, handoff, and Goose session artifacts;
8. understand exactly what each artifact does and does not authorize;
9. run concrete verification before accepting changes;
10. promote future runtime behavior only through explicit docs, tests, HITL approval, rollback, and audit paths.
