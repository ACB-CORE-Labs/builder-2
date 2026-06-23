---
name: core-pre-edit-sweep
description: Before editing CORE sensitive modules, trace imports and all call sites across algebra, field, generate, vault, cognition, teaching, calibration.
---

# Pre-Edit Sweep

Before any edit in `algebra/`, `field/`, `generate/`, `vault/`, `core/cognition/`, `teaching/`, `calibration/`:

1. Read the full target module
2. Search imports and callers of changed symbols
3. Check `calibration/` and `evals/` for paths exercising the change
4. Confirm `versor_condition(F) < 1e-6` preserved
5. Only then propose [SPECULATIVE] edits