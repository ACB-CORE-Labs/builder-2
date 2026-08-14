# ADR-0004: CORE-Born Builder's Signet Doctrine

## Status

Accepted

## Context

builder-II is a generic governed local agent/developer platform. It is also CORE-born.

For builder-II, `CORE-born` means the Builder's Signet is embedded as first-principles engineering doctrine, not decorative lineage language.

The Builder's Signet is:

```text
Mechanical Sympathy
Semantic Rigor
The Third Door
```

These pillars shape artifacts, schemas, commands, adapters, promotion gates, verification, rollback, handoff, operator experience, and future integration boundaries.

builder-II remains architecturally separate from CORE, the CORE runtime, and CORE Workbench/UI. CORE-specific behavior belongs in the `core` target profile or in explicit future target adapters, not in the global platform identity.

## Decision

builder-II shall treat the Builder's Signet as platform design law.

This means:

- **Mechanical Sympathy** keeps builder-II aligned with local repositories, Git, Goose, tests, diffs, constrained hardware, human review, and real operator workflows.
- **Semantic Rigor** keeps builder-II precise about plans, execution, verification, promotion, artifacts, approvals, model output, and subagent output.
- **The Third Door** keeps builder-II useful without drifting into ceremony or hidden capability.

The public repository language should use `CORE-born` to mean originating design lineage plus embedded engineering doctrine.

The public repository language should not make builder-II a CORE runtime, CORE Workbench/UI surface, or CORE-only platform.

## Consequences

- The Builder's Signet is an architectural test for future work.
- A feature that violates any pillar is not aligned with builder-II.
- The `core` target profile may contain CORE-specific conventions, but those conventions must not leak globally.
- Notion planning may refine language, but repository ADRs, docs, schemas, tests, command registries, and source code remain the durable project record.

## Acceptance criteria

This ADR is satisfied when future builder-II work can answer:

1. How does this preserve Mechanical Sympathy with real engineering work?
2. How does this preserve Semantic Rigor across claims and artifacts?
3. How does this preserve The Third Door?
4. How does this keep CORE-specific behavior target-profile scoped?
