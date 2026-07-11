# CodeVault G2 Wave Work Orders (PR-7a … PR-7c) — StructuralField v1 emission

**Status:** Dispatchable work orders for the [execution map](CODE_VAULT_EXECUTION_MAP.md)'s wave 3 (G2).
**Kind:** Design / work orders (RECORDED_ONLY). Implements no capability by existing.

G2 is the payoff of the climb: the **first field that carries real structural intelligence** — a
`StructuralField` whose `facts` are emitted by a Python structural extractor and are provable
**R+D** (representation + detection), so they may be named *structural correspondence **candidates***
(hypothesis vocabulary), never verified correspondence and never a utility (U) claim.

The execution map fixes PR-7 as the single G2 payoff. On contact with the settled schemas it is too
large for one order — a new extraction lane, a manifest builder, an emission path, a CLI surface, and
**six fact kinds each needing labeled invariance *and* discrimination fixtures** (the R+D proof).
Per the decomposability law it is authored as a **G2 wave**, exactly as G1 split into wave 1 / wave 2:
PR-7a proves the whole pipeline end-to-end with **one** fact kind; PR-7b/7c add the rest against the
then-settled pipeline. This is a map amendment, recorded in
[`CODE_VAULT_EXECUTION_MAP.md`](CODE_VAULT_EXECUTION_MAP.md) in the same PR that lands these orders.

> **Dispatch gate.** PR-7a does **not** dispatch until **wave 2 (G1b: PR-4, PR-5, PR-6) has fully
> landed on `main`** — the StructuralField binds to the frame and manifest whose byte-stability wave 2
> completes. **Wave 2 is fully landed** (PR-4 #82, PR-6 #83, PR-5 #84; plus the #85 status-board render
> fix), so **PR-7a is cleared to dispatch** once this plan PR merges. Author the PR-7b/7c detailed
> orders only after PR-7a lands (measure, then amend; never specify against an unbuilt pipeline).
>
> **Update (this amendment): PR-7a is LANDED** (#87, merged 2026-07-10; cold-reviewed by running —
> battery green, frame digest byte-identical to pre-PR main). The PR-7b order below is now the
> detailed, dispatchable one, authored against the landed pipeline per the gate above; **PR-7b has since
> LANDED** (the order below, with its implementation amendments recorded in-section). PR-7c stays a
> stub until its normalized form is decided or formally deferred.

---

## Code-clock starting line (measured on the settled schemas, not assumed)

