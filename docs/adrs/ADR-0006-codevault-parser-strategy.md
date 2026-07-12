# ADR-0006: CodeVault Parser Strategy (Hybrid)

## Status

Accepted (2026-07-11).

## Context

Gate G3 (second-language extractor skeleton) was blocked on an open deferred-decision registry row:

> Parser strategy (native AST vs tree-sitter vs SCIP/LSIF vs hybrid) — do not bind before G2 lessons

G2 is OPEN. The G2 lessons that bind this decision are concrete:

1. **Language-semantics fidelity, not a syntax tree.** PR-7d adopted CPython's own `__qualname__` /
   `<locals>` scheme rather than inventing a parallel naming lattice. Whatever we parse with must
   honor the language's own identity model.
2. **`parser_version` is inside the digest.** A host-dependent parser identity is a digest-stability
   flake, not a convenience. Pinnable grammar versions are required for R proofs.
3. **Residue over fabrication; declared blindness.** Whatever we parse with must let us say what we
   did not read (`unsupported` / readiness states / declared-blindness vocabulary).

ADR-0005 forbids CodeVault from executing anything over the target repository. SCIP/LSIF indexes are
produced by running language servers / indexers (e.g. rust-analyzer). Naively that appears to kill
the SCIP option.

It does not. The same shape that dissolved `changed` scope applies: reframe a *capability*
("compute a diff" / "run an indexer") into a *declaration* ("be told what changed / be handed an
index", digest-bound). The caller runs the indexer. CodeVault ingests SCIP/LSIF as a
caller-supplied, digest-bound, declared input — same grammar as provenance, coverage, and `changed`.
Never derived. Always handed in.

## Decision

**Hybrid strategy:**

| Layer | Choice | Why |
|---|---|---|
| **G3 skeleton** | In-process parse with a **pinned grammar version** (stdlib AST for Python; pinned skeleton grammar for Rust and future layout-only languages) | G3's bar is R-only (`layout_only` / partial stubs) — no name resolution required. A pinnable grammar keeps `parser_version` stable across host toolchains (G2 digest lesson). |
| **G4 relation depth** | Caller-supplied, **digest-bound SCIP/LSIF** (or equivalent indexer output) as declared input | Real name resolution without CodeVault ever executing an indexer. Severability cost: zero. CodeVault never generates SCIP/LSIF. |

### Non-decisions (explicit)

- tree-sitter is **not** the G3 default. It remains an optional future path only if a pinned grammar
  crate and CI-friendly native build prove R-stable on M1 without authority creep.
- `builder_ii_validation_rs` is an **artifact validator accelerator**, not a source extractor.
- The optional `core_rs` recall backend is a **matrix scorer**, not a Rust parser.
- Generating SCIP/LSIF inside `code_vault/` by spawning rust-analyzer or any indexer is **forbidden**.

### Scoring axes satisfied

| Axis | How the hybrid scores |
|---|---|
| Determinism | Pinned grammar versions enter the digest; host toolchain drift is refused |
| Install cost / M1 sympathy | In-process skeleton has no native toolchain; SCIP is optional caller input |
| Severability of `code_vault/` | No git/shell/indexer imports; SCIP is bytes+digest handed in |
| Fidelity | Semantics fidelity at G2 (Python AST); declared residual honesty at G3; SCIP for G4 depth |
| Fail-closed coverage honesty | `layout_only` / `structure_partial` / `unsupported_*` readiness states remain mandatory |

## Consequences

- The deferred-decision registry parser-strategy row flips to **Decided (ADR-0006)**.
- G3 is no longer blocked solely by this row; G3 work may land as a G2-shaped wave (schema → emission
  → R-suite → ledger readiness evidence). Gate OPEN remains HITL.
- G4 RelationField may accept SCIP/LSIF only as a digest-bound declared input block; emission paths
  that shell out to indexers must fail closed in tests.
- `parser_version` for skeleton extractors is a **pinned constant** (or language-runtime version only
  when that runtime is the declared grammar, as with CPython AST), never an unbound host probe of
  optional tools.

## Acceptance criteria

- This ADR is indexed in `docs/adrs/README.md`.
- `docs/plan/CODE_VAULT_EXECUTION_MAP.md` deferred-decision registry records the row as decided and
  cites this ADR plus G2 lessons and ADR-0005.
- `docs/CODE_VAULT_LANGUAGE_SUBSTRATE.md` parser-strategy section crowns the hybrid (no longer
  "non-decision yet").
- Authority pins: `tests/test_code_vault_no_runtime_authority.py` and any SCIP-ingest tests continue
  to prove CodeVault never executes an indexer.

## Related

- [`ADR-0005-codevault-boundary-and-authority.md`](ADR-0005-codevault-boundary-and-authority.md)
- [`../CODE_VAULT_LANGUAGE_SUBSTRATE.md`](../CODE_VAULT_LANGUAGE_SUBSTRATE.md)
- [`../plan/CODE_VAULT_EXECUTION_MAP.md`](../plan/CODE_VAULT_EXECUTION_MAP.md)
- [`../CODE_VAULT_GATE_STATE.md`](../CODE_VAULT_GATE_STATE.md)
