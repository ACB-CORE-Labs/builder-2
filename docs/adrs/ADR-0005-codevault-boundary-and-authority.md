# ADR-0005: CodeVault Boundary and Authority

## Status

Accepted (2026-07-10).

## Vocabulary note (2026-07-10)

This ADR predates the vision set's vocabulary lock
([`CODE_VAULT_GLOSSARY.md`](../CODE_VAULT_GLOSSARY.md)): where the text below says "Tier-6
reconstruction," "Tier-0 layout map," or "roadmap Tier 5," read capability **fields** F6 / F0 / F5
(the evidence generalization now lands at gate G6). "Tier" is reserved for command authority and
the enrichment encoder block. The decision itself is unchanged by this note.

## Context

CodeVault began as a staged, artifact-only software-geometry subsystem and is growing toward the
capability ladder in [`CODE_VAULT_VISION_AND_CAPABILITY_LADDER.md`](../CODE_VAULT_VISION_AND_CAPABILITY_LADDER.md):
layout, exact identity, structure, relations, change, evidence, reconstruction. Each tier makes its
output more persuasive — a reconstruction that names impacted tests and historical risk *reads like a
verdict* even when it is a hypothesis.

That creates a specific failure mode: authority creep by usefulness. A finding gets treated as a
verification result; a context pack gets treated as an approval input; the receipt bridge gets treated
as a promotion mechanism. None of those steps would require anyone to *decide* to grant CodeVault
authority — each is one habit away. The boundary therefore has to be a recorded decision with
enforcement, not scattered prose.

builder-II already draws this line for its other substrates: Goose and deepagents are governed
adapters underneath the policy/artifact/HITL boundary, never parallel authorities. CodeVault is the
same kind of thing on the intelligence axis.

## Decision

We establish the following platform relationship without conflation:

```text
builder-II
  Governs targets, profiles, policy, approval, execution, verification,
  receipts, rollback, handoff, and capability promotion.

CodeVault
  Constructs fields, retrieves/reconstructs context, emits hypotheses,
  and consumes independent evidence through governed artifacts.

No CodeVault output grants execution or promotion authority.
```

The intelligence of a CodeVault output never changes its authority. A Tier-6 reconstruction carries
exactly the authority of a Tier-0 layout map: none.

## Consequences

- CodeVault findings are hypotheses (`status=hypothesis`, `severity=review`) and remain so until
  independently corroborated — and corroboration classifies, it does not promote.
- The receipt bridge classifies a finding's relationship to a verification chain
  (corroborated / uncorroborated / refuted / blocked) without mutating the finding or granting
  authority. Its `RECORDED_ONLY` model is the baseline for all future evidence correction (roadmap
  Tier 5), not a temporary inconvenience.
- CodeVault retains no direct route to command execution, approval, verification pass/fail,
  promotion, or repository mutation.
- Rollback for every CodeVault layer is deleting emitted JSON artifacts; no layer mutates a target
  repository.
- Relationship to Codename Goose and CORE: CodeVault starts no runtime and is Goose-independent;
  CORE appears only as a target profile and as the optional `core_rs` recall backend behind explicit
  selection with recorded `pure_numpy` fallback. No CORE Workbench coupling.
- If CodeVault is ever packaged commercially, its paid value must be empirical capability — never a
  withheld or bypassed builder-II governance core (see the vision document's "Definition of shines").

## Acceptance criteria

The boundary is enforced, not asserted. Existing enforcement this ADR is accountable to:

- `tests/test_code_vault_no_runtime_authority.py` — no runtime/authority leak from the recall path.
- `tests/test_code_vault_findings.py` — findings carry `status=hypothesis`, `severity=review`, and
  cannot claim verification.
- `tests/test_code_vault_receipt_bridge.py`, `tests/test_code_vault_receipt_bridge_cli.py` — the
  corroboration bridge re-derives from sources and emits classifications without mutating findings.
- `tests/test_code_vault_context_bridge.py` — bounded projection, `agent_authority` DISABLED,
  `artifact_is_authority` false.
- `tests/test_command_authority.py` — `builder-code-vault` stays Tier 1 artifact-only in the command
  authority registry.
- The per-layer ledger in [`CODE_VAULT_STAGED_ACCEPTANCE.md`](../CODE_VAULT_STAGED_ACCEPTANCE.md),
  which records every layer's capability state, failure mode, rollback path, and verification path.

A future tier that cannot name its equivalent of these pins has not met this ADR.

## Related vision set

- [`../CODE_VAULT_VISION_AND_CAPABILITY_LADDER.md`](../CODE_VAULT_VISION_AND_CAPABILITY_LADDER.md) — destination and ladder  
- [`../CODE_VAULT_PROOF_PROGRAM.md`](../CODE_VAULT_PROOF_PROGRAM.md) — claim classes R / D / U  
- [`../CODE_VAULT_LANGUAGE_SUBSTRATE.md`](../CODE_VAULT_LANGUAGE_SUBSTRATE.md) — polyglot substrate law  
- [`../CODE_VAULT_FIELD_BLUEPRINTS.md`](../CODE_VAULT_FIELD_BLUEPRINTS.md) — dual correction  
- [`../plan/CODE_VAULT_MASTER_PLAN.md`](../plan/CODE_VAULT_MASTER_PLAN.md) — path to fruition  

Intelligence never changes authority: a future reconstruction carries the same authority as a layout
map — none.
