# CodeVault Tier-1 encoder RFC

Status: **Accepted design record; largely shipped** (F1 content-identity enrichment on main).
Provisional scale `0.1` was **refuted** by the dominance audit; measurement fixed
`TIER1_ENRICHMENT_SCALE = 0.001`. Remaining open questions are marked below.

This file remains the historical RFC and measurement narrative (Axiom Zero exemplar). For the full
vision set and path beyond F1, see
[`../CODE_VAULT_VISION_AND_CAPABILITY_LADDER.md`](../CODE_VAULT_VISION_AND_CAPABILITY_LADDER.md) and
[`CODE_VAULT_MASTER_PLAN.md`](CODE_VAULT_MASTER_PLAN.md).

---

*Original RFC framing (retained for history):* design-only proposal of doctrine amendment and plan.
The paragraphs below describe the design as proposed; resolution notes in later sections record what
measurement did.

## Purpose

CodeVault today is a **Tier-0** substrate: every geometric coordinate derives strictly from stable
layout identity (`docs/CODE_VAULT.md`), and the determinism demo pins that with the proof
`content_edit_changes_digest_not_center` (`builder_ii/code_vault_demo_loop.py`,
`tests/test_code_vault_hierarchy.py::test_content_edit_changes_digest_not_center`). The only
content-derived value anywhere in the frame is the per-node `content_digest`.

Tier-1 adds a **declared, bounded, content-derived enrichment block** to the CGA lift so that
*content identity* — not just layout identity — becomes geometrically visible. The concrete recall
capability this buys is exact clone/near-duplicate structure: two symbols with identical content at
different layout positions become geometrically relatable, and an edited symbol becomes
geometrically distinguishable from its previous self, while all positional geometry stays
layout-stable.

Tier-1 is **not** semantic embedding. Model embeddings, learned encoders, vector-database
similarity, and tokenizer-dependent features all remain refused (see "What stays refused").

## The doctrine amendment (amendment-FIRST)

Per the adversarial critique on file (`planning/evidence/critique-doctrine.json`), the amendment
must land **before** any encoder code, and it must re-scope what the determinism demo proves rather
than let the existing pinned proof silently narrow.

`docs/CODE_VAULT.md` currently states:

> coordinates derive strictly from **stable layout identity** — never from source content, sibling
> count, insertion order, model embeddings, or global graph state.

Amended doctrine:

> **Positional geometry** (centers, containment spheres, interface planes, call-edge rotors — the
> scalar, grade-1, and grade-2 subspaces) derives strictly from **stable layout identity** — never
> from source content, sibling count, insertion order, model embeddings, or global graph state.
> **Declared enrichment geometry** (the grade-3 Tier-1 block) derives deterministically from
> content identity alone — the same `content_digest` always produces the same enrichment, and it is
> version-declared, scale-bounded, and validator-enforced. No slot is ever derived from model
> output.

This is the same principled line the frame already draws for `content_digest`: content-derived
values are allowed when they are deterministic, content-addressed, declared, and validated — never
when they are learned, approximate, or hidden.

## Slot layout and collision analysis (verified against the code)

Cl(4,1) multivectors have 32 components in grade blocks (see
`builder_ii/code_vault/geometry/cl41.py`): scalar `[0]`, grade-1 `[1..5]`, grade-2 `[6..15]`,
grade-3 `[16..25]`, grade-4 `[26..30]`, grade-5 `[31]`.

| Subspace | Current owner | Tier-1 use |
| --- | --- | --- |
| grade-1 `[1..5]` | Fully consumed by the conformal point embedding: `embed_point` writes `coords` into `[1..4)` and the null-cone split into `e4`/`e5`; `null_project_point` re-derives from the Euclidean part; IPNS spheres/planes also live here | **Forbidden.** Any content contribution breaks the null-cone invariant and every containment/crossing predicate |
| scalar + grade-2 `[0, 6..15]` | Rotor subspace: `embed_rotor_candidate` (call-edge rotors, `rotor_call_edge_contract`), `rotor_similarity` | **Forbidden.** Content components here would masquerade as call-edge structure |
| grade-3 `[16..25]` (10 slots) | Unused (zero) in every current builder | **The Tier-1 enrichment block** |
| grade-4 `[26..30]`, grade-5 `[31]` | Unused | Reserved; stay zero in Tier-1 (future tiers must amend doctrine again) |

