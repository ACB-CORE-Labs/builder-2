# builder-II Architecture Decision Records

This directory records durable architecture decisions for CORE builder-II.

builder-II is a CORE product and brand extension, but it remains architecturally separate from the CORE runtime and CORE Workbench/UI. ADRs in this directory should preserve that distinction while carrying CORE's engineering signet into the developer-platform layer.

## Index

| ADR | Status | Decision |
| --- | --- | --- |
| [`ADR-0001`](ADR-0001-core-builder-ii-governed-engineering-extension.md) | Accepted | Define CORE builder-II as a governed engineering extension: CORE-born, Codename-Goose-reinforcing, generic-first, engineer-centered, and governed by Mechanical Sympathy, Semantic Rigor, and The Third Door. |
| [`ADR-0002`](ADR-0002-builder-convention-layer-over-codename-goose.md) | Accepted | Define the builder convention layer over Codename Goose: stable builder commands/config/profiles/artifacts above, Goose-native env/recipe/context/session surfaces underneath. |

## ADR discipline

Each ADR should state:

- the engineering problem;
- the decision;
- the authority boundary;
- the evidence or test expectation;
- the relationship to Codename Goose, CORE runtime, CORE Workbench/UI, and optional future harnesses where relevant.

ADRs are not runtime authority. A design decision does not promote autonomous writes, shell execution, model calls, Goose runtime activation, deepagents construction, verification-passed claims, or merge authority unless the corresponding capability promotion path is documented, tested, approved, and evidenced.
