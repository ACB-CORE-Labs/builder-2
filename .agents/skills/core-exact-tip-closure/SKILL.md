---
name: core-exact-tip-closure
description: EXACT-TIP SCIENTIFIC CLOSURE workflow. Use as the mandatory final gate before push/PR. Enforces the ordered closure sequence that makes premature, rewrapped, or faked qualification structurally hard.
---
# EXACT-TIP SCIENTIFIC CLOSURE

## Ordered sequence (do not reorder; each step gates the next)
1. code settled
2. focused tests pass
3. adversarial lesions pass
4. commit
5. verify clean exact tip
6. freeze manifest/methodology
7. perform the actual required observation (real seam; UNAVAILABLE if not exercisable)
8. seal raw evidence
9. derive report
10. independently validate
11. full receipt-backed CI
12. verify HEAD unchanged since measurement
13. clean tree
14. push
15. PR update
16. final review (final-closure-reviewer agent)
17. STOP

## Guards
- If HEAD changed after step 7, the measurement is invalid → return to step 4.
- If the real seam is unavailable at step 7 → STOP, report UNAVAILABLE. No proxy.
- Only final-closure-reviewer may emit CLOSURE: PASS.