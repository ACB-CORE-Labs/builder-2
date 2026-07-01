# Artifact Memory

`builder-memory` is the B8 passive artifact-memory lane for builder-II.

It records explicit, content-addressed continuity artifacts. It does not add hidden memory, an opaque vector store, autonomous writes, runtime execution, model authority, shell execution, MCP/tool execution, Goose runtime, deepagents runtime, or target-repo mutation.

## Artifacts

- `builder_ii.memory_atom`
- `builder_ii.memory_index`
- `builder_ii.memory_search_result`
- `builder_ii.memory_reconstruction`

Every artifact keeps:

- `artifact_is_authority: false`
- `grants_authority: false`
- disabled runtime/model/shell/memory-mutation governance
- explicit source or parent refs
- deterministic canonical digests

## Commands

```bash
builder-memory atom SOURCE_ARTIFACT.json --output MEMORY_ATOM.json
builder-memory index MEMORY_ATOM.json --output MEMORY_INDEX.json
builder-memory search MEMORY_INDEX.json --query "artifact memory" --output MEMORY_SEARCH.json
builder-memory reconstruct MEMORY_INDEX.json --query "artifact memory" --output MEMORY_RECONSTRUCTION.json
builder-memory validate-atom MEMORY_ATOM.json
builder-memory validate-index MEMORY_INDEX.json
builder-memory validate-search-result MEMORY_SEARCH.json
builder-memory validate-reconstruction MEMORY_RECONSTRUCTION.json
```

## Boundaries

- Memory is explicit artifact output only.
- Search is deterministic lexical scoring only.
- Reconstruction is replay-stable review data only.
- Handoff-derived atoms require source refs and cannot inflate prose into source truth.
- Model-generated summaries remain derived and non-authoritative.

## Truth state

Artifact memory is now `PASSIVE_FOUNDATION`.

That means:

- atoms, indexes, search results, and reconstruction artifacts exist;
- command authority and chain validators know these kinds;
- searchable handoffs are explicit and reviewable;
- hidden memory, vector search, and autonomous memory writes remain disabled.
