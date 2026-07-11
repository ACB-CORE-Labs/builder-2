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
> completes. As of this writing PR-4 (#82) and PR-6 (#83) are merged; **PR-5 (#84) must merge first.**
> Author the PR-7b/7c detailed orders only after PR-7a lands (measure, then amend; never specify
> against an unbuilt pipeline).

---

## Code-clock starting line (measured on the settled schemas, not assumed)

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
  PR-7a  Structural emission pipeline + FIRST fact kind (signature), R+D end-to-end
  PR-7b  fact kinds: nesting, ownership, decorator, import_fact (each R+D)   [authored after 7a]
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

## PR-7b — `nesting`, `ownership`, `decorator`, `import_fact` (authored after PR-7a lands)

Adds four fact kinds against the settled PR-7a pipeline, each with its own labeled invariance +
discrimination suite and declared `invariance_class`. Sketch (finalized in its own order):
`nesting` = normalized scope-depth/path structure (invariant: comment/format/rename/reorder);
`ownership` = method→owner-class membership (invariant: comment/format/reorder/move);
`decorator` = normalized decorator-name set on a subject (invariant: comment/format);
`import_fact` = normalized (module, imported-name) pair (invariant: format/reorder). Each grows
`STRUCTURAL_SUPPORTED_CONSTRUCTS` → a `STRUCTURAL_EXTRACTOR_VERSION` bump + manifest re-declaration.

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
