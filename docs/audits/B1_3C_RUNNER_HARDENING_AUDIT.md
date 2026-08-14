# B1.3C Runner Hardening Audit

## Source

This hardening slice responds to the post-B1.3A/B adversarial audit of the verification execution surface.

## Verdict

The audit blocked B1.4 until three B1.3B governance gaps were remediated:

1. `builder-verify run-approved` could continue toward execution when schema-valid plan or approval artifacts had `valid=false`.
2. The bounded runner environment preserved `PATH` by copying the full ambient environment, which could forward secrets or model/MCP credentials.
3. Receipt output paths were only rejected when inside the target repository but outside the artifact root, allowing out-of-tree writes.

## Remediation

This slice hardens the B1.3B runner without adding new execution authority:

- requires referenced plan and approval artifacts to have `valid=true` before subprocess execution is considered;
- preserves only an explicit safe environment allowlist plus required bounded runner variables;
- strips ambient secrets such as model provider keys, GitHub tokens, and cloud secret keys from child subprocess environments;
- requires receipt output paths to resolve under the configured artifact root;
- avoids writing blocked receipts to unsafe output paths;
- adds regression coverage for invalid plan/approval artifacts, stripped secrets, and unsafe output confinement.

## Non-goals

This slice does not expand command profiles, add arbitrary argv, enable shell execution, grant patch/source/git/model/MCP/Goose/deepagents/B2 authority, or implement B1.4 ledger/replay.
