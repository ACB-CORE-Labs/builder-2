# CodeVault Wave-2 Work Orders (PR-4, PR-5, PR-6) — G1b completion

**Status:** Dispatchable work orders for the [execution map](CODE_VAULT_EXECUTION_MAP.md)'s wave 2.  
**Kind:** Design / work orders (RECORDED_ONLY). Implements no capability by existing.

Wave 1 (G1 scaffolding) merged 2026-07-11, so the schemas these orders consume are settled. Wave 2
completes **G1b — real-repo scale and honesty**: the frame stops implying full coverage, the
refresh≡rebuild law is pinned before any optimizer exists, and the linter's quadratic scan is
indexed. None of these touch F2 intelligence (that is G2 / PR-7, authored separately).

Each order resolves every design decision in advance. If a decision survives contact with the code
imperfectly, the implementing PR **amends this document in the same change** — never diverges
silently. All three inherit the [standing invariants](CODE_VAULT_EXECUTION_MAP.md#standing-invariants-every-pr-in-this-slice-inherits)
(severability + its import allowlist, governance block, claim law, fail-closed, TDD, docs-in-same-PR,
frame byte-stability) and the [work-order protocol](CODE_VAULT_EXECUTION_MAP.md#work-order-protocol)
(battery **after** the last commit; receipt head_sha == pushed head).

**Dependencies:** PR-4 and PR-6 are independent of each other and of PR-5 — implement concurrently in
separate worktrees, one branch per PR from `main`. PR-5 is independent but should reference PR-4's
coverage block in its determinism pin if both are in flight (note in PR-5 below).

---

## Code-clock starting line (measured on merged main `1116c4f`)

| Surface | Fact |
|---|---|
| `repo_map.py` | Already emits `truncated` (bool), `file_count` (int), `scan_state` (`READ_ONLY`), default `max_files = 500`. Truncation honesty exists **at repo-map level**. |
| `code_vault/repo_map_adapter.py` | `hierarchical_input_from_repo_map(...)` returns `{"files": [...]}` — it **strips** `truncated`/`file_count`; by the time `create_hierarchical_frame` runs, those fields are gone. |
| `code_vault/hierarchy.py` | `create_hierarchical_frame(repo_map, *, target_name, provenance=None)`; schema `2`, `PROVENANCE_FRAME_SCHEMA_VERSION = 3`, `SUPPORTED = (1,2,3)`. Provenance is the additive-optional-block precedent (default-off, byte-identical, provenance-gated version bump). `canonical_frame_json` only serializes `provenance` when present. The frame surfaces **no coverage/truncation** today. |
| `code_vault/reports/linter.py` | `run_geometric_linter`: for each symbol node, a **linear scan over all file nodes** to find its parent (`for file_node in file_nodes: if symbol.parent_layout_digest == file_node.layout_digest`), plus `_module_sphere_for_file` re-scans `frame.nodes` per call → O(symbols × files). Clone scan is already linear (digest grouping). |
| Determinism pin (exists) | `tests/test_code_vault_hierarchy.py::test_same_repo_map_produces_identical_frame_digest` — rebuild-determinism is already pinned; PR-5 extends it into the refresh≡rebuild law. |

---

## PR-4 — Coverage honesty on the frame (G1b)

**Objective:** a hierarchical frame can declare that it describes a **truncated / scoped** view, so
it never silently implies full-repo coverage. Closes the gap-map row *"full-repo maps without
truncation lies"* at the frame level.

**Claims unlocked:** honest scoped indexing. **Refused:** full-monorepo coverage without flags; any
claim that a truncated frame is complete.

### Resolved design decisions

1. **Caller-threaded, not adapter-derived.** The adapter strips `truncated`/`file_count`, and
   changing the adapter to preserve them would silently alter every real-repo frame's bytes
   (invariant #8). So coverage is an explicit optional param on `create_hierarchical_frame`, exactly
   like provenance. An in-package helper `build_frame_coverage(repo_map) -> dict` (repo_map is an
   allowed import — severability allowlist) reads `truncated`/`file_count`/`max_files` from a
   **full** repo_map and shapes the block; the caller passes its output in.

   **Amendment (recorded during PR-4 implementation):** `create_repo_map`'s `max_files` bound is a
   *call parameter* to `builder_ii/repo_map.py::create_repo_map`, not a key it persists onto the
   emitted repo_map dict (only `truncated`, `file_count`, and `scan_state` are). `build_frame_coverage`
   therefore cannot read `max_files` back off `repo_map` as this decision originally assumed. Resolved
   without touching `repo_map.py` (out of scope for this PR; would also risk that artifact's own
   byte-stability): `build_frame_coverage(repo_map, *, declared_bound: int | None = None)` takes
   `declared_bound` as an explicit caller-supplied override — `None` means unbounded/unknown, matching
   the block shape's existing `null` case below. Callers who know the `max_files` value they scanned
   with (e.g. because they called `create_repo_map` themselves) pass it through explicitly.
2. **Default-off / byte-stable.** `create_hierarchical_frame(..., coverage=None)` — absent → no block
   → byte-identical to today. The recorded schema-v2 digest pin (`97fa0331…277f`) and demo pins stay
   green. `canonical_frame_json` serializes `coverage` only when present (same conditional as
   `provenance`).
3. **Shares the v3 gate.** Emitted `schema_version` becomes `3` when **either** `provenance` **or**
   `coverage` is present (generalize the existing provenance-gated bump); stays `2` when both absent.
   No new schema constant — reuse `PROVENANCE_FRAME_SCHEMA_VERSION` (rename its comment to "additive
   top-level blocks," not a new number).
4. **Coverage ≠ provenance.scope.** Provenance's `scope` says *which repo state* (commit/path set);
   coverage says *how much of that scope this frame actually contains* (truncation, counts). They are
   distinct top-level blocks. A frame may carry both, one, or neither.
5. **Vault validates, in-package derivation is fine.** Unlike provenance (whose derivation reads
   `.git`, outside the package), coverage derives from the repo_map the frame is already built from —
   pure in-package computation, no severability concern.

### Coverage block shape (schema v3)

```text
coverage: {
  truncated: true | false,
  file_count: <int ≥ 0>,           # files actually in this frame's scope
  declared_bound: <int> | null,    # caller-supplied scan bound (e.g. max_files used), null if
                                   # unbounded/unknown — see PR-4 amendment above: repo_map does
                                   # not persist max_files, so this is not read off repo_map
  scan_state: "READ_ONLY"          # mirrors repo_map; fail-closed on any other value
}
```

Validator `validate_frame_coverage(block)`: object; `truncated` bool; `file_count` non-negative int;
`declared_bound` non-negative int or null; `scan_state == "READ_ONLY"`; unknown keys refused; missing
required keys refused.

### Files

Edit `code_vault/hierarchy.py` (coverage field on `HierarchicalFrame` + `create_hierarchical_frame`
param + `validate_frame_coverage` + `build_frame_coverage` helper + conditional serialization +
`hierarchical_frame_from_dict` round-trip + generalized version gate); edit
`tests/test_code_vault_hierarchy.py`; docs: staged-acceptance amendment, gap-map row
(`Full-repo maps without truncation lies` → landed partial at frame level), `CODE_VAULT_HIERARCHY.md`
note. **No CLI change required** (coverage is threaded by callers; wiring prepare-package to opt in is
a later, separate PR — out of scope, note it).

### Tests first

Default-off byte-identity (frame without `coverage` == recorded v2 digest); frame with coverage →
schema 3, round-trips byte-stably; frame with **both** provenance and coverage → schema 3, both
serialize, round-trip; `build_frame_coverage` reads a full repo_map correctly (truncated + counts);
validator refuses unknown keys / bad `scan_state` / negative counts / missing keys; a coverage-only
frame (no provenance) is schema 3 and valid; demo suite untouched.

### Out of scope

Wiring prepare-package/workflow/CLI to emit coverage (separate PR); changing the adapter's strip
behavior; any structure/relation facts; scope *enforcement* (coverage declares, it does not gate).

---

## PR-5 — Refresh ≡ rebuild law (test-first; law before optimizer)

**Objective:** pin the **refresh ≡ rebuild** invariant as an enforced test *before* any incremental
frame path exists, so a future optimizer cannot ship a faster-but-divergent refresh. This is an
invariant, not a feature.

**Claims unlocked:** none (it is a guard). **Refused:** any incremental path that trades determinism
for speed.

### Resolved design decisions

1. **No incremental path is built here.** There is no refresh function today; PR-5 does not add one.
   It lands (a) the law in doctrine and (b) a reference test the future refresh must pass.
2. **The reference is rebuild-determinism.** The enforceable content today: building a frame twice
   from the same input is byte-identical (`test_same_repo_map_produces_identical_frame_digest` already
   asserts this). PR-5 adds a **named law test** `test_refresh_equals_rebuild_reference` that asserts
   the from-scratch build is the canonical reference, and documents that any `refresh_frame(...)`
   added later must assert byte-equality against `create_hierarchical_frame(...)` on the same tree or
   it does not ship.
3. **Covers the v3 blocks.** The reference test builds frames with and without provenance/coverage
   (post-PR-4) so the law covers the additive blocks, not just the v2 core. If PR-4 has not merged
   when PR-5 lands, cover the v2 core and note the coverage-block extension as a one-line follow-up.

### Files

Edit `tests/test_code_vault_hierarchy.py` (the named reference test); `docs/CODE_VAULT_HIERARCHY.md`
(the refresh≡rebuild law paragraph — already named in the vision set's roadmap/glossary; make it
concrete here); gap-map row (`Frame provenance + refresh ≡ rebuild law` → law pinned, no incremental
path yet). No production code change.

### Tests first

`test_refresh_equals_rebuild_reference`: two from-scratch builds byte-equal (with and without the v3
blocks); a docstring/comment naming the contract for any future `refresh_frame`.

### Out of scope

Building an incremental/caching refresh path (that is the PR that must *pass* this law, authored only
when a measured need exists); any performance work (PR-6 owns linter perf).

---

## PR-6 — Index the linter's containment scan (G1b; deferrable)

**Objective:** replace the geometric linter's per-symbol linear scans with a pre-built digest→node
index, so package-scale linting is honest at 10k nodes. R-parity: **identical findings** before and
after. Closes the gap-map row *"package-scale lint honesty at 10k nodes."*

**Claims unlocked:** honest 10k-node bench path. **Refused:** none (behavior is unchanged; only
complexity improves).

**Deferrable:** the quadratic scan only bites past ~10k nodes and no bench above 1k is claimed today.
This must land **before** any 10k-node bench result is published — that ordering is the constraint,
not its wave position.

### Resolved design decisions

1. **Index, don't restructure.** Build `files_by_layout_digest = {f.layout_digest: f for f in
   file_nodes}` once; replace the inner `for file_node in file_nodes` parent lookup with an O(1)
   `.get(symbol.parent_layout_digest)`. Do the same for `_module_sphere_for_file` (index file nodes
   by `layout_id` once instead of re-scanning `frame.nodes` per call).
2. **Findings must be byte-identical.** The linter sorts findings before digesting
   (`findings.sort(...)`), so ordering is already stable; the index changes *lookup*, not *result*.
   Prove it: a test builds a fixture frame, runs the linter before and after the change, asserts the
   `report_digest` is unchanged (author records the pre-change digest as the pin).
3. **No new finding kinds, no threshold changes.** Pure internal refactor of the scan.

### Files

Edit `code_vault/reports/linter.py` (the two indexed lookups); edit
`tests/test_code_vault_linter.py` (parity pin + a scaling smoke test on a synthetic multi-hundred-node
frame to show the lookup no longer scans linearly — assert findings identical, not timing); gap-map
row update. No schema, CLI, or doc-surface change beyond the gap-map row.

### Tests first

Parity: `report_digest` on a fixture frame is identical pre/post (pin the value); a many-node
synthetic frame lints to the same findings as a naive reference; existing linter tests stay green.

### Out of scope

The bench harness / 10k-node runs (separate; this only makes them honest); any change to what the
linter detects; spatial geometry beyond the digest index.

---

## Shared acceptance battery (all three PRs)

```bash
uv run pytest <the PR's named test slice> -q
uv run builder-platform audit-docs
uv run pytest tests/test_docs_truth_enforcement.py -q
bash scripts/ci.sh --receipt .builder/artifacts/gate-battery-receipt.json   # AFTER the last commit
```

PR bodies report actual command output, follow conventional-commit format, bind the receipt
`head_sha` to the pushed head, and state: RECORDED_ONLY, no matrix flip, no promotion, rollback =
revert + delete emitted JSON.

---

## What comes after wave 2

**G2 / PR-7 — StructuralField v1 via Python extractor v1** (the first R+D field: real structural
facts, invariance fixtures) is authored as its own order once wave 2 lands, against the merged
StructuralField schema and ExtractorManifest. It is the payoff of the climb; it does not depend on
PR-4/5/6 mechanically but follows them in gate order (G1b honesty before G2 structure).

---

## Related

- [`CODE_VAULT_EXECUTION_MAP.md`](CODE_VAULT_EXECUTION_MAP.md) — wave structure, invariants, protocol
- [`CODE_VAULT_G1_WAVE_BRIEFS.md`](CODE_VAULT_G1_WAVE_BRIEFS.md) — wave-1 orders (landed)
- [`../CODE_VAULT_ROADMAP.md`](../CODE_VAULT_ROADMAP.md) — gate G1b these PRs complete
- [`../CODE_VAULT_PROOF_PROGRAM.md`](../CODE_VAULT_PROOF_PROGRAM.md) — R evidence each PR files
