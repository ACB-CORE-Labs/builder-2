# CodeVault Execution Map — First Slice (G1 → G1b → G2)

**Status:** Official per-PR execution truth for the master plan's first slice.  
**Kind:** Design / execution map (RECORDED_ONLY). Implements no capability by existing.

The [master plan](CODE_VAULT_MASTER_PLAN.md) fixes the gate order; this map fixes the **PR
decomposition** of the first slice — what each PR touches, what it proves, what it may claim, and
what it must refuse. **No chronos:** waves are dependency groupings, not sprints. Work orders for
dispatchable PRs live in [`CODE_VAULT_G1_WAVE_BRIEFS.md`](CODE_VAULT_G1_WAVE_BRIEFS.md).

Scope of this map: **G1, G1b, G2**. Gates G3–G7 stay at master-plan resolution because each is
blocked on an upstream decision recorded in the [deferred-decision registry](#deferred-decision-registry)
— specifying their PRs now would be planning theater, which Axiom Zero forbids.

---

## Code-clock starting line (measured, not assumed)

The facts below were read from the modules, not inferred from docs. They are the honest baseline
every wave-1 PR builds on.

| Surface | Fact (code clock) |
|---|---|
| `code_vault/symbol_extractor.py` | Top-level `FunctionDef`/`AsyncFunctionDef`/`ClassDef` only; async collapsed to kind `function`; bounds `MAX_SYMBOLS_PER_FILE = 64`, `MAX_SYMBOL_CONTENT_BYTES = 8192`; syntax errors → `[]`. Fabricates nothing — but declares nothing (no manifest, no version, no unsupported list). |
| `code_vault/hierarchy.py` | `HIERARCHICAL_FRAME_SCHEMA_VERSION = 2`; `SUPPORTED_FRAME_SCHEMA_VERSIONS = (1, 2)`; the additive-optional versioning policy is encoded at the constant (Tier-1 RFC). The frame carries **no repository-state provenance** (no commit id, dirty flag, or scope header anywhere in the build path). |
| `repo_map.py` | Emits `truncated`, `file_count`, `ignored_directories`, default `max_files = 500` — truncation honesty exists at repo-map level but does **not** propagate onto the frame. |
| `code_vault/reports/linter.py` | Containment scan is quadratic (per-symbol linear scans over file nodes); clone scan is linear (digest grouping). Spatial index named as bench prerequisite in the Tier-1 RFC; not shipped. |
| Registration seams | New artifact kind = `*_KIND` string + `validate_*` + registration in `artifact_index_records.py` + row in `docs/ARTIFACT_INDEX.md`. New subcommand = Typer command in `cli/code_vault_cli.py` + entry in the `command_authority.py` subcommand enumeration + `docs/COMMAND_SURFACE_AUDIT.md`. Tests pin both. |
| Severability precedent | `code_vault_receipt_bridge.py` lives **outside** the package so the vault never imports verification lanes. Any helper that touches repo state (e.g. git metadata) follows this precedent. |

---

## Wave structure

```text
Wave 1 (parallel, independent)          Wave 2 (after wave 1)            Wave 3 (after wave 2)
  PR-1 ExtractorManifest                  PR-4 scope/coverage on frame     PR-7 StructuralField v1
  PR-2 StructuralField schema stub        PR-5 refresh ≡ rebuild guard          via Python extractor
  PR-3 frame provenance binding           PR-6 linter spatial index             (first R+D field)
                                               (deferrable — see below)
```

Wave-1 PRs are mutually independent and safe to implement concurrently in **separate worktrees**.
Work orders for wave 2 and wave 3 are authored only after wave 1 lands — schemas must settle before
they are consumed (measure, then amend; never specify against an unlanded surface).

**Wave 1 landed 2026-07-11** (PRs #78 ExtractorManifest, #79 frame provenance, #77 StructuralField
stub; plus #80, a ruff-conformance hotfix for a trailing-newline defect an amendment commit left on
main). Schemas are now settled, so wave-2 work orders are authored:
[`CODE_VAULT_G1B_WAVE_BRIEFS.md`](CODE_VAULT_G1B_WAVE_BRIEFS.md) (PR-4/5/6). Two review findings fed
back into this map: standing invariant #1 was amended to an explicit import allowlist (below), and
the process note under [work-order protocol](#work-order-protocol) now requires the battery to run
**after** the last commit.

**Wave 2 (G1b) landed 2026-07-11** (PRs #82 frame coverage honesty, #83 linter index, #84
refresh≡rebuild law; plus #85, a status-board render fix for a host-dependent test the cross-vendor
cold review of #84 surfaced — the flaky test was pre-existing on main, not a wave-2 regression).
G1b's schemas are settled, so **wave-3 (G2) work orders are authored:**
[`CODE_VAULT_G2_WAVE_BRIEFS.md`](CODE_VAULT_G2_WAVE_BRIEFS.md). On contact with the settled schemas,
**PR-7 decomposes into a G2 wave** (PR-7a: emission pipeline + first fact kind, R+D end-to-end →
PR-7b/7c: remaining fact kinds) — one order cannot carry a new extraction lane, a manifest builder,
an emission path, a CLI surface, and six fact kinds each needing labeled invariance + discrimination
fixtures. This is the decomposability law, applied exactly as G1 split into wave 1 / wave 2.

---

## Per-PR map

| # | Gate | Scope | Proof | Claims unlocked | Refused claims |
|---|---|---|---|---|---|
| 1 | G1 | `ExtractorManifest` artifact + the Python extractor v0 declares one | R | "extractors are declared" | any structure intelligence |
| 2 | G1 | `StructuralField` schema stub (validator only; no fact emission path) | R | "the F2 schema exists" | structural correspondence vocabulary |
| 3 | G1b | Frame provenance block (additive-optional, caller-supplied; schema v2→v3) | R | "a frame can bind to a repo state" | lineage / change intelligence (F4) |
| 4 | G1b | Truncation/coverage propagated from repo_map onto the frame; scope modes | R | honest scoped indexing | full-monorepo coverage without flags |
| 5 | G1b | Refresh ≡ rebuild byte-identity guard (test-first; law before optimization) | R | — (an invariant, not a feature) | any incremental path that trades determinism |
| 6 | G1b | Linter containment scan → spatial index (identical findings pre/post) | R | honest 10k-node bench path | — |
| 7 | G2 | StructuralField v1 fed by Python extractor v1 (nested, async, signatures, decorators, ownership, imports-as-facts) + invariance fixtures | R+D | structural correspondence **candidates** (hypothesis) | multi-language structure; any utility language (U) |
| 7d | G2 | **Scope-correct subject walk**: closures + definitions inside `if`/`try`/`with`/`for`/`while`/`match` guards. Extractor v1.1.0 → v1.2.0 | R (regression: zero of 10,339 pre-existing facts moved) + D | "nested definitions" (the G2 bullet) | any new fact kind; motif (G2m) |

PR-6 is **deferrable within G1b**: the quadratic scan only bites past ~10k nodes, and no bench
above 1k nodes is claimed today. It must land before any 10k-node bench result is published — that
ordering is the constraint, not its position in the wave.

PR-7 was **decomposed into a G2 wave** in [`CODE_VAULT_G2_WAVE_BRIEFS.md`](CODE_VAULT_G2_WAVE_BRIEFS.md).
**The G2 wave is now LANDED:** PR-7a (#87) stood up the whole emission lane (structural extractor →
structural manifest → field → CLI → validator), proven end-to-end with the `signature` fact kind under
a labeled R+D fixture suite; PR-7b (#90) added `nesting`, `ownership`, `decorator`, and `import_fact`,
each under its own labeled invariance + discrimination suite, and re-grounded the per-file bound to
count **subjects** rather than facts (the PR-7a loop broke on `len(facts)`, which silently walked 22 of
64 subjects once subjects became multi-fact). PR-7c **registers `motif` as a deferred decision** rather
than specify against an unformed idea: it is blocked by the F2 schema's per-subject `subject_layout_id`
binding and by the operator-deferred Tier-2 similarity RFC (see that section for the leading candidate
and what would unblock it).

**Five of the six registered fact kinds emit; the sixth is honestly refused** (`motif_fact` stays in
`STRUCTURAL_UNSUPPORTED_CONSTRUCTS`, a declared refusal the manifest carries, now owned by Gate G2m).
PR-7d (#100) closed the walk to be scope-correct — closures and definitions inside `if`/`try`/`with`/
`for`/`while`/`match` blocks are now subjects, using CPython's own `__qualname__` scheme — which
closed G2's last `PARTIAL` bullet. Claims stay exactly where G2 allows: structural correspondence
**candidates** (hypothesis, R+D). No completion-matrix flip, no promotion, no new command (the
synthesized-count pin stays 102). **That condition now holds: Gate G2 is OPEN** (operator decision,
2026-07-11 — see [`../CODE_VAULT_GATE_STATE.md`](../CODE_VAULT_GATE_STATE.md) for the per-bullet
evidence).

Gate G1 opens only when **all** of its bullets in the [roadmap](../CODE_VAULT_ROADMAP.md) hold
(manifest + stub + provenance skeleton + fail-closed posture) — landing PR-1 alone does not open
G1, and no doc may say otherwise. **That condition now holds: Gate G1 is OPEN** (operator decision,
2026-07-11 — see [`../CODE_VAULT_GATE_STATE.md`](../CODE_VAULT_GATE_STATE.md) for the per-bullet
evidence and every other gate's current, honestly-scored state).

---

## Standing invariants (every PR in this slice inherits)

1. **Severability** — the package stays excisable with a *named, small* vendoring surface, not zero
   imports. **Allowed inbound imports:** `builder_ii.repo_map` (existing adapter seam) and
   `builder_ii.governance_standard` (the one canonical governance-block builder/validator — a leaf
   utility, not an authority lane). *Amended 2026-07-11: two wave-1 implementers independently
   imported `governance_standard` rather than hand-roll a governance block; hand-rolling would be
   its own drift vector, and the module is a pure formatter that vendors trivially on excision —
   so it is allowed, not forbidden.* **Forbidden:** imports from authority/execution lanes
   (verification execution, HITL, model/command execution, patch apply, Goose/deepagents runtime).
   Helpers that *read repo state* still live outside the package (`code_vault_provenance.py` /
   receipt-bridge precedent). Adding a new inbound import is a doctrine amendment, not a convenience.
2. **Governance block** — every new artifact carries the standard block: all execution surfaces
   `DISABLED`, `artifact_is_authority: false`, a named `capability_state`. Promotion state stays
   `artifact_only` / `validation_only`; no completion-matrix flip.
3. **Claim law** ([proof program](../CODE_VAULT_PROOF_PROGRAM.md)) — R alone → artifact may exist;
   R+D → `*_candidate` vocabulary; U → product language. Nothing in this slice reaches U.
4. **Anti-transcription** — declarations derive from the code constants they describe (import the
   constant, never re-type it). A manifest that transcribes is a manifest that drifts.
5. **Fail closed** — unknown constructs, unknown enum states, and tampered digests are refusals,
   never defaults.
6. **TDD** — the work order's test list is written and failing before implementation; every new
   module gets `tests/test_<module>.py` mirroring 1:1.
7. **Docs in the same PR** — staged-acceptance row, gap-map delta update, and `ARTIFACT_INDEX` /
   `COMMAND_SURFACE_AUDIT` rows land with the code that makes them true; `audit-docs` stays green.
8. **Frame byte-stability** — no wave-1 PR may alter the bytes of a frame built with today's
   inputs. New fields are additive-optional and absent by default (the schema-versioning policy at
   `hierarchy.py`).

---

## Work-order protocol

- Work orders are **implementer-agnostic**: they resolve every design decision so the implementer
  (human or dispatched agent) inherits zero ambiguity and burns no reasoning on architecture.
- One PR per work order; one branch per PR from `main`; concurrent work in separate worktrees.
- Each work order names its acceptance commands. The PR body reports their output; `bash
  scripts/ci.sh` is the final word before review.
- A work order that survives contact with the code imperfectly is **amended in the same PR** that
  discovers the mismatch — the map records the amendment, not a silent divergence.
- **Gate evidence binds to the final tree.** Run `bash scripts/ci.sh --receipt` **after the last
  commit** (amendments included) and confirm the receipt's `head_sha_before == head_sha_after ==`
  the pushed head. A receipt captured before a later fix is not evidence for what merges — wave 1's
  #80 hotfix exists because an amendment commit landed a ruff defect behind a stale "gates passed"
  receipt.
- **Re-verify after merge.** After a PR merges, re-sync both remotes and confirm `main` is green on
  a fresh checkout — a mirror silently fell behind and `main` was briefly red in wave 1 before this
  step was added.

---

## Deferred-decision registry (blocks G3+)

| Decision | Blocks | Owner / mechanism | State |
|---|---|---|---|
| Parser strategy (native AST vs tree-sitter vs SCIP/LSIF vs hybrid) | G3 second-language extractor | HITL decision note scored on the [language substrate](../CODE_VAULT_LANGUAGE_SUBSTRATE.md) axes | **Decided (ADR-0006)** — hybrid: pinned in-process grammar for G3 skeleton; caller-supplied digest-bound SCIP/LSIF for G4. Cites G2 lessons (semantics fidelity, parser_version-in-digest, residue/declared blindness) and ADR-0005 non-execution. |
| U task registry + rubric design | G5 | HITL-approved RECORDED_ONLY design artifact (F6 blueprint law: unapproved rubric = unopened gate) | **Instrument landed (Track B)** — registry + eval + sealed held-out + baseline arm; HITL approval still **pending** before scored CodeVault arms |
| Tier-2 graded-similarity RFC | any similarity geometry | Operator-deferred at Tier-1 PR-1 time (RFC open question 2) | Deferred |
| Bench self-snapshot corpus (pinned builder-II snapshot) | richer D evidence | Tier-1 RFC open question 3 | **In use** — default U registry binds `self_snapshot` / builder-II |
| Frame `dirty`-flag derivation (requires git status semantics) | provenance depth | Amendment to PR-3's helper after measurement; v1 declares `dirty` unknown rather than guessing | Open |
| `changed` scope mode (+ the frame/StructuralField scope-vocabulary divergence) | was **Gate G1b**'s one UNMET bullet | **RESOLVED by dissolving the premise.** The deferral assumed `changed` is a *capability* (compute a diff → needs repo state → violates standing invariant #1). It is a **declaration**: the caller diffs and hands the paths in; CodeVault records that it was told, and binds the claim to a `base_commit_id` so it is checkable. Same grammar as `provenance` (PR-3) and `coverage` (PR-4) — caller-supplied, additive, never derived. Severability cost: **zero** (`code_vault/scope.py` imports only `typing` + one in-package leaf, pinned by a parsed-import test). The vocabulary divergence is closed by construction: one `SCOPE_MODES` in one module, imported by both artifacts, neither declaring its own — so `package`-on-the-frame answered itself | **Closed (PR-8)** — see [`../CODE_VAULT_GATE_STATE.md`](../CODE_VAULT_GATE_STATE.md) |
| Declared-blindness vocabulary (body / type annotations / default values / decorator arguments) | Nothing today — but it bounds what F2 facts may ever be *claimed* to detect, so it is upstream of any F2 product language | Surfaced closing G2's interface-stable bullet. The facts are blind to four things no artifact states: **bodies** (deliberate — the source of refactor-survival, but it means an unchanged fact set is *not* a claim that code is unchanged), **type annotations**, **default values**, **decorator arguments**. All four are now pinned by labeled tests and declared in `structural_extractor.py`'s docstring, but only in **prose** — `STRUCTURAL_UNSUPPORTED_CONSTRUCTS` names constructs, not blindnesses, so nothing machine-readable carries them into the manifest. Two questions: (1) should blindness be a declared, manifest-carried vocabulary alongside the invariance classes? (2) should `signature` capture annotations at all — **it is not free**: annotations are type *references*, so reading them makes `signature` sensitive to type renames, trading away part of the rename-invariance it currently declares | **Open (registered)** — pinned + declared in prose; not closed |

**Amendment, 2026-07-11 (operator decision) — motif split out of G2 into Gate G2m.** Not entered as a
row above because it does not block G3+ (unlike every row above, which does). PR-7c's review found
motif does not fit the F2 schema's per-subject `subject_layout_id` binding as specified — a property
of a *set* of subjects, not one. Rather than leave that mismatch sitting inside G2's bullet list
forever (a `DEFERRED` bullet holds its gate closed permanently per the [gate-state
ledger](../CODE_VAULT_GATE_STATE.md)'s own law), the roadmap's G2 definition is amended: motif moves
to a new, explicitly unordered **Gate G2m** ([`../CODE_VAULT_ROADMAP.md`](../CODE_VAULT_ROADMAP.md) §
Gate G2m). This is Axiom Zero's distinction in practice — a reasoned, recorded scope change is not
the silent narrowing the axiom forbids. G2's other two open bullets (closures under "nested
definitions"; the interface-stable-change fixture) are unaffected and do not depend on this amendment.

---

## Verification matrix

| PR | Verification commands (minimum; `bash scripts/ci.sh` before review) |
|---|---|
| 1 | `uv run pytest tests/test_code_vault_extractor_manifest.py tests/test_code_vault_cli.py tests/test_command_authority.py tests/test_command_surface_audit.py tests/test_artifact_index_records.py -q` + `uv run builder-platform audit-docs` |
| 2 | `uv run pytest tests/test_code_vault_structural_field.py tests/test_code_vault_cli.py tests/test_command_authority.py tests/test_artifact_index_records.py -q` + `uv run builder-platform audit-docs` |
| 3 | `uv run pytest tests/test_code_vault_hierarchy.py tests/test_code_vault_provenance.py tests/test_code_vault_demo_loop.py -q` + `uv run builder-platform audit-docs` |
| 4 | `uv run pytest tests/test_code_vault_hierarchy.py -q` + `uv run builder-platform audit-docs` (landed, #82) |
| 5 | `uv run pytest tests/test_code_vault_hierarchy.py -q` + `uv run builder-platform audit-docs` (landed, #84) |
| 6 | `uv run pytest tests/test_code_vault_linter.py -q` + `uv run builder-platform audit-docs` (landed, #83) |
| 7a | `uv run pytest tests/test_code_vault_structural_extractor.py tests/test_code_vault_structural_field.py tests/test_code_vault_extractor_manifest.py tests/test_code_vault_cli.py tests/test_command_authority.py tests/test_command_surface_audit.py tests/test_artifact_index_records.py -q` + `uv run builder-platform audit-docs` (landed, #87) |
| 7b | same suite as 7a (landed, #90). Frame byte-stability proven independently by comparing the default `frame_digest` on `main` vs the branch; the subject-cap semantics are mutation-proven (restoring the PR-7a `len(facts)` break walks 22 of 64 subjects) |
| 7c | **No code.** `motif` is registered as a deferred decision — see [`CODE_VAULT_G2_WAVE_BRIEFS.md`](CODE_VAULT_G2_WAVE_BRIEFS.md) § PR-7c. Verified by `uv run builder-platform audit-docs` + `uv run pytest tests/test_docs_truth_enforcement.py -q` |
| 7d | `uv run pytest tests/test_code_vault_structural_extractor.py tests/test_code_vault_structural_field.py tests/test_code_vault_extractor_manifest.py -q` + `uv run builder-platform audit-docs`. The load-bearing proof is the **regression**: the walk changed, so every fact the old walk emitted must come out byte-identical. Verified over the full `builder_ii/` tree (266 files) — **0 of 10,339 facts moved**, 79 gained. Mutation-proven three ways: dropping the `<locals>` marker fails the collision test; not walking scope-transparent blocks fails the guarded-def tests; not descending into function bodies fails the closure tests |
| 8 | `uv run pytest tests/test_code_vault_scope.py tests/test_code_vault_hierarchy.py tests/test_code_vault_structural_field.py -q` + `uv run builder-platform audit-docs`. The load-bearing proof is **byte-stability across two schema events** (field v1→v2, frame v3→v4): every pre-PR-8 digest re-derived on the parent commit and compared — **all identical**. The existing literal `_RECORDED_V2_FRAME_DIGEST` pin is an independent guard and did not move. Severability pinned by parsing `scope.py`'s actual import set |

---

## Related

- [`CODE_VAULT_G1_WAVE_BRIEFS.md`](CODE_VAULT_G1_WAVE_BRIEFS.md) — wave-1 work orders (PR-1/2/3, landed)
- [`CODE_VAULT_G1B_WAVE_BRIEFS.md`](CODE_VAULT_G1B_WAVE_BRIEFS.md) — wave-2 work orders (PR-4/5/6, landed)
- [`CODE_VAULT_G2_WAVE_BRIEFS.md`](CODE_VAULT_G2_WAVE_BRIEFS.md) — wave-3 / G2 work orders (PR-7a/7b/7c)
- [`CODE_VAULT_MASTER_PLAN.md`](CODE_VAULT_MASTER_PLAN.md) — gate law and path to fruition
- [`../CODE_VAULT_ROADMAP.md`](../CODE_VAULT_ROADMAP.md) — gate definitions G0…G7
- [`../CODE_VAULT_LANGUAGE_SUBSTRATE.md`](../CODE_VAULT_LANGUAGE_SUBSTRATE.md) — Artifact IR sketches the stubs implement
- [`../CODE_VAULT_CURRENT_STATE_AND_GAP_MAP.md`](../CODE_VAULT_CURRENT_STATE_AND_GAP_MAP.md) — deltas these PRs close
- [`../CODE_VAULT_GATE_STATE.md`](../CODE_VAULT_GATE_STATE.md) — the gate-state ledger: which bullets hold, and which gates are therefore closed
- [`../adrs/ADR-0005-codevault-boundary-and-authority.md`](../adrs/ADR-0005-codevault-boundary-and-authority.md) — authority boundary every PR inherits