> Snapshot taken when PR-7a was authored (pre-#87). PR-7a has since landed; the **PR-7b starting
> line** table inside the PR-7b order below re-measures the surfaces 7b builds on.

| Surface | Fact (read from the modules) |
|---|---|
| `code_vault/structural_field.py` | Schema v1 **settled** (#77): validator + `create_structural_field_stub` only, **no emission path**. Fact shape = `{subject_layout_id, fact_kind, normalized_value, language, invariance_class[]}`. `FACT_KINDS = {decorator, import_fact, motif, nesting, ownership, signature}`; `INVARIANCE_CLASSES = {comment, format, move, rename, reorder}`; `SCOPE_MODES = {paths, package, full}`. `field_digest` excludes itself; `compute_field_digest` uses the package `ensure_ascii=False` convention. `extractor_manifest_ref` must be a 64-char sha256. |
| `code_vault/symbol_extractor.py` | **Feeds the frame** (`extract_symbols_from_file` → `repo_map_adapter` → `create_hierarchical_frame`). Top-level func/class only; async collapsed to `function`; declares `EXTRACTOR_ID="python-ast-toplevel"`, v`0.1.0`, and lists `nested_definitions`/`async_function_distinction`/`decorators_as_facts`/`methods`/… as **unsupported**. Changing it changes frame bytes (invariant #8) — it is **frozen** for G2. |
| `code_vault/extractor_manifest.py` | Schema v1 settled (#78). Generic enough to declare a v1 structural extractor **without a schema bump**: `coverage="structure"` is already a registered `READINESS_COVERAGE_STATES` value ("StructuralField R+D for declared construct set"). `build_extractor_manifest("python")` is bound to the v0 extractor's constants; it stays byte-identical. Manifest imports its constants from the extractor module (anti-transcription). |
| `hierarchy.py` | Frame symbol nodes use `layout_id = f"path:{normalize_layout_id(path)}#{kind}:{name}"` (`_symbol_layout_id`). Top-level facts can bind to real frame nodes by reproducing this scheme; nested/method subjects extend it (StructuralField is a superset of the frame, not a subset). |
| CLI / registration | `builder-code-vault validate-structural-field` exists and is registered in `command_authority.py` (a real command record) + `artifact_index_records.py` (validator map). **No emit command.** `_SYNTHESIZED_PARENTS` count pin = **101** (`tests/test_command_authority.py:877`); adding one emit command makes it **102** — flip it via the generator `uv run python -m builder_ii.command_authority`, never by hand. |
| Proof bar (`CODE_VAULT_PROOF_PROGRAM.md`) | **D = detection validity:** labeled fixtures, invariance / false-positive audits, a **declared false-positive mode**. Guard: "synthetic beauty without labels." R+D → `*_candidate` / hypothesis vocabulary; **U stays closed** (no product/utility language anywhere in G2). |

---

## Wave structure

```text
Wave 3 (G2) — after wave 2 (G1b) fully lands
  PR-7a  Structural emission pipeline + FIRST fact kind (signature), R+D end-to-end  [LANDED #87]
  PR-7b  fact kinds: nesting, ownership, decorator, import_fact (each R+D)   [LANDED — order below]
  PR-7c  fact kind: motif — OR formally defer motif as a registered decision  [authored after 7b]
```

PR-7a is the load-bearing de-risk: it lands the **entire** lane (extractor → manifest → field →
CLI → validator → fixtures) and proves it with one fully-specified fact kind. PR-7b/7c then add fact
kinds against a settled pipeline and are specified only after 7a lands.

---

## PR-7a — Structural emission pipeline + `signature` fact kind (G2)

**Objective:** stand up the StructuralField **emission** path end-to-end for Python, proving it with
the `signature` fact kind under a labeled R+D fixture suite. After this PR, `builder-code-vault` can
emit a governed `StructuralField` whose facts are deterministic, digest-stable, invariant under
declared transforms, and discriminating under genuine structural change.

**Claims unlocked:** structural correspondence **candidates** (hypothesis) for one construct.
**Refused:** multi-language structure (Python only; non-Python is fail-closed residue); verified
correspondence; any utility / U language; touching the frame-feeding extractor.

### Resolved design decisions

1. **Separate extraction lane — the frame path is frozen.** Add a NEW module
   `builder_ii/code_vault/structural_extractor.py`. It **must not import from or modify**
   `symbol_extractor.py`'s frame-feeding functions (`extract_python_symbols` /
   `extract_symbols_from_file`) — those bytes feed `create_hierarchical_frame` and are locked by
   invariant #8. The structural lane reads source independently and emits facts. It declares its own
   constants: `STRUCTURAL_EXTRACTOR_ID = "python-ast-structural"`, `STRUCTURAL_EXTRACTOR_VERSION =
   "1.0.0"`, `STRUCTURAL_PARSER_ID = "cpython_ast"`, plus `STRUCTURAL_SUPPORTED_CONSTRUCTS` /
   `STRUCTURAL_UNSUPPORTED_CONSTRUCTS` frozensets. For PR-7a `SUPPORTED` contains exactly the
   signature-relevant constructs it actually walks (`function_def`, `async_function_def`, `method` —
   i.e. it *does* descend into classes and nested scopes for signatures); everything else stays in
   `UNSUPPORTED`. Growing `SUPPORTED` later is a manifest/version event, not an edit.

2. **Manifest builder, no schema bump.** Add `build_structural_extractor_manifest(*, provenance=None)`
   to `extractor_manifest.py`, importing the structural extractor's constants (anti-transcription),
   with `coverage="structure"`, `language="python"`, `fail_closed=True`. Do **not** alter
   `build_extractor_manifest` (v0) — it stays byte-identical, existing manifest tests untouched. The
   two manifests coexist: distinct `extractor_id`, distinct coverage; both valid. The StructuralField
   binds to the **structural** manifest's `manifest_digest`.

3. **`subject_layout_id` scheme — bind to F0 where possible, extend where necessary.** Reproduce the
   frame's identity scheme so top-level facts bind to real frame nodes:
   `subject_layout_id = f"path:{normalize_layout_id(path)}#{subject_kind}:{qualname}"`, `subject_kind ∈
   {function, async_function, method, class}`, `qualname` = the dotted scope path (`Outer.inner`,
   `Cls.method`). For a top-level `def foo` this **equals** the frame node's `layout_id` exactly (facts
   bind to F0); for a method/nested def it extends beyond the frame (allowed — the field is a superset).
   Import `normalize_layout_id` from the layout module (intra-package; allowed). The id is
   deterministic and stable under file reformatting.

4. **`signature` normalized_value — arity shape, not names.** The canonical form is a **count/shape
   descriptor**, never argument names or text:
   `{"posonly": <int>, "pos_or_kw": <int>, "kwonly": <int>, "defaults": <int>, "kw_defaults": <int>,
   "vararg": <bool>, "kwarg": <bool>}` derived from the `ast.arguments` node. Because it carries no
   names and no formatting, it is invariant under `rename` (of args or the def), `format`, `comment`,
   and `reorder` (of sibling definitions — **not** of a function's own parameters, which is a genuine
   change). Therefore each `signature` fact declares
   `invariance_class = ["comment", "format", "rename", "reorder"]`.

5. **Emission function + determinism.** Add `build_structural_field(files, *, manifest, scope) ->
   dict` (files = an iterable of `(path, source)` or a repo_map-shaped input — resolve to one and state
   it). It runs the structural extractor over the scope, collects facts, **sorts** them by
   `(subject_layout_id, fact_kind, canonical_json(normalized_value))` for replay stability, collects
   fail-closed residue into `unsupported` (sorted), sets `extractor_manifest_ref =
   manifest["manifest_digest"]`, and computes `field_digest`. Reuse `create_structural_field_stub`'s
   assembly + `compute_field_digest` (do not fork the digest convention). Two builds over the same
   input are byte-identical (pin this).

6. **Fail-closed residue, never fabricated facts.** Syntax-error files, non-UTF-8 files, and any
   construct outside `STRUCTURAL_SUPPORTED_CONSTRUCTS` produce entries in `unsupported[]` (stable
   strings), never a guessed fact. A non-Python file in scope is `unsupported`, not an error.

7. **CLI + registration.** Add `builder-code-vault structural-field` (emit) — reads a repo map /
   source scope, builds the structural manifest, emits the field JSON. Register it: a real record in
   `command_authority.py` (structurally a leaf command, `artifact_only`, no execution authority) + a
   row in `docs/COMMAND_SURFACE_AUDIT.md`; re-generate the `_SYNTHESIZED_PARENTS` count (101 → 102)
   via `uv run python -m builder_ii.command_authority`, never by hand. `validate-structural-field`
   already exists — leave it.

8. **Governance / claim law.** `capability_state = code_vault_structural_field` (already registered);
   standard governance block (all execution surfaces `DISABLED`, `artifact_is_authority: false`).
   Promotion stays `artifact_only` / `hypothesis` — **no completion-matrix flip, no promotion**. Docs
   and the emit command describe facts as *structural correspondence candidates*; the words "verified",
   "correct", or any utility framing are forbidden (U is closed until G5).

### The R+D fixture suite (the proof — this is the point of the PR)

Under `tests/fixtures/` (or inline), a **labeled** suite for `signature`:

- **Invariance (must MATCH):** a canonical source and, for each declared class, a transformed twin —
  reformatted (`format`), comment-added (`comment`), args-and-def renamed (`rename`), sibling defs
  reordered (`reorder`). Assert identical `normalized_value` for the corresponding subject across every
  twin.
- **Discrimination (must DIFFER):** twins with a **genuine** signature change — a parameter added, a
  positional arg made keyword-only, `*args` introduced, a default added. Assert `normalized_value`
  differs. This is the "declared false-positive mode": a fact that cannot differ under real change has
  no detection value.
- **End-to-end determinism:** `build_structural_field` over a small fixture repo yields a byte-stable
  `field_digest` across two builds (pin the value); the field passes `validate_structural_field`;
  `extractor_manifest_ref` equals the structural manifest's digest.

### Files

New: `builder_ii/code_vault/structural_extractor.py`, `tests/test_code_vault_structural_extractor.py`,
fixture assets. Edit: `extractor_manifest.py` (+ `build_structural_extractor_manifest`, its test),
`structural_field.py` (+ `build_structural_field` emission, keep the stub), `cli/code_vault_cli.py`
(+ emit command), `command_authority.py` (+ record; regenerate count),
`tests/test_code_vault_structural_field.py`, `tests/test_command_authority.py` (count 101→102 via
generator), `docs/COMMAND_SURFACE_AUDIT.md`, `docs/CODE_VAULT_LANGUAGE_SUBSTRATE.md` (mark python
`structure_partial` → note the structural extractor lands `structure` for the declared set),
`docs/CODE_VAULT_STAGED_ACCEPTANCE.md` (new row), `docs/CODE_VAULT_CURRENT_STATE_AND_GAP_MAP.md` (gap
row: "structural intelligence" → landed-partial R+D for `signature`), `docs/ARTIFACT_INDEX.md` if the
emit surface warrants it.

### Tests first

Write the invariance + discrimination fixture assertions RED before the extractor exists; then the
emission determinism pin; then the manifest-builder test; then the CLI emit test. Implement to green.

### Out of scope

Fact kinds other than `signature` (PR-7b/7c); any change to `symbol_extractor.py` or the frame; a
second language; RelationField / edges (G4); any similarity geometry over facts; recall/lint consuming
the field; U / utility claims of any kind.

---

## PR-7b — `nesting`, `ownership`, `decorator`, `import_fact` (G2, LANDED)

**Objective:** add four fact kinds to the landed PR-7a emission pipeline, each proven R+D under its
own labeled invariance + discrimination suite. After this PR, `builder-code-vault structural-field`
emits five of the six registered fact kinds; only `motif` (PR-7c) remains.

**Claims unlocked:** structural correspondence **candidates** (hypothesis) for four more constructs.
**Refused:** `motif` (PR-7c); RelationField / dependency **edges** with source→target ids (G4 —
`import_fact` here is a per-file fact, not an edge); similarity scoring over facts; a second
language; touching the frame path; descending into function bodies for subjects; any U language.

### PR-7b starting line (measured on landed `main` after #87 — verify, then build)

| Surface | Fact (read from the modules) |
|---|---|
| `structural_extractor.py` | v`1.0.0`; `SUPPORTED = {function_def, async_function_def, method}`; walks module top-level + class bodies (any depth) for def subjects; **never** descends into function bodies. `MAX_STRUCTURAL_SUBJECTS_PER_FILE = 64` — but the loop breaks on `len(facts) >= 64`, i.e. it currently counts **facts**, which equals subjects only while each subject emits exactly one fact. Decision #7 below re-grounds it. |
| `structural_field.py` | **Kind-agnostic**: `build_structural_field` aggregates whatever the extractor returns; `_validate_fact` requires `subject_layout_id` = any non-empty string, `fact_kind ∈ FACT_KINDS` (all six registered), `normalized_value` present (any JSON), `invariance_class` = non-empty subset of `INVARIANCE_CLASSES`. **Expect zero changes to this module.** |
| `extractor_manifest.py` | `build_structural_extractor_manifest` imports the extractor constants — construct/version changes flow through with **no manifest-code edit**. |
| Frame (`hierarchy.py`) | Top-level classes are real F0 nodes: `path:{p}#class:{Name}` (v0 symbol kind `"class"`). File nodes are `path:{p}` (pure path). Both give 7b facts real F0 binding targets. |
| CLI / registration | `builder-code-vault structural-field` exists; `_SYNTHESIZED_PARENTS` pin = **102**. 7b adds **no command** — the pin does not move. |
| 7a review debt (carried by this order) | (1) 7a's rename twin renamed args only — decision #9 closes it. (2) Literal digest pins are **forbidden** — see decision #8 for why. Recorded here so neither narrowing repeats silently. |

### Resolved design decisions

1. **Declared version event.** `STRUCTURAL_SUPPORTED_CONSTRUCTS` grows by
   `{class_def, decorator_fact, import_fact, nesting_fact, ownership_fact}`;
   `STRUCTURAL_UNSUPPORTED_CONSTRUCTS` keeps `{lambda_def, motif_fact, nested_function_def,
   non_python_files, non_utf8_files, syntax_error_files}`. Bump `STRUCTURAL_EXTRACTOR_VERSION`
   `"1.0.0"` → `"1.1.0"`. The manifest re-declares itself via its imports — no manifest edit. The
   7a test pinning the exact 7a construct set is **updated deliberately** (rename it to match; this
   is the declared version event, not a forbidden edit — say so in its docstring).

2. **New subjects and their binding.** Classes become subjects: `subject_kind = "class"`, dotted
   `qualname` (`Outer.Inner`); a top-level class's `subject_layout_id` **equals** its F0 frame node
   id. Module-level facts (`import_fact`) bind the frame **file** node **verbatim**:
   `subject_layout_id = f"path:{normalize_layout_id(path)}"` — no `#` fragment, exactly the frame's
   file `layout_id` (the validator requires only a non-empty string; this is the strongest possible
   F0 binding, zero invented scheme).

3. **`nesting` — scope shape, no names.** Subjects: every walked def/class. `normalized_value =
   {"depth": <int>, "scope_chain": ["module", "class", ...]}` — enclosing scope **kinds** only,
   never names (`depth == len(scope_chain) - 1`; top-level def → `{"depth": 0, "scope_chain":
   ["module"]}`; method or class-nested class → `["module", "class"]`, deeper as found). Closures
   stay out (function bodies are not walked — unchanged). `invariance_class = ["comment", "format",
   "rename", "reorder"]`. Discrimination is **cross-subject** where re-scoping changes the id: a
   module function moved into a class is compared value-to-value between the old and new subjects.

4. **`ownership` — the membership fact, path-free.** Subjects: methods only (per the sketch).
   `normalized_value = {"member_kind": "method", "member_name": "<name>", "owner_qualname":
   "<dotted class chain>"}`. It deliberately **carries names** and **no path**, so it is invariant
   under `move` (same class in a different file → identical value, compared cross-subject) and
   **not** under `rename` — renaming the method or its owner is a *genuine change* for this kind.
   `invariance_class = ["comment", "format", "move", "reorder"]`.

5. **`decorator` — ordered, called-aware; sketch refined.** Subjects: any walked def/class that has
   decorators (**emit nothing for undecorated subjects** — absence of the fact means "no
   decorators"; declared here). `normalized_value = [{"name": "<dotted>", "called": <bool>}, ...]`
   in **source order, top to bottom**. Two refinements of the stub's "name set", recorded with
   reasons: (a) an **ordered list**, not a set — Python composes decorators in order, and a sorted
   set would make a decorator swap an undetectable collision (a worse declared false-positive
   mode); (b) `called` distinguishes `@f` from `@f()`. The `name` is the dotted path of a
   `Name`/`Attribute` callee (`property`, `functools.wraps`); a callee that is not statically a
   dotted name normalizes to the declared sentinel `"<dynamic>"` — declared ignorance, never a
   fabricated name (state this in the module docstring). `invariance_class = ["comment", "format",
   "reorder"]` (`reorder` = of sibling definitions — **not** of the subject's own decorator
   sequence, which is a genuine change; same parenthetical convention as `signature`'s parameters).

6. **`import_fact` — the file's import surface.** Subject: the file node (decision #2). One fact
   per imported binding, from **every** `Import`/`ImportFrom` node in the file (full-tree walk —
   `if TYPE_CHECKING:`- and `try/except`-guarded imports are real dependencies; the
   no-function-body rule protects definition *subjects*, and the subject here is the file).
   `normalized_value = {"level": <int>, "module": "<str>", "name": <str | null>}` — `level` =
   relative-import dot count (0 for absolute), `module` = the stated module (`""` for a bare
   `from . import x`), `name` = the imported binding (`null` for `import os`; `"*"` for a star
   import). Local aliases (`as z`) are **ignored** — the dependency is what is imported, not what
   it is locally called. **Dedupe identical `(subject, fact_kind, normalized_value)` facts**
   (declared; two `import os` statements are one dependency). `invariance_class = ["comment",
   "format", "reorder"]` — a refinement of the stub's `format/reorder`: comment-invariance is
   trivially provable, so declare and prove it.

7. **Cap semantics re-grounded: the bound counts subjects, not facts.** With multiple kinds per
   subject, a fact-count break truncates at ~13 subjects and its meaning silently drifts from the
   manifest's `max_symbols_per_file`. Re-implement: walk at most `MAX_STRUCTURAL_SUBJECTS_PER_FILE`
   (64) **subjects** per file, emitting *all* facts for each walked subject; bound `import_fact`s
   separately at the same constant per file. Truncation stays **silent** (bound declared in the
   manifest, no residue entry) — the v0 convention, kept deliberately (#87 disposition). Pin the
   subject-cap semantics with a >64-subject fixture asserting complete fact sets per walked subject.

8. **Determinism; literal digest pins FORBIDDEN.** Two builds over the same input are
   byte-identical (pin by comparing the two builds). Do **not** pin a literal `field_digest` or
   `manifest_digest` in any test: `field_digest` covers `extractor_manifest_ref` →
   `manifest_digest` → `parser_version` = the **running Python version**, so a literal pin is a
   host-dependent flake (7a review finding; the "pin the value" wording in the 7a order was the
   defect). Facts sort under the existing `(subject_layout_id, fact_kind,
   canonical_json(normalized_value))` key — unchanged.

9. **Signature stays byte-stable; the 7a rename gap closes here.** (a) Regression pin: the
   `signature`-kind subset of facts over 7a's canonical fixture is **identical** (subjects and
   values) before and after this PR — new kinds add facts, they never change settled ones.
   (b) Backfill the 7a narrowing: one new test renames a def **and** its args
   (`alpha` → `omega`) and asserts the renamed subject's `signature` `normalized_value` equals the
   canonical subject's, **cross-subject** — proving the descriptor is fully name-blind. (c) The
   frame path stays frozen: `symbol_extractor.py` / `hierarchy.py` untouched; default frame digest
   unchanged (invariant #8).

10. **Governance / claim law — unchanged.** Same `capability_state`, `artifact_only` / `hypothesis`,
    standard governance block, **no completion-matrix flip, no promotion, no new command** (count
    stays 102). All docs and docstrings use *structural correspondence candidates*; "verified" /
    "correct" / utility framing forbidden (U closed until G5).

### The R+D fixture suite (the proof — one labeled suite per kind)

For **each** of the four kinds, against a canonical source rich enough to exercise it:

- **Invariance (must MATCH):** one twin per declared invariance class — reformatted (`format`),
  comment/docstring-added (`comment`), sibling-defs-reordered (`reorder`); plus per kind:
  `nesting` an args-**and-def** renamed twin (`rename`, cross-subject); `ownership` a same-content
  twin at a **different file path** (`move`, cross-subject). Assert equal `normalized_value` for
  the corresponding subject in every twin.
- **Discrimination (must DIFFER — the declared false-positive audit):**
  `nesting`: module function moved into a class; a class nested into another class.
  `ownership`: method moved to a different class; method renamed; owner class renamed.
  `decorator`: decorator added; removed; two decorators swapped; `@f` → `@f()`.
  `import_fact`: import added; removed; module changed; `from x import y` → `from x import y, z`;
  absolute → relative (`level` change); star import introduced.
- **Baseline shape pins:** exact `normalized_value` dicts for representative subjects of each kind
  (the 7a pattern — these exact-equality pins are what give the suite teeth against descriptor
  drift).
- **End-to-end:** one `build_structural_field` run over a mixed fixture emitting **all five kinds**;
  validates with zero errors; two builds byte-identical; residue behavior unchanged (non-Python /
  syntax-error / unreadable files); the decision-#7 subject-cap pin; the decision-#9 signature
  regression + def-rename backfill pins.

### Files

Edit: `builder_ii/code_vault/structural_extractor.py` (four kinds + constants + version + cap
semantics), `tests/test_code_vault_structural_extractor.py` (suites above; update the 7a exact-set
constants test as a declared version event), `tests/test_code_vault_structural_field.py` (mixed-kind
end-to-end additions), `docs/CODE_VAULT_LANGUAGE_SUBSTRATE.md` (readiness cell: F2 partial →
`signature`+4, `motif` outstanding), `docs/CODE_VAULT_CURRENT_STATE_AND_GAP_MAP.md` (structural-
intelligence row), `docs/CODE_VAULT_STAGED_ACCEPTANCE.md` (7b row),
`docs/COMMAND_SURFACE_AUDIT.md` (the PR-7a delta prose says "`signature` facts only" — update to the
five-kind truth), `builder_ii/cli/code_vault_cli.py` **docstring only** (same "signature facts only"
staleness; no behavior change). Expected untouched: `structural_field.py`, `extractor_manifest.py`,
`command_authority.py`, `symbol_extractor.py`, `hierarchy.py`.

### Tests first

Per kind: write the invariance + discrimination fixtures RED, then implement that kind to green,
kind by kind (`nesting` → `ownership` → `decorator` → `import_fact`), then the mixed-kind
end-to-end + cap + signature-regression pins. If the code contradicts this order anywhere, **amend
this section in the same PR** and say so in the PR body — recorded divergence is protocol; silent
narrowing is a defect even when the code choice is right (that is the 7a lesson, twice).

### Amendments recorded during implementation (PR-7b)

Four places where the order met the code imperfectly. Recorded here per the work-order protocol,
not silently absorbed.

1. **`tests/test_code_vault_cli.py` needed an edit — it was not in the Files list.** Its
   structural-field assertion selected a subject's fact by `subject_layout_id` alone. Once a
   subject carries several kinds this is ambiguous, and it silently began reading the wrong fact:
   under the canonical sort key, `nesting` sorts ahead of `signature`. Fixed by selecting on
   `(subject, fact_kind)`. The same latent ambiguity existed in the extractor suite's `_fact_for`
   helper, which is now keyed by `(subject, kind)` and still asserts exactly one match — a subject
   must never carry two facts of one kind.
2. **The cap bounds *distinct* imports.** Decision #7 said to bound `import_fact`s "separately at
   the same constant" but did not say whether the bound applies before or after the decided
   dedupe. Implemented as **dedupe first, then cap**, so the bound counts distinct dependencies —
   the alternative would let one repeated `import os` consume budget that a real dependency needs.
3. **`tests/test_code_vault_structural_field.py`'s two PR-7a `len(facts)` pins moved.** They
   asserted exact fact *counts* (3, and 1) that only held while each subject emitted one fact.
   Re-expressed as kind-aware assertions that still pin the `signature` subset exactly (decision
   #9a) while admitting the added kinds.
4. **TDD sequencing, stated honestly.** The four kinds hang off one shared subject walk, which was
   rewritten during the `nesting` cycle (it is also where the decision-#7 cap fix lives). To keep
   red-first real rather than nominal, the `ownership` / `decorator` / `import_fact` emission
   blocks were **backed out** of that rewrite and re-added one at a time, so each kind's fixtures
   were genuinely RED before its own emission code existed. The cap pin was additionally
   **mutation-proven**: restoring PR-7a's `len(facts)` break makes it fail with 22 of 64 subjects
   walked — the latent truncation quantified.

### Out of scope

`motif` (PR-7c); RelationField / edges (G4); similarity geometry; recall/lint consuming the field;
second language; frame changes; closures/function-body subjects; new CLI surface.

## PR-7c — `motif`, or formally defer it (authored after PR-7b lands)

`motif` (recurring structural pattern) is the fuzziest kind and has no settled normalized form. Per
Axiom Zero, PR-7c either lands a precise, labeled definition or **registers `motif` as a deferred
decision** (schema already reserves the kind) rather than specify against an unformed idea.

---

## Shared acceptance battery (every PR in this wave)

```bash
uv run pytest tests/test_code_vault_structural_extractor.py tests/test_code_vault_structural_field.py \
  tests/test_code_vault_extractor_manifest.py tests/test_code_vault_cli.py \
  tests/test_command_authority.py tests/test_command_surface_audit.py tests/test_artifact_index_records.py -q
uv run builder-platform audit-docs
uv run pytest tests/test_docs_truth_enforcement.py -q
bash scripts/ci.sh --receipt .builder/artifacts/gate-battery-receipt.json   # AFTER the last commit; head_sha == pushed head
```

PR bodies report actual output, bind the receipt `head_sha` to the pushed head, and state:
RECORDED_ONLY, no matrix flip, no promotion, facts are hypothesis candidates (R+D, not U), rollback =
revert + delete emitted JSON.

---

## Deferred decisions (carried into / created by G2)

| Decision | Blocks | Mechanism | State |
|---|---|---|---|
| `motif` normalized form | PR-7c | precise labeled definition or a registered deferral | Open — do not specify before PR-7b lessons |
| Second-language extractor (parser strategy) | G3 | HITL note on the language-substrate axes | Open (already registered in the execution map) |
| Similarity geometry over structural facts | any correspondence *scoring* | Tier-2 graded-similarity RFC (operator-deferred) | Deferred — G2 emits facts, it does not score them |
| U task registry + rubric | G5 utility claims | HITL-approved RECORDED_ONLY design artifact | Open — nothing in G2 reaches U |

---

## Related

- [`CODE_VAULT_EXECUTION_MAP.md`](CODE_VAULT_EXECUTION_MAP.md) — wave structure, standing invariants, protocol
- [`CODE_VAULT_G1B_WAVE_BRIEFS.md`](CODE_VAULT_G1B_WAVE_BRIEFS.md) — wave-2 orders (landing PR-4/5/6)
- [`../CODE_VAULT_LANGUAGE_SUBSTRATE.md`](../CODE_VAULT_LANGUAGE_SUBSTRATE.md) — StructuralField IR sketch these facts implement
- [`../CODE_VAULT_PROOF_PROGRAM.md`](../CODE_VAULT_PROOF_PROGRAM.md) — the R+D bar and labeled-fixture requirement
- [`../CODE_VAULT_ROADMAP.md`](../CODE_VAULT_ROADMAP.md) — gate G2 this wave opens toward
