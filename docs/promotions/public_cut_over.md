# Transition Runbook: Public / Open-Source Cut-over

## 1. Executive Summary
This runbook outlines the critical decisions, readiness checks, and rollback plans for the **Public/Open-Source Cut-over**. This is a highly sensitive promotion that transitions internal proprietary components of the architecture into a public-facing, open-source repository state, requiring stringent security and licensing reviews.

## 2. Readiness Records
### 2.1 Capability Gap Addressed
- Blocked capability: Public / Open-Source Cut-over.
- Status: **Pending Approval**
- Tracker Reference: `BUILDER-II-TRK-B4`
- License chosen: **MIT** (2026-07-27; see [`LICENSE`](../../LICENSE) and
  [`NOTICE.md`](../../NOTICE.md)). This is the license decision itself, not the audit below — that
  remains unchecked until actually performed. The copyright holder recorded in `LICENSE` is
  provisional (an individual, pending formation of a formal entity) and may be reassigned without
  changing the license terms.

### 2.2 Validation Checklist
- [ ] **Secret Scanning**: Executed deep history rewrites (e.g., BFG Repo-Cleaner) and automated scans (TruffleHog, Gitleaks) to ensure 0 leaked internal secrets, API keys, or proprietary internal IP addresses.
- [ ] **Licensing Audit**: Confirmed all headers, dependencies, and included assets comply with the chosen license (MIT, chosen — see 2.1). CodeVault (`builder-ii-code-vault`) is a separate, commercially licensed repository and is out of scope for this audit.
- [ ] **Documentation**: Verified that `README.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and architecture diagrams are scrubbed of internal jargon and are ready for community consumption.
- [ ] **CI/CD Separation**: Ensured that the public repository has its own isolated GitHub Actions/CI pipelines that do NOT have access to internal deployment environments.
- [ ] **Legal Approval**: Final sign-off received from Open Source Compliance and Legal teams.

## 3. Promotion Steps

The intended end state is dual-hosted and public on both remotes: `core-labs/builder-II` on the
private Forgejo instance (`core-gitquarters.acbcontent.org`) and the GitHub mirror
(`AssetOverflow/builder-II`) — see [`docs/README.md`](../README.md) for which remote is
authoritative for which repository class. Both need their own visibility toggle; toggling one does
not toggle the other.

1. **Repository Mirroring / History Prep**: Decide the git-history strategy (fresh-start vs. full
   history) before either remote goes public — this is irreversible once public and forkable.
2. **Final Automated Scan**: Run a final, synchronous security scan (secrets, PII in commit
   history/authorship) on the branch/history that will actually be published.
3. **Visibility Toggle**: Change repository visibility from `Private` to `Public` on **both**
   `core-gitquarters.acbcontent.org` and GitHub. Operator-executed only; not something an agent has
   authority to do (see [`docs/BETA_CHARTER.md`](../BETA_CHARTER.md)).
4. **Announcement**: Publish the release notes, blog posts, and community announcements.
5. **Community Onboarding**: Activate community issue templates and open the repository for external Pull Requests.

## 4. Rollback Story
If a critical leak, licensing violation, or security vulnerability is discovered immediately post-cut-over:
1. **Emergency Privatization**: Immediately toggle the repository visibility back to `Private`. If the platform prevents this due to forks, contact support for an emergency takedown.
2. **Credential Rotation**: Rotate ANY and ALL internal credentials, API keys, or certificates that may have been inadvertently exposed, assuming they are compromised.
3. **Damage Assessment**: Analyze clone traffic and fork networks to assess the spread of the exposed data.
4. **Scrub and Relaunch**: Perform the necessary history scrubs and legal reviews before attempting a second cut-over.
