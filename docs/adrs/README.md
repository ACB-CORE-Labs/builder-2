# builder-II Architecture Decision Records

This directory records durable architecture decisions for builder-II.

builder-II is CORE-born and governed by the Builder's Signet, but it is a generic governed local agent/developer platform. CORE is the originating design lineage and a first-class target profile, not the global platform identity. ADRs in this directory should preserve that distinction while treating CORE's engineering signet — Mechanical Sympathy, Semantic Rigor, and The Third Door — as first-principles design doctrine for the developer-platform layer.

## Index

| ADR | Status | Decision |
| --- | --- | --- |
| [`ADR-0001`](ADR-0001-core-builder-ii-governed-engineering-extension.md) | Accepted | Define builder-II as a governed engineering extension: CORE-born, Codename-Goose-reinforcing, generic-first, engineer-centered, and governed by Mechanical Sympathy, Semantic Rigor, and The Third Door. |
| [`ADR-0002`](ADR-0002-builder-convention-layer-over-codename-goose.md) | Accepted | Define the builder convention layer over Codename Goose: stable builder commands/config/profiles/artifacts above, Goose-native env/recipe/context/session surfaces underneath. |
| [`ADR-0003`](ADR-0003-builder-ii-generic-platform-identity-and-capability-factory.md) | Accepted | Refine builder-II identity as a generic governed platform, define repo docs as source of truth over Notion planning, and establish the profile-pack/capability-factory direction. |
| [`ADR-0004`](ADR-0004-core-born-builders-signet-doctrine.md) | Accepted | Define `CORE-born` as originating design lineage plus embedded Builder's Signet doctrine, while keeping CORE-specific behavior target-profile scoped. |
| [`ADR-0005`](ADR-0005-codevault-boundary-and-authority.md) | Accepted | Define CodeVault as a reconstructive intelligence substrate whose outputs never grant execution or promotion authority; builder-II remains the sole governance/control plane at every capability tier. |

## ADR discipline

Each ADR should state the engineering problem, decision, authority boundary, evidence or test expectation, and relationship to Codename Goose, CORE runtime, CORE Workbench/UI, and optional future harnesses where relevant.
