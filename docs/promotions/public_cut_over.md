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
- [x] **Secret Scanning**: `gitleaks detect --source . --log-opts="--all"` (v8.30.1) against the
  full history reachable from every ref (1,217 commits, ~20.9MB scanned), 2026-07-27. One finding:
  a `ghp_`-shaped token in `tests/test_content_read_receipts.py` — a deliberately fake, sequential
  fixture value used to test the repo's own secret-redaction logic, matching this repo's documented
  convention that `tests/` and `docs/` carry illustrative fake keys by design (`scripts/
  secret_scan.py`'s own `EXCLUDED_PREFIXES`). Not a real credential. **This scan covers the
  current default branch's full history; it does not by itself clear step 3.1 below** — see the
  history-exposure finding there before deciding the publish strategy.
- [x] **Licensing Audit**: `pip-licenses` against all 51 installed dependencies, 2026-07-27 — zero
  GPL/AGPL/LGPL/SSPL/BUSL/Commons-Clause licenses. One package (`rich-pixels`) reported `UNKNOWN`
  due to missing PyPI metadata on the upstream package's part; confirmed MIT directly from its
  GitHub repository. CodeVault (`builder-ii-code-vault`) is a separate, commercially licensed
  repository and stays out of scope for this audit.
- [ ] **Documentation**: `README.md` and `CONTRIBUTING.md` reviewed clean — no internal domains,
  personal emails, or local paths found (`grep` swept for `acbcontent.org` account addresses,
  `@icloud.com`/`@gmail.com`, and `/Users/` paths across all public-facing docs; none present).
  **Not yet ready**: `CODE_OF_CONDUCT.md`'s Enforcement section still has no real reporting
  contact — its broken pointer to a nonexistent `docs/ROADMAP.md` section is fixed, but the actual
  contact (an email or form) is a decision only the operator can make, not something to invent.
- [x] **CI/CD Separation**: Read `.github/workflows/ci.yml` directly, 2026-07-27 — zero `secrets.*`
  references, zero deploy/publish steps; the job does exactly checkout → provision (rust/uv/python)
  → run `scripts/ci.sh` → upload the gate-battery receipt as a build artifact. There is no
  "internal deployment environment" in this project's architecture for a public pipeline to reach
  into — this checklist line is boilerplate that doesn't map onto a local-tool project, not an
  unmet requirement.
- [ ] **Legal Approval**: Requires an actual decision by the operator (and, if desired, outside
  counsel) — not something that can be produced by an audit. No concrete legal red flags surfaced
  during this pass (trademark, embedded proprietary snippets, or similar); that is not the same
  as sign-off.

## 3. Promotion Steps

The intended end state is dual-hosted and public on both remotes: `core-labs/builder-II` on the
private Forgejo instance (`core-gitquarters.acbcontent.org`) and the GitHub mirror
(`AssetOverflow/builder-II`) — see [`docs/README.md`](../README.md) for which remote is
authoritative for which repository class. Both need their own visibility toggle; toggling one does
not toggle the other.

1. **Repository Mirroring / History Prep**: Decide the git-history strategy (fresh-start vs. full
   history) before either remote goes public — this is irreversible once public and forkable.
   **Blocked on a concrete finding, not a hypothetical one**: CodeVault's complete source —
   every module under `builder_ii/code_vault/` (geometry engine, extractor, recall, hierarchy,
   linter, the full `docs/CODE_VAULT_*.md` design-doc set, and its entire test suite) — was
   deleted from the tracked tree on 2026-07-15 (commit `336ecd0`) when it was separated into the
   commercial `builder-ii-code-vault` repository, but it was **deleted, not rewritten out of
   history**. Confirmed by direct retrieval (`git show 336ecd0^:builder_ii/code_vault/geometry/
   cl41.py`, among others) that the full pre-separation tree is still reachable from any full
   clone. Publishing this repo with its current full history would hand out the paid plugin's
   complete source for free, one `git log`/`git show` away — this directly contradicts the
   "keep CodeVault severable as a paid tier" decision this whole separation was done to protect.
   **A fresh-start history (or a targeted rewrite removing every `code_vault`-touching commit) is
   required before publishing, not merely one of two acceptable options** — and either one is a
   destructive, hard-to-reverse operation on the canonical history, so it needs your explicit
   go-ahead and choice of approach, not an agent picking one and running it.
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
