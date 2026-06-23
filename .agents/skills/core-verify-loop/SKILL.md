---
name: core-verify-loop
description: Autonomous edit-test-fix loop for CORE. Write change, run builder verify, read failure output, fix upstream, re-run until PASS or human needed.
---

# CORE Verify Loop

1. Identify target module and suite (`builder verify <path>` auto-routes)
2. Make minimal [SPECULATIVE] change
3. Run verification:
   ```bash
   builder verify <module_path>
   ```
4. On FAIL: read tail output; diagnose upstream operator — never patch tests to green; never add forbidden patterns
5. Re-run until PASS
6. Report exact pytest summary line

Never add normalization, ANN, or hot-path repair to pass tests.