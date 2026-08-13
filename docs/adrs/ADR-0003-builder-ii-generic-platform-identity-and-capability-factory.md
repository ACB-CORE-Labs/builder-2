# ADR-0003: builder-II Generic Platform Identity and Capability Factory

## Status

Accepted

## Context

ADR-0001 and ADR-0002 established builder-II as CORE-born, Codename-Goose-reinforcing, generic-first, engineer-centered, and governed by the Builder's Signet. They also used earlier shorthand such as `CORE builder-II`, `CORE product`, and `brand extension`.

The implementation and design discussion have since refined the language boundary. The architecture did not change in its core constraints: builder-II remains generic-first, Goose-reinforcing, evidence-bearing, and HITL-gated. The phrasing needed tightening so no document implies that builder-II is CORE, a CORE runtime, CORE Workbench/UI, or a CORE-only product surface.

The refined platform identity is:

```text
builder-II = generic governed local agent/developer platform
CORE       = first-class target profile and lineage context
Goose      = local operator/runtime adapter under builder-II governance
deepagents = optional inner planning/delegation harness under builder-II governance
MCP        = external capability adapter under builder-II governance
models     = reasoning/proposal/review adapters under builder-II governance
```

The next architectural refinement is that builder-II should not only ship built-in governed workflows. It should become a governed capability factory where users can create and promote their own target profiles, agent profiles, subagent profiles, task profiles, tool profiles, MCP policies, context packs, model policies, verification profiles, approval policies, Goose projections, deepagents projections, and handoff profiles.

## Decision

builder-II shall be documented and implemented as a generic governed local agent/developer platform. CORE remains a first-class target profile and origin lineage, not the global platform identity.

Older phrases such as `CORE builder-II`, `CORE product`, and `brand extension` should be treated as historical lineage shorthand only. New documentation should prefer:

```text
builder-II
builder-II platform
local agent/developer platform
governed platform
target repo
target profile
target adapter
agent profile
verification profile
context target
```

New documentation should avoid:

```text
CORE cockpit
CORE Workbench
CORE UI cockpit
CORE runtime cockpit
CORE product identity for builder-II
CORE-only platform identity
```

**V.5 (2026-07-13) cross-ref:** The full Workbench separation (what builder-II may do for Workbench *source* as target work vs what Workbench owns as product UI, plus design-only requirements for any future authorized adapter) lives in [`docs/architecture/CORE_WORKBENCH_BOUNDARY.md`](../plan/CORE_WORKBENCH_BOUNDARY.md). That document is hygiene/spec only; it does not authorize coupling or promote a Workbench adapter.

## Source-of-truth hierarchy

Repository documentation is authoritative for builder-II architecture.

The source-of-truth order is:

1. accepted ADRs and later ADR refinements;
2. `README.md` identity and architecture summary;
3. `docs/MANIFESTO.md` product doctrine;
4. `docs/ROADMAP.md` current status and promotion plan;
5. implementation docs, command registries, schemas, tests, and source code;
6. Notion planning artifacts and external notes as supportive planning material only.

Notion artifacts may help plan, summarize, or organize work. They must not override repository ADRs, source code, tests, command authority registries, artifact schemas, or promotion records.

When a Notion artifact captures a genuine refinement, that refinement must be reconciled back into the repository through docs, ADRs, schemas, tests, or code before it is treated as project truth.

## Capability factory lifecycle

User-created capabilities must follow a common lifecycle:

```text
scaffold
→ render
→ validate
→ dry-run
→ inspect
→ propose
→ approve
→ execute only if promoted
→ verify
→ record
→ handoff
```

A capability may not skip from profile/spec/artifact existence to runtime authority.

## First-class profile-pack direction

builder-II should support governed profile packs as a first-class extension layer.

Initial pack surface:

```text
.builder/profiles/
  agents/
  subagents/
  tasks/
  tools/
  context/
  verification/
  approvals/
  goose/
  deepagents/
  mcp/
  handoff/
  packs/
```

A profile pack should be able to declare:

- target profiles;
- agent profiles;
- subagent profiles;
- task profiles;
- tool profiles;
- MCP inventory/policy stubs;
- context pack definitions;
- model routing policy candidates;
- verification profiles;
- approval policies;
- Goose projections;
- deepagents projections;
- handoff profiles.

Every pack must expose deterministic artifacts, schema versions, source refs, content hashes, authority classifications, denied defaults, expected outputs, promotion requirements, and validation results.

## Planning completeness map

The master plan should track these first-class surfaces:

1. core governance spine;
2. capability factory and profile packs;
3. runtime promotion;
4. operator experience and command ergonomics;
5. artifact memory and context reconstruction;
6. event ledger and observability;
7. security and secret boundaries;
8. test/proof matrix;
9. extension distribution and upgrade hygiene;
10. demos, docs, release proof, and recovery playbooks.

These surfaces refine the original master plan without weakening the core doctrine.

## Non-goals

This ADR does not authorize:

- autonomous writes;
- shell execution;
- hidden model calls;
- Goose runtime activation;
- deepagents construction;
- MCP tool execution;
- source collection;
- durable memory mutation;
- commit, push, PR, merge, or release authority;
- CORE Workbench/UI coupling;
- CORE-specific behavior outside the `core` target profile;
- treating Notion planning artifacts as implementation authority.

## Consequences

- Docs should use `CORE-born` for lineage and reserve `CORE` behavior for the `core` target profile.
- Existing ADRs remain historically valid, but this ADR refines their identity language.
- `docs/MANIFESTO.md`, `docs/ROADMAP.md`, and ADR indexes should align with the refined identity vocabulary.
- Notion planning pages should explicitly remain supportive planning artifacts.
- New implementation work should begin with the profile-pack/capability-factory substrate before live runtime expansion where that substrate changes downstream architecture.

## Acceptance criteria

This ADR is satisfied when:

- repository docs no longer imply builder-II is CORE, CORE Workbench/UI, a CORE runtime, or a CORE-only platform;
- CORE is consistently represented as target profile and lineage context;
- source-of-truth hierarchy is explicit;
- profile packs are represented as a first-class future platform substrate;
- Notion artifacts are explicitly non-authoritative and reconciled into repo docs/code when they contain real refinements;
- all future capability promotion still requires docs, tests, command surface, failure mode, human approval boundary, output artifact, rollback path, and verification path.
