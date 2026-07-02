# GitHub Branch Protection Requirements

> [!IMPORTANT]
> GitHub branch protection is an external repository-level setting managed on GitHub.com. It is NOT a code-level guarantee and cannot be fully enforced by files within the repository.

To enforce the integrity of the `main` branch, repository administrators should ensure that the following branch protection settings or rulesets are configured for `main`.

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
