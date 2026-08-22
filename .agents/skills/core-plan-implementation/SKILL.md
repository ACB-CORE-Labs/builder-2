---
name: core-plan-implementation
description: BUILDER-II plan→implementation workflow. Use when starting a non-trivial change: runs reconnaissance, produces an implementation plan, then applies scoped edits and immediate tests. Keeps implementation fast and grounded.
---
# BUILDER-II PLAN IMPLEMENTATION

## When to use
Starting any non-trivial change in builder-II.

## Steps
1. Reconnaissance — map the target module; name the authoritative abstraction, caller, validator, command surface, artifact schema, test seam, authority boundary. (Use /core-pre-edit-sweep.)
2. Plan — short implementation plan: targeted files, dependencies, logic changes, test to add. Confirm before editing.
3. Implement — scoped edits; inspect signatures/schemas first; extend existing abstractions.
4. Lesion — add a focused regression test around the concrete defect.
5. Test — run the narrowest relevant test immediately.
6. Iterate — through compiler/type/test failures to green.
7. Hand off — do NOT claim done. /agents → evidence-auditor, then final-closure-reviewer.

## Bias
Fast, grounded, scoped. No parallel systems. No fabricated schemas/signatures.