**Unit-scale dominance:** recall scoring is the exact diagonal inner product over the full
32-vector (`score_inner_product`, `CGA_INNER_METRIC`). An unbounded enrichment block would dominate
layout separation. Tier-1 therefore declares a hard bound: the enrichment block's L2 norm is
exactly `TIER1_ENRICHMENT_SCALE` (proposed: `0.1`, roughly an order of magnitude below unit layout
scale — final value is a bench-lane output, not a guess in this RFC). The geometric linter gains a
fail-closed check that every node's grade-3 block norm is either `0` (Tier-0 node) or exactly the
declared scale.

## The encoder (deterministic, content-addressed, no models)

`tier1_enrichment(content_digest) -> 10 floats`:

1. Expand the sha256 `content_digest` with a fixed, versioned expansion (`sha256(digest || i)` for
   `i in 0..9`, taking each result's first 8 bytes as a big-endian integer).
2. Map each integer uniformly into `[-1, 1]`, then normalize the 10-vector to L2 norm
   `TIER1_ENRICHMENT_SCALE`.
3. Serialize into the artifact as fixed-9 decimal strings (same byte-stable convention as
   `center_xyz`).

Properties, stated honestly:

- **Same content → identical enrichment** anywhere in any repo (content identity is geometric).
- **Different content → uncorrelated enrichment** (hash expansion): edits are *visible*, but edit
  *distance* is not graded — this is content-identity geometry, **not** similarity geometry.
  Graded similarity (e.g. deterministic token statistics) would drag in tokenizer doctrine and
  language dependence; it is explicitly out of scope and would require its own RFC ("Tier-2",
  SPECULATIVE).
- Deterministic, replayable, dependency-free, and identical across Python and Rust backends.

## Determinism demo re-scope (the critique's requirement)

The demo's pinned proof set changes in the **same PR as the doctrine amendment**, before any
encoder exists — center stability AND declared enrichment instability:

| Proof | Status | Claim |
| --- | --- | --- |
| `content_edit_changes_digest_not_center` | kept, meaning narrowed and documented | edits never move positional geometry |
| `content_edit_changes_enrichment` | new | same layout, edited content → grade-3 block differs (declared instability) |
| `content_identity_enrichment_stable` | new | identical content at two different layout positions → identical enrichment block, different centers |
| `enrichment_scale_bounded` | new | every non-zero grade-3 block has exactly the declared norm |

The demo evidence bundle and `validate-demo` pins are re-derived alongside; until the encoder PR
lands, the two new content proofs assert the Tier-0 degenerate form (all enrichment blocks zero),
so the proof *vocabulary* changes first and the *values* flip only when the encoder ships.

## Schema and the post-v0.1.0 versioning policy

`HIERARCHICAL_FRAME_SCHEMA_VERSION` bumps `1 → 2` with one **optional** per-node field:

```json
"content_enrichment": {
  "tier": 1,
  "encoder": "digest-expand-v1",
  "scale": "0.100000000",
  "components": ["-0.031415927", "..."]
}
```

Per `CHANGELOG.md`, post-`v0.1.0` schema changes require an explicit versioning policy. This RFC
proposes the platform's first one, scoped to additive-optional changes:

- an additive-optional field = **minor schema bump**; validators for version `N` accept `N` and
  `N-1` for one release cycle; absence of the field means Tier-0 semantics;
- readers never infer tier from raw vector components — only from the declared field;
- removal or meaning-change of an existing field remains a **major** bump requiring its own
  migration plan (no silent hard cuts anymore).

## Blast radius (enumerated)

`builder_ii/code_vault/hierarchy.py` (schema + builder), geometry `builders.py` (grade-3 injection
into point entities), `predicates.py` (no change — scoring already covers all 32 components),
recall backends (pure-NumPy reference AND the Rust adapter in `builder_ii_validation_rs` — the
existing byte-parity gate extends to enrichment), lint (`scale` check), context projection
(surfaces `tier`), TUI (renders tier), `code_vault_demo_loop.py` + `validate-demo`,
`docs/CODE_VAULT.md` + `CODE_VAULT_GEOMETRIC_ONTOLOGY.md` + `CODE_VAULT_STAGED_ACCEPTANCE.md`
(new rows), `docs/ARTIFACT_INDEX.md` (bench report kind), and the pinned tests
(`test_code_vault_hierarchy.py`, `test_code_vault_cli.py`, Rust parity tests).

*Clarification (2026-07-10):* the Rust surface named above is the **artifact-validation**
accelerator (`builder_ii_validation_rs`), whose byte-parity gate covers enrichment validation. The
optional Rust **recall** path is the separate `core_rs` scoring backend behind explicit selection.
Neither is a language extractor — see the category-error table in
[`../CODE_VAULT_LANGUAGE_SUBSTRATE.md`](../CODE_VAULT_LANGUAGE_SUBSTRATE.md).

## Bench lane (`builder-code-vault bench`)

New Tier-1-CLI artifact kind `builder_ii.code_vault_bench_report` (+ `validate-bench`), run over a
deterministic fixture corpus with planted clones:

1. **Determinism:** two runs produce byte-identical frames, recall reports, and bench reports.
2. **Clone detection:** precision/recall of enrichment-block equality against the planted ground
   truth (target: exact — this is identity, not similarity; anything below 100% is a defect).
3. **Dominance audit:** max enrichment contribution to any pairwise score / min layout separation
   in the corpus; the gate fails if enrichment can reorder any layout-only ranking beyond the
   declared tolerance. This is the empirical input that fixes `TIER1_ENRICHMENT_SCALE`.
4. **Scale:** wall-clock and memory at 1k/5k/10k nodes. Prerequisite: the geometric linter's
   pairwise collision scan is O(N²) today and must move to a spatial index (sorted center buckets)
   before 10k-node benches are honest.

## Severability (operator constraint, 2026-07-08)

CodeVault may be excised into a paid tier while the rest of builder-II is open-sourced. Tier-1
work therefore adds **no new imports from core lanes into `builder_ii/code_vault/`**; the encoder,
bench lane, and enrichment live entirely inside the package (plus its existing CLI/TUI seams), so
the package stays removable without touching the governed core.

## What stays refused

Model embeddings and learned encoders; vector-database similarity; tokenizer/language-dependent
features; any content contribution to positional geometry; autonomous writes of any kind. The
matrix rows and staged-acceptance states do not move with this RFC — promotion happens only
through the eight gates with bench evidence, operator-applied as always.

## Implementation plan (ordered PRs, each fully gated)

1. **Doctrine amendment + demo re-scope** — amend `CODE_VAULT.md`, re-scope the proof set
   (degenerate Tier-0 values), update `validate-demo` pins. No encoder.
2. **Collision-scan spatial index + bench harness skeleton** — the O(N²) fix and the bench report
   kind with determinism + scale measurements only.
3. **Schema v2 + encoder + NumPy reference** — `content_enrichment`, lint scale check, demo proofs
   flip to live values; versioning policy lands in validators (accept v1 + v2).
4. **Rust parity + full bench lane** — extend the PyO3 validator and the byte-parity gate; run the
   dominance audit; fix `TIER1_ENRICHMENT_SCALE` from its output.
5. **Findings + projection** — `content_clone_candidate` advisory finding kind and context-pack
   surfacing; staged-acceptance table rows for all of the above.
   **SHIPPED (PR-5, 2026-07-08):** geometric linter emits `content_clone_candidate` for shared
   `content_digest`s; context projection surfaces bounded `content_identity` (tier/peers) for the
   requested artifact.

## Open questions for the operator

1. Accept `0.1` as the provisional enrichment scale pending the bench dominance audit?
   **RESOLVED (PR-4, 2026-07-08): the audit REFUTED 0.1.** Measured on the bench corpus, the
   smallest positional gap the float32 scoring arithmetic can resolve (noise-floor-adjusted:
   gaps under `N_COMPONENTS * eps32 * max|score|` are measurement ties) is ~7.6e-6, while a 0.1
   scale contributes up to scale² ≈ 9.6e-3 per pair. The audit fixed
   `TIER1_ENRICHMENT_SCALE = 0.001` (max contribution ≤ 1.2e-6: ~6–8× under the bound at both
   bench sizes, and an order of magnitude above float32 score quantization so enrichment stays
   score-visible). Clone detection is exact (precision = recall = 1.0) at both sizes. This is
   the RFC's process working as designed: provisional value proposed, measurement refuted it,
   measurement fixed it.
2. Should a Tier-2 (graded, still-deterministic similarity) RFC be drafted after Tier-1 ships, or
   is content-identity geometry the intended end state for the paid tier? (Open; operator
   deferred at PR-1 time.)
3. Bench fixture corpus: synthetic-only, or additionally a pinned snapshot of builder-II itself?
   (PR-4 shipped synthetic-with-planted-clones; a pinned self-snapshot remains a PR-5+ option.)
