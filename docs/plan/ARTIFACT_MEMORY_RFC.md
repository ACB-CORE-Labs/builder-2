# Artifact memory RFC

Status: design-only RFC.

This document defines the first builder-II memory design as a governed artifact graph. It does not implement memory mutation, retrieval, model calls, runtime behavior, or a CORE-style vault.

## Purpose

builder-II needs long-session continuity and reviewable recall without hidden agent memory. The safe starting point is not a magical memory subsystem. The safe starting point is content-addressed, provenance-carrying artifacts.

```text
validated artifact
+ stable kind
+ schema version
+ sha256
+ target profile
+ task
+ source refs
+ parent refs
+ claim boundary
+ review state
= governed memory atom
```

The platform can later reconstruct context from these atoms instead of trusting stale chat history or opaque agent memory.

## Non-goals

This RFC does not authorize:

- autonomous durable memory mutation;
- hidden agent memory;
- model-generated memory as truth;
- replacing source files, git state, or validated artifacts with summaries;
- CORE Workbench/UI coupling;
- making builder-II a CORE runtime;
- shell execution;
- command execution;
- source mutation;
- model calls;
- deepagents construction;
- source collection, web search, or MCP execution.

## Terminology

### Memory atom

A memory atom is a validated artifact plus metadata sufficient to reconstruct why it exists and what it may safely claim.

### Artifact graph

The artifact graph is the relationship between memory atoms through parent references, source references, target profile, task, and verification lineage.

### Reconstruction

Reconstruction is the process of selecting relevant memory atoms for a target/task and producing a reviewable context pack or summary. Reconstruction does not grant authority.

## Canonical memory sources

The canonical memory layer begins with artifacts builder-II already understands or is actively adding:

- target bundle artifacts;
- verification profile artifacts;
- quality gate artifacts;
- research plan artifacts;
- handoff artifacts;
- Goose session manifests;
- read-only audit artifacts;
- bounded inspection audit artifacts;
- future linked artifact audit records;
- future compatibility reports;
- future git state records;
- future approval records;
- future verification records;
- future rollback records;
- future context summary artifacts.

## Memory atom envelope

Future memory-compatible artifacts should expose or be wrapped by an envelope with fields like:

```json
{
  "kind": "builder_ii.memory_atom",
  "schema_version": 1,
  "artifact_kind": "builder_ii.goose_session_manifest",
  "artifact_schema_version": 1,
  "artifact_path": ".builder/artifacts/goose-session.json",
  "artifact_sha256": "...",
  "target_profile": "builder",
  "task": "inspect repo state",
  "created_at_utc": "2026-06-26T00:00:00Z",
  "source_refs": [],
  "parent_artifact_refs": [],
  "claim_boundary": "artifact_schema_and_recorded_fields_only",
  "review_state": "unreviewed",
  "artifact_is_authority": false
}
```

The envelope records provenance. It does not make the artifact authoritative.

## Claim boundaries

Every memory atom must state what kind of claim it supports.

Suggested boundaries:

| Claim boundary | Meaning |
| --- | --- |
| `schema_validity_only` | Artifact matched schema and invariant checks. |
| `operator_declared_intent` | Task/summary was declared by the operator. |
| `metadata_only` | Artifact records metadata, not contents. |
| `verification_result` | Artifact records a concrete verification result. |
| `reviewed_handoff` | Artifact was reviewed as a handoff, not source truth. |
| `derived_summary` | Artifact is lossy and must carry source refs. |
| `proposal_only` | Artifact proposes future work but grants no authority. |

No atom should claim more than its evidence supports.

## Artifact graph links

Artifacts should link to prior artifacts explicitly instead of relying on chat context.

Examples:

```text
Goose session manifest
→ read-only audit
→ bounded inspection audit
→ linked artifact audit
→ compatibility report
→ handoff
```

Each child should include parent paths or hashes where practical.

## Review states

Suggested review states:

| State | Meaning |
| --- | --- |
| `generated` | Produced by a command or model but not reviewed. |
| `validated` | Schema/invariant validation passed. |
| `operator_reviewed` | Human reviewed the artifact. |
| `superseded` | Replaced by a newer artifact. |
| `invalidated` | Later evidence shows the artifact should not be used. |

Review state is separate from truth. A reviewed artifact can still be limited to a narrow claim boundary.

## Reconstruction workflow

Future reconstruction may look like:

```text
input: target profile + task + current git state
→ locate relevant memory atoms
→ verify hashes and schema versions
→ filter by review state and claim boundary
→ order by dependency/parent chain
→ emit context reconstruction artifact
→ optionally summarize with MLX as derived summary
```

The reconstruction artifact must include:

- selected atom refs;
- excluded atom refs and reasons;
- source hashes;
- target profile;
- task;
- reconstruction policy;
- known gaps;
- artifact_is_authority: false.

## Relationship to context summaries

Context summaries are derived artifacts. They may help humans and models regain context, but they are never canonical memory.

A summary must carry:

- source artifact refs;
- source hashes;
- model alias and backend when model-generated;
- prompt/profile used;
- known omissions;
- review_required: true;
- artifact_is_authority: false.

## Relationship to CORE-inspired vault ideas

CORE-inspired reconstruction-over-storage and exact retrieval ideas may inform future experiments, but builder-II must not become CORE or a CORE runtime.

For builder-II, the safe interpretation is:

```text
artifact graph first;
content addressing first;
provenance first;
review state first;
retrieval later;
models never as authority.
```

Any CORE-specific behavior belongs in the `core` target profile or an explicit future adapter.

## Promotion path

### Phase 1: documentation only

- This RFC.
- No implementation.

### Phase 2: memory atom schema artifact

- Add schema and validator for memory atom envelopes.
- No automatic indexing.
- No hidden storage.

### Phase 3: explicit index artifact

- Add command to create a memory index from explicit artifact paths.
- Index records hashes and relationships only.
- No model calls.

### Phase 4: reconstruction artifact

- Add command to reconstruct context from explicit index and task.
- Output is a review artifact.

### Phase 5: optional summary artifact

- Add MLX/local summarization only as derived summary with source refs.
- Human review required.

## Denied until separate promotion

- autonomous memory writes;
- implicit background indexing;
- model-authored canonical memory;
- semantic search as authority;
- mutation of source artifacts;
- unreviewed durable summaries;
- hidden retrieval in runtime sessions;
- retrieval that bypasses target profiles, verification profiles, quality gates, or audit artifacts.

## Acceptance criteria for first implementation

A future implementation PR must prove:

- memory atoms are explicit artifacts;
- content hashes are stable;
- invalid atoms fail closed;
- summaries cannot be treated as authority;
- target profile boundary is preserved;
- CORE Workbench/UI remains separate;
- no shell, model, deepagents, source mutation, commit, push, PR, source collection, web search, or MCP behavior is enabled.
