# Local merge verification policy

> [!IMPORTANT]
> `ACB-CORE-Labs/builder-2` is the canonical upstream. GitHub-hosted workflows and
> status checks are intentionally not used. Local `bash scripts/ci.sh` remains the
> authoritative pre-push and pre-merge verification gate.

Repository maintainers should protect `main` with:

1. Pull requests required before merge; direct pushes disabled.
2. Human review when desired; no paid GitHub review/check service is required.
3. Force pushes and branch deletion disabled.
4. A locally generated gate-battery receipt bound to the exact PR head before merge.

## Operator verification

The merge record must include the exact commit, `bash scripts/ci.sh` result, and receipt
path or digest. GitHub is used only for source hosting and explicitly authorized PR
creation/merge; it is not a test executor.
