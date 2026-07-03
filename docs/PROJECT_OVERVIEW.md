# builder-II — Project Overview

## Identity

builder-II is a **generic governed local agent/developer platform**.

It is not CORE. It is not the CORE Workbench. It is not a second CORE
runtime. It may target CORE as one repository/profile, but it remains
logically and architecturally separate from CORE itself.

---

## First-Class Concepts

| Concept | Description |
|---|---|
| Target repository | The repository being operated on |
| Target profile | Named bundle of defaults and conventions for a target |
| Context pack | Curated context for an agent session |
| Prompt profile | Prompt conventions for a session type |
| Agent profile | Agent role and capability envelope |
| Verification profile | Verification conventions for a target |
| Git state artifacts | Pre/post-flight git state records |
| Note/handoff artifacts | Operator-to-operator context records |
| Optional runtime harness | Governed execution harness (Goose, deepagents) |

---

## Target Profiles

Initial target profiles:

| Profile | Purpose |
|---|---|
| `generic` | Any normal software repository |
| `builder` | builder-II self-development |
| `core` | AssetOverflow/core development (target profile only) |

CORE-specific behaviour (repo path, agent defaults, invariant conventions)
lives exclusively inside the `core` target profile/adapter — never in
platform-level config resolution.

---

## Architecture Guardrails

These guardrails are enforced by tests and must not be violated:

### 1. builder-II is generic-first

All platform-level modules must be target-agnostic. A module that works
only for CORE is not a platform module — it is a target adapter.

### 2. CORE is a target profile/adapter

CORE appears in builder-II only as:
- A named entry in `target_profiles.py`
- A named entry in `target_profile_defaults.py`
- A `CoreDemoAdapter` in `core_demo_loop.py`

CORE must never appear as implicit platform behaviour.

### 3. Target defaults must not live in generic config resolution

`config_sources.py` is target-agnostic. It delegates all target-specific
defaults to `target_profile_defaults.py`. The config resolver must not
contain:

- Hardcoded target repo paths
- Hardcoded target agent names
- Target-to-repo or target-to-agent maps

Violations of this rule are detected by `tests/test_config_sources.py`
(`TestConfigSourcesBoundaryGuard`).

### 4. Demo loops must be generic-first or adapter-scoped

Demo loops that are specific to a target must:

- Implement a generic base class (`GenericTargetDemoLoop`)
- Isolate all target-specific strings in an adapter class
- Accept the adapter as an injected parameter
- Never hardcode target-specific strings in the generic base

### 5. Deepagents is optional and governed

Deepagents support is **optional**. The approved protocol lane
(`protocol_fake`) is a bounded, governed proof lane — it is not native
deepagents runtime promotion. See `docs/DEEPAGENTS_POLICY.md` for the
full policy.

Native deepagents construction, model invocation, tool/MCP execution,
shell execution, and autonomous source writes remain **disabled** until
explicit capability promotion.

---

## System Boundaries

### builder-II owns

- Local setup and model/runtime policy
- Goose setup and recipes
- Prompt/lane/persona definitions
- Tool registry and context packs
- Repo targets and git pre/postflight
- Verification profiles
- Notes and handoffs
- Optional agent/subagent orchestration

### CORE (target profile, not platform identity)

CORE is the deterministic cognitive engine project. In builder-II, CORE
appears only as a target profile/adapter.

### CORE Workbench/UI

CORE Workbench lives inside the CORE product context. builder-II must not
become the Workbench or claim to drive Workbench UX flows.

### deepagents (optional harness)

Deepagents is an optional agent/subagent harness. It must not bypass
builder-II governance. It starts generic-first and is gated by readiness
audits before any execution capability is enabled.

---

## Governance Invariants

All builder-II operations preserve:

- No autonomous source writes by default.
- No shell execution without HITL approval.
- No bypassing verification.
- No hidden agent authority.
- No Deephaven changes.
- No claims without artifacts.
- No CORE Workbench/UI coupling.
