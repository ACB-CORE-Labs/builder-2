# GitHub branch protection requirements

> [!IMPORTANT]
> `ACB-CORE-Labs/builder-2` is the canonical upstream. Branch protection is an
> external repository setting, not a code-level guarantee. Local `bash scripts/ci.sh`
> remains the authoritative pre-push verification gate.

Administrators should protect `main` with:

1. Pull requests required before merge; direct pushes disabled.
2. At least one approving review, with stale approvals dismissed after new commits.
3. The `high-assurance-gates` status check required before merge.
4. Force pushes and branch deletion disabled.
5. A human review plus a locally generated gate-battery receipt when hosted checks are
   unavailable. The receipt must bind to the exact PR head.

## Operator verification

```bash
gh api repos/ACB-CORE-Labs/builder-2/branches/main/protection
```

Applying branch protection or changing repository settings is an administrator action and
is outside this local Plan Set 0 implementation.
