# CodeVault Wave-1 Work Orders (PR-1, PR-2, PR-3)

**Status:** Dispatchable work orders for the [execution map](CODE_VAULT_EXECUTION_MAP.md)'s wave 1.  
**Kind:** Design / work orders (RECORDED_ONLY). Implements no capability by existing.

Each order resolves every design decision in advance: the implementer inherits zero architectural
ambiguity. If a decision here survives contact with the code imperfectly, the implementing PR
amends this document in the same change — never diverges silently.

**All three orders inherit the [standing invariants](CODE_VAULT_EXECUTION_MAP.md#standing-invariants-every-pr-in-this-slice-inherits)**
(severability, governance block, claim law, anti-transcription, fail-closed, TDD, docs-in-same-PR,
frame byte-stability). The three PRs are mutually independent: implement concurrently in separate
worktrees, one branch per PR from `main`.

---

## PR-1 — ExtractorManifest: the Python extractor v0 declares itself

**Objective:** every extraction surface must be able to say *what it is, what it covers, and what
it refuses* — the substrate every later field (F2/F3/F4) hangs coverage honesty off.

**Claims unlocked:** "extractors are declared." **Refused:** any structure-intelligence language;
the extractor's *behavior* does not change in this PR — PR-1 only declares what already exists.

### Resolved design decisions

1. **Separate artifact, never a frame field.** The manifest records `parser_version` (runtime
   CPython), which varies across hosts. Embedding it in the frame would make frame digests
   machine-dependent and break byte-stability pins. The manifest is its own artifact; future
   StructuralField binds to it by digest (`extractor_manifest_ref`).
2. **Anti-transcription is structural.** The construct lists and bounds live as constants in
   `symbol_extractor.py`, adjacent to the code they describe; the manifest builder **imports**
   them. A test asserts the manifest equals the module constants — the manifest cannot drift.
3. **Identity strings:** `extractor_id = "python-ast-toplevel"`, `extractor_version = "0.1.0"`
   (semver; bump on any behavior change), `parser_id = "cpython_ast"`, `parser_version =
   platform.python_version()` at build time (provenance, deliberately host-dependent).
4. **Coverage vocabulary** comes from the [language substrate readiness matrix](../CODE_VAULT_LANGUAGE_SUBSTRATE.md#language-readiness-matrix-v0--honest):
   Python v0 declares `structure_partial`. Unknown coverage states fail closed in the validator.
5. **Digest convention:** `manifest_digest` = SHA-256 over canonical JSON (`sort_keys=True`,
   separators `(",", ":")`) of the manifest dict *before* the digest field is added — the same
   convention as `report_digest` in `reports/linter.py`.

### Files

| Action | Path |
|---|---|
| create | `builder_ii/code_vault/extractor_manifest.py` |
| edit | `builder_ii/code_vault/symbol_extractor.py` (add declaration constants only — no behavior change) |
| edit | `builder_ii/cli/code_vault_cli.py` (two subcommands) |
| edit | `builder_ii/command_authority.py` (subcommand enumeration) |
| edit | `builder_ii/artifact_index_records.py` (register kind + validator) |
| create | `tests/test_code_vault_extractor_manifest.py` |
| edit | `tests/test_code_vault_cli.py`, docs listed below |

### Schema (`builder_ii.code_vault.extractor_manifest`, v1)

```text
kind: "builder_ii.code_vault.extractor_manifest"
schema_version: 1
language: "python"                      # v1 registers python only; unknown languages refused
extractor_id: "python-ast-toplevel"
extractor_version: "0.1.0"
parser_id: "cpython_ast"
parser_version: "<platform.python_version()>"
coverage: "structure_partial"           # readiness-matrix vocabulary; frozenset-validated
constructs_supported: ["class_def_toplevel", "function_def_toplevel", "async_function_def_toplevel"]
unsupported_constructs: [               # honest enumeration of v0's silences
  "async_function_distinction",         # async collapsed to kind "function"
  "assignments_as_symbols", "decorators_as_facts", "lambdas",
  "methods", "nested_definitions",
  "non_utf8_files",                     # OSError/read failure → []
  "syntax_error_files"                  # SyntaxError → []
]
limits: { max_symbols_per_file: 64, max_symbol_content_bytes: 8192 }   # imported, not typed
fail_closed: true
provenance: { scope_paths?: [...], commit_id?: str, dirty?: bool } | absent   # accepted, never derived here (F4 skeleton)
governance: { …standard block…, capability_state: "code_vault_extractor_manifest",
              artifact_is_authority: false }
manifest_digest: "<sha256>"
```

Constants added to `symbol_extractor.py`: `EXTRACTOR_ID`, `EXTRACTOR_VERSION`, `PARSER_ID`,
`SUPPORTED_CONSTRUCTS`, `UNSUPPORTED_CONSTRUCTS` (frozensets; serialized sorted). Lists in
artifacts are emitted sorted for byte stability.

### Validator (`validate_extractor_manifest(data) -> list[str]`)

Kind/schema-version exact; language in registered frozenset; coverage in readiness vocabulary;
construct lists sorted + disjoint; limits present and positive ints; `fail_closed is True`;
governance block enforced key-by-key (linter-validator style); `manifest_digest` re-derived and
compared — mismatch is a named error; unknown top-level keys refused; provenance, when present,
shape-checked (`commit_id` 40-char hex or absent).

### CLI

`builder-code-vault extractor-manifest --language python --output PATH` (build + validate + write)
and `builder-code-vault validate-extractor-manifest PATH`. Both added to the `command_authority.py`
enumeration; `builder-code-vault` record itself is untouched (stays Tier 1 / artifact-only).

### Tests first (TDD — write failing, then implement)

1. Build → validate round trip: zero errors.
2. Tampered `manifest_digest` → named refusal.
3. Unknown `coverage` / unknown `language` / `fail_closed: false` → refusals.
4. Governance: each execution key must be `DISABLED`; `artifact_is_authority` must be `False`.
5. **Anti-transcription pin:** manifest construct lists == `symbol_extractor` frozensets; limits ==
   module constants (import both sides; no literals in the test).
6. Determinism: two builds in-process differ only by nothing (same `parser_version` host) — byte-equal JSON.
7. CLI: build/validate exit codes; invalid path exits non-zero. Command-authority enumeration test
   updated (the pin will fail until the registry entry lands — that is the TDD signal).

### Docs in the same PR

`docs/ARTIFACT_INDEX.md` (kind row), `docs/COMMAND_SURFACE_AUDIT.md` (subcommands),
`docs/CODE_VAULT_STAGED_ACCEPTANCE.md` (new ledger row: capability state `artifact_only` /
`validation_only`, failure mode, rollback = delete JSON, verification path),
`docs/CODE_VAULT_CURRENT_STATE_AND_GAP_MAP.md` (ExtractorManifest delta row → landed at ledger
state), `docs/CODE_VAULT_LANGUAGE_SUBSTRATE.md` (design-target section gains a landing note).
Roadmap G1 stays open — it needs all its bullets, not this PR alone.

### Out of scope

Extractor behavior changes; frame schema changes; StructuralField facts; second languages;
completion-matrix flips; promotion of any kind.

---

## PR-2 — StructuralField schema stub (validator without an emission path)

**Objective:** land the F2 Artifact IR shape (schema + validator + registration) with **no
builder that emits facts** — the schema exists and is enforceable before any extractor may fill
it, so G2 work lands against a settled, reviewed target.

**Claims unlocked:** "the F2 schema exists." **Refused:** structural-correspondence vocabulary
(needs G2's R+D), any claim that structure is extracted.

### Resolved design decisions

1. **No build subcommand in this PR.** Only `validate-structural-field` ships. A build path without
   invariance fixtures would be a fabricated-structure vector — exactly what fail-closed forbids.
   The G2 work order (authored after wave 1) adds emission.
2. **Fact vocabulary is a registered frozenset**, v1: `{"decorator", "import_fact", "motif",
   "nesting", "ownership", "signature"}`. Unknown `fact_kind` refused. Growing the set is a
   schema-version event, not an edit.
3. **Invariance classes are a registered frozenset**: `{"comment", "format", "move", "rename",
   "reorder"}` — each fact declares which transformations its `normalized_value` survives.
4. **Cross-artifact binding:** `extractor_manifest_ref` is the SHA-256 `manifest_digest` of a
   PR-1 manifest. Shape-validated here (64-char hex); resolution against a real manifest file is
   G2 behavior. This keeps PR-2 parallel-safe with PR-1.
5. **`language` on each fact is provenance only** — the schema stays language-neutral; no
   language-privileged fields (substrate law).

### Schema (`builder_ii.code_vault.structural_field`, v1)

```text
kind: "builder_ii.code_vault.structural_field"
schema_version: 1
extractor_manifest_ref: "<sha256>"      # binds every fact to a declared extractor
scope: { mode: "paths" | "package" | "full", paths: [...] }   # sorted; coverage-honest
facts: [ { subject_layout_id, fact_kind, normalized_value, language,
           invariance_class: [...] } ]  # MAY be empty in the stub era
unsupported: [...]                      # fail-closed residue; sorted
governance: { …standard block…, capability_state: "code_vault_structural_field",
              artifact_is_authority: false }
field_digest: "<sha256>"                # same canonical-JSON convention as PR-1
```

### Files

Create `builder_ii/code_vault/structural_field.py` + `tests/test_code_vault_structural_field.py`;
edit `cli/code_vault_cli.py`, `command_authority.py` (add `validate-structural-field`),
`artifact_index_records.py`; docs: `ARTIFACT_INDEX.md`, `COMMAND_SURFACE_AUDIT.md`,
staged-acceptance row, gap-map delta update.

### Tests first

Empty-facts artifact round-trips; tampered `field_digest` refused; unknown `fact_kind` /
`invariance_class` / `scope.mode` refused; malformed `extractor_manifest_ref` refused; governance
enforced; a fact with every field present validates; unknown top-level keys refused; CLI
validate-path exit codes; command-authority enumeration pin updated.

### Out of scope

Fact emission of any kind; extractor changes; grade-4/5 lifts (needs its own Axiom Zero
measurement per the substrate); relation facts (F3 is `RelationField`, gate G4).

---

## PR-3 — Frame provenance binding (schema v2 → v3, additive-optional)

**Objective:** a hierarchical frame can declare **which repository state it describes** —
`commit_id`, `dirty`, scope — closing the gap-map row "frame binds to the repository state it
describes." This is the F4 skeleton applied at frame level.

**Claims unlocked:** "a frame can bind to a repo state." **Refused:** lineage/change intelligence
(F4 proper, gate G7); any claim that `dirty` is known when it was not derived.

### Resolved design decisions

1. **The vault validates provenance; it never derives it.** Derivation reads repo state, which is
   outside the package's severability line. A new helper `builder_ii/code_vault_provenance.py`
   lives **outside** `code_vault/` (receipt-bridge precedent) and callers thread its output in.
2. **Pure file reads, no subprocess.** The helper resolves `commit_id` by reading `.git/HEAD`,
   following a ref to `.git/refs/...` or `.git/packed-refs`. No `git` invocation. Non-git
   directory, unreadable files, detached-head edge cases → `commit_id: None`, fail-closed.
3. **`dirty` is honest-unknown in v1.** Computing dirtiness requires status semantics the helper
   does not implement; it returns `dirty: None` with `dirty_reason: "not_derived"`. Upgrading this
   is a registered deferred decision — never a guess.
4. **Default OFF.** `create_hierarchical_frame` gains an optional `provenance=None` parameter.
   Absent → no block emitted → frames built with today's inputs are byte-identical to today's.
   Demo pins, byte-stability tests, and downstream consumers are untouched. Wiring
   prepare-package to opt in is wave-2 (PR-4) territory, deliberately out of scope here.
5. **Versioning per the encoded policy** (`hierarchy.py`): additive-optional field → schema 3,
   `SUPPORTED_FRAME_SCHEMA_VERSIONS = (1, 2, 3)`; v1/v2 frames stay valid.

### Provenance block shape

```text
provenance: {
  commit_id: "<40-char sha1 hex>" | null,
  dirty: true | false | null,
  dirty_reason: "not_derived" | "caller_supplied",   # required iff dirty is null / supplied
  scope: { mode: "full" | "paths", paths?: [...] },
  derived_by: "caller" | "builder_ii.code_vault_provenance"
}
```

Validator: when present, shape-checked key-by-key; `commit_id` 40-char lowercase hex or null;
unknown keys refused; a `dirty` value without a consistent `dirty_reason` refused.

### Files

Edit `builder_ii/code_vault/hierarchy.py` (dataclass field + builder param + validator + version
constants); create `builder_ii/code_vault_provenance.py` (outside the package) +
`tests/test_code_vault_provenance.py`; edit `tests/test_code_vault_hierarchy.py`; docs:
staged-acceptance amendment, gap-map row update, `CODE_VAULT_HIERARCHY.md` note.

### Tests first

v2 frame (no provenance) still validates; v3 frame with provenance round-trips byte-stably;
tampered/short `commit_id` refused; unknown provenance keys refused; **default-off pin:** frame
built without the param is byte-identical to before the change (assert against a recorded
digest); helper: resolves HEAD in fixture git dirs (direct hash, ref file, packed-refs), returns
`None` fail-closed on non-git dirs; helper performs no subprocess calls (no `subprocess` import —
assert at module level); demo suite still passes untouched.

### Out of scope

Deriving `dirty`; wiring prepare-package/workflow emission (wave 2); extractor or StructuralField
changes; any lineage claims.

---

## Shared acceptance battery (all three PRs)

```bash
uv run pytest <the PR's named test slice> -q
uv run builder-platform audit-docs        # docs claims stay within capability states
uv run pytest tests/test_docs_truth_enforcement.py -q
bash scripts/ci.sh                        # the full blocking gate battery before review
```

PR bodies report actual command output, follow the conventional-commit format, and state
explicitly: RECORDED_ONLY, no matrix flip, no promotion, rollback = revert + delete emitted JSON.

---

## Related

- [`CODE_VAULT_EXECUTION_MAP.md`](CODE_VAULT_EXECUTION_MAP.md) — wave structure and invariants
- [`../CODE_VAULT_ROADMAP.md`](../CODE_VAULT_ROADMAP.md) — gates G1/G1b these PRs serve
- [`../CODE_VAULT_LANGUAGE_SUBSTRATE.md`](../CODE_VAULT_LANGUAGE_SUBSTRATE.md) — the IR sketches PR-1/PR-2 implement
- [`../CODE_VAULT_PROOF_PROGRAM.md`](../CODE_VAULT_PROOF_PROGRAM.md) — R evidence each PR must file
