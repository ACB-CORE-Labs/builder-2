# Branch protection requirements (Forgejo primary + GitHub mirror notes)

> [!IMPORTANT]
> **builder-II is Forgejo-primary** (`core-labs/builder-II`). Branch protection is an
> external repository-level setting. It is NOT a code-level guarantee and cannot be fully
> enforced by files within the repository.
>
> When the Forgejo Actions / Act runner is offline or not a required check, **local
> `bash scripts/ci.sh --receipt .builder/artifacts/gate-battery-receipt.json` is the
> merge evidence**. Attach the receipt path + HEAD digest in the PR body.

## Forgejo (source of truth)

Administrators should configure branch protection / rulesets on Forgejo `main` to:

1. Require pull requests before merge (no direct push to `main`).
2. Prefer required status check `high-assurance-gates` when the runner is healthy.
3. Block force pushes and branch deletion on `main`.
4. When the runner is down: require human review + gate battery receipt artifact.

### Operator-ready Forgejo API payload

Apply with an **admin** token (`FORGEJO_ADMIN_TOKEN`, never committed). The status-check
context must match the exact context string Forgejo Actions reports on a recent `main`
commit (shape: `CI / high-assurance-gates (push)` — check a recent commit's status list,
or use a glob pattern as below):

```bash
curl -sS -X POST \
  -H "Authorization: token ${FORGEJO_ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  "https://core-gitquarters.acbcontent.org/api/v1/repos/core-labs/builder-II/branch_protections" \
  -d '{
    "branch_name": "main",
    "enable_push": false,
    "enable_status_check": true,
    "status_check_contexts": ["CI / high-assurance-gates*"],
    "block_on_outdated_branch": false,
    "required_approvals": 1,
    "block_on_rejected_reviews": true,
    "dismiss_stale_approvals": true
  }'
```

Notes:
- A protected branch in Forgejo blocks force pushes and deletion by construction; no
  separate toggles are needed.
- `block_on_outdated_branch` stays `false` while the runner is a single local Mac queue —
  strict up-to-date requirements + a sleeping runner would deadlock merges. Flip to
  `true` once the runner is continuously available.
- Verify afterwards: `GET .../branch_protections` should list the `main` rule, and a PR
  with a red or absent `high-assurance-gates` status must show merge blocked.
- When the runner is asleep, the documented fallback stands: human review + a
  `gate_battery_receipt` artifact bound to the PR HEAD.

## GitHub mirror (if present)

GitHub.com settings below are **not** the deploy authority for CORE-primary repos; they
apply only if a GitHub mirror is used. Use Forgejo admin UI / API for the primary host.

# GitHub Branch Protection Requirements (mirror only)

To enforce the integrity of the `main` branch on a GitHub mirror, repository administrators should ensure that the following branch protection settings or rulesets are configured for `main`.

## Recommended Settings
1. **Require Pull Requests before merging**:
   - Require at least **1 review approval** before merging (if organization/repo settings permit).
   - Dismiss stale pull request approvals when new commits are pushed.
2. **Require status checks to pass before merging**:
   - Require branch to be up to date before merging (Strict mode).
   - **Required Status Check**: `high-assurance-gates` (must pass successfully).
3. **Block Force Pushes**:
   - Do not allow force pushes (disabled for all users, including administrators).
4. **Block Branch Deletion**:
   - Prevent the `main` branch from being deleted.
5. **Preserve Merge Commits**:
   - Do not force linear history unless specifically requested. builder-II intentionally preserves merge commits where appropriate.

---

## Dry-run Payload

The following JSON payload describes the exact settings payload required by the GitHub API. 

```json
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["high-assurance-gates"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
```

## Operator Verification & Application (Manual)

To inspect the current branch protection settings, run:
```bash
gh api repos/AssetOverflow/builder-II/branches/main/protection
```

To manually update the settings using the dry-run payload (if authorized and possessing admin credentials), run:
```bash
gh api -X PUT repos/AssetOverflow/builder-II/branches/main/protection \
  -H "Accept: application/vnd.github+json" \
  -F "required_status_checks[strict]=true" \
  -F "required_status_checks[contexts][]=high-assurance-gates" \
  -F "enforce_admins=true" \
  -F "required_pull_request_reviews[required_approving_review_count]=1" \
  -F "required_pull_request_reviews[dismiss_stale_reviews]=true" \
  -F "restrictions=null"
```
