# Target profiles

builder-II is a generic local agent/developer platform. It can work against multiple repositories through explicit target profiles.

Initial targets:

- `generic` — a normal software repository with no project-specific doctrine.
- `builder` — builder-II self-development.
- `core` — AssetOverflow/core as a target repository.

CORE is a target profile, not builder-II's platform identity. CORE Workbench/UI remains separate from builder-II.

**V.5 boundary (design hygiene):** builder-II may help build/verify Workbench *source* as target work; it is **not** Workbench and does not drive Workbench UX. See [`docs/plan/CORE_WORKBENCH_BOUNDARY.md`](plan/CORE_WORKBENCH_BOUNDARY.md).

## Commands

```bash
builder-targets list
builder-targets show generic
builder-targets show builder
builder-targets show core
builder-targets validate
```

## Rules

- Keep platform behavior generic first.
- Keep CORE-specific behavior isolated to the `core` target profile.
- Do not treat builder-II as CORE Workbench or CORE UI.
- Do not let optional deepagents integration bypass target profile boundaries.

## Next use

Future commands should accept a target name before applying context, verification, agent profile, or notes behavior.

Examples:

```bash
builder-context pack --target builder --changed
builder-context pack --target core --changed
builder-agent render patch_planner --target generic
builder-agent render patch_planner --target builder
builder-agent render core.invariant_auditor --target core
```
