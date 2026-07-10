# CodeVault Master Plan — Path to Fruition

**Status:** Official consolidated plan for CodeVault in **builder-II**.  
**Kind:** Design / execution map (RECORDED_ONLY). Implements no capability by existing.

This document merges the vision ladder, language substrate, field dual-correction law, proof program,
and gate roadmap into one followable path. **No chronos** — order is dependency, leverage, and proof.

---

## North star

```text
builder-II + CodeVault
  = bleeding-edge reconstructive intelligence for engineers, agents, and deepagents
  = inspectable fields under governance
  = never authority

Fruition
  = throwing builder-II at real repositories
    (flagship evaluation substrate: core-labs/core;
     plus multi-language targets for polyglot claims)
  = proof class U earned for registered tasks
  = F0–F1 solid; F2–F6 first-class only when dual-correction + R/D/(U) hold
```

If docs and synthetic benches look complete but engineers will not open builder-II+CodeVault for real
work, the vision is **not** successful.

---

## Axiom Zero (non-negotiable)

```text
propose → instrument → refute or confirm → amend doctrine/constants/claims
```

Exemplar: F1 enrichment scale `0.1` refuted by dominance audit → `0.001`.  
Every later field inherits this loop ([proof program](../CODE_VAULT_PROOF_PROGRAM.md)).

---

## Architecture of the intelligence upgrade

```text
                    ADR-0005 (authority boundary)
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
   Vision + Ladder      Staged acceptance     Proof program
   (destination)        (what exists)         (R / D / U)
         │                    │                    │
         └──────────────┬─────┴──────────┬─────────┘
                        ▼                ▼
              Language substrate   Field blueprints
              (Artifact IR +       (dual correction)
               Grade IR)
                        │
                        ▼
              Roadmap gates G0…G7
                        │
                        ▼
         builder-II CLI / prepare-package / agents / deepagents
         consume reconstructed context — never as authority
```

**LNIR:** Artifact IR (primary, inspectable) + Grade IR (optional lifts only).  
Never: grades as the only IR; Python AST as global ontology; embeddings as structure.

---

## Document set (official)

| Doc | Role |
|---|---|
| [`../CODE_VAULT_VISION_AND_CAPABILITY_LADDER.md`](../CODE_VAULT_VISION_AND_CAPABILITY_LADDER.md) | Destination, axioms, ladder |
| [`../CODE_VAULT_GLOSSARY.md`](../CODE_VAULT_GLOSSARY.md) | Vocabulary lock |
| [`../CODE_VAULT_PROOF_PROGRAM.md`](../CODE_VAULT_PROOF_PROGRAM.md) | Claim law |
| [`../CODE_VAULT_LANGUAGE_SUBSTRATE.md`](../CODE_VAULT_LANGUAGE_SUBSTRATE.md) | Polyglot fortification |
| [`../CODE_VAULT_FIELD_BLUEPRINTS.md`](../CODE_VAULT_FIELD_BLUEPRINTS.md) | Dual-correction blueprints |
| [`../CODE_VAULT_ROADMAP.md`](../CODE_VAULT_ROADMAP.md) | Gates |
| [`../CODE_VAULT_CURRENT_STATE_AND_GAP_MAP.md`](../CODE_VAULT_CURRENT_STATE_AND_GAP_MAP.md) | Three-clock truth |
| [`../CODE_VAULT_STAGED_ACCEPTANCE.md`](../CODE_VAULT_STAGED_ACCEPTANCE.md) | Existence ledger |
| [`../CODE_VAULT.md`](../CODE_VAULT.md) | Operator surface today |
| [`../adrs/ADR-0005-codevault-boundary-and-authority.md`](../adrs/ADR-0005-codevault-boundary-and-authority.md) | Boundary law |
| [`CODE_VAULT_TIER1_ENCODER_RFC.md`](CODE_VAULT_TIER1_ENCODER_RFC.md) | F1 measurement history |
| **This file** | Consolidated path |

---

## Gate graph (execution order)

| Gate | Name | Unlocks claims | Proof |
|---|---|---|---|
| **G0** | Foundation F0–F1 | Layout + identity at ledger states | Done |
| **G1** | ExtractorManifest + IR stubs | Declared extractors; no fabricated structure | R |
| **G1b** | Scale / scope honesty | Honest real-repo indexing | R |
| **G2** | StructuralField + Python extractor v1 | Structure candidates (hypothesis) | R+D |
| **G3** | Second-language extractor skeleton | Polyglot coverage honesty | R |
| **G4** | RelationField | Relation/impact candidates (hypothesis) | R+D |
| **G5** | Real-repo utility harness | "Helps engineering" for scoped suite | **U** |
| **G6** | Evidence protocol + reconstruction depth | Correctable findings; task packs with omissions | R (+U for product language) |
| **G7** | ChangeField | Lineage / calibrated history stories | R+D (+U for risk claims) |

**Parallel:** docs truth, ADR pins, staged-acceptance rows — never a substitute for G5.

**HITL:** authority-adjacent or doctrine-amending gates stop for human approval per builder-II norms.

---

## Implementation principles

1. **Artifact IR before grade lifts** for F2/F3.  
2. **Python proves the extractor path; schemas stay language-neutral.**  
3. **Second language skeleton before deep multi-lang structure claims.**  
4. **Do not overload `validation_rs` or `core_rs` as source extractors.**  
5. **Provenance skeleton from G1** — full F4 later.  
6. **Dual correction mandatory** on every first-class field.  
7. **U is a claim gate** — R/D work may precede; product language may not.  
8. **Severability** of `builder_ii/code_vault/` preserved.  
9. **Agents/deepagents** receive reconstructed context under policy — CodeVault never becomes their execution authority.

---

## Success criteria (falsifiable)

Fruition is achieved when:

1. An engineer chooses **builder-II + CodeVault** for real development tasks (including CORE engineering sessions) because reconstructions and field signals help.  
2. Registered **U** suite passes for declared scopes (artifacts + operator rubric).  
3. Language readiness matrix is honest; multi-lang claims match extractor reality.  
4. Ladder "Implemented" rows still bind to staged-acceptance states — not promotion theater.  
5. ADR-0005 pins remain green; no authority creep.  
6. Axiom Zero is visible in the history of constants/schemas (refutations recorded, not buried).

---

## Explicit non-goals (this plan)

- Replacing CORE's own vault/cognition runtime.  
- CodeVault as autonomous engineer or patch authority.  
- Embedding / ANN / cosine "structure."  
- Calendar roadmaps.  
- Promotion by documentation alone.

---

## Suggested first execution slice (after HITL)

1. Keep this vision set as source of planning truth.  
2. Implement **G1** (manifest + stubs) and **G1b** (scope honesty) as code PRs.  
3. Then **G2** StructuralField with TDD.  
4. Do not claim U until **G5**.

---

## Related platform

- [`../MANIFESTO.md`](../MANIFESTO.md) — Signet  
- [`../CAPABILITY_PROMOTION.md`](../CAPABILITY_PROMOTION.md) — eight gates  
- [`MASTERPIECE_PLAN.md`](MASTERPIECE_PLAN.md) — broader builder-II mastery context (Goose/deepagents); CodeVault is the intelligence substrate within that arc  
