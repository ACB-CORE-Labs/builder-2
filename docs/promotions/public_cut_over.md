# Transition Runbook: Public / Open-Source Cut-over

## 1. Executive Summary
This runbook outlines the critical decisions, readiness checks, and rollback plans for the **Public/Open-Source Cut-over**. This is a highly sensitive promotion that transitions internal proprietary components of the architecture into a public-facing, open-source repository state, requiring stringent security and licensing reviews.

## 2. Readiness Records
### 2.1 Capability Gap Addressed
- Blocked capability: Public / Open-Source Cut-over.
- Status: **Pending Approval**
- Tracker Reference: `BUILDER-II-TRK-B4`

### 2.2 Validation Checklist
- [ ] **Secret Scanning**: Executed deep history rewrites (e.g., BFG Repo-Cleaner) and automated scans (TruffleHog, Gitleaks) to ensure 0 leaked internal secrets, API keys, or proprietary internal IP addresses.
- [ ] **Licensing Audit**: Confirmed all headers, dependencies, and included assets comply with the chosen open-source license (e.g., Apache 2.0 or MIT).
- [ ] **Documentation**: Verified that `README.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and architecture diagrams are scrubbed of internal jargon and are ready for community consumption.
- [ ] **CI/CD Separation**: Ensured that the public repository has its own isolated GitHub Actions/CI pipelines that do NOT have access to internal deployment environments.
- [ ] **Legal Approval**: Final sign-off received from Open Source Compliance and Legal teams.

## 3. Promotion Steps
1. **Repository Mirroring**: Create a clean, squashed mirror of the internal repository targeting the public GitHub organization.
2. **Final Automated Scan**: Run a final, synchronous security scan on the mirrored staging branch.
3. **Visibility Toggle**: Change the repository visibility settings on GitHub from `Private` to `Public`.
4. **Announcement**: Publish the release notes, blog posts, and community announcements.
5. **Community Onboarding**: Activate community issue templates and open the repository for external Pull Requests.

## 4. Rollback Story
If a critical leak, licensing violation, or security vulnerability is discovered immediately post-cut-over:
1. **Emergency Privatization**: Immediately toggle the repository visibility back to `Private`. If the platform prevents this due to forks, contact support for an emergency takedown.
2. **Credential Rotation**: Rotate ANY and ALL internal credentials, API keys, or certificates that may have been inadvertently exposed, assuming they are compromised.
3. **Damage Assessment**: Analyze clone traffic and fork networks to assess the spread of the exposed data.
4. **Scrub and Relaunch**: Perform the necessary history scrubs and legal reviews before attempting a second cut-over.
