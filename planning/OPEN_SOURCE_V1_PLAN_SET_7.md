# Plan Set 7 — Release Proof and Open-Source v1

STATUS: `PLANNED_ONLY_AWAITING_DIGEST_BOUND_HITL_APPROVAL`

## Exact current-base binding

This passive plan is bound to the refreshed hosted Set-6 merge:

```text
CANONICAL_REPOSITORY = https://github.com/ACB-CORE-Labs/builder-2
REMOTE               = origin
BASE_SHA              = 70d5d508eda036b969f6f63f7667985b5399e818
BASE_PARENTS          = a8d926d557e357e21d54e925f1afc76f0bad4c12
                        ff94e6e2524bd8638822c4a0c2a62665fd8317fe
BASE_TREE             = e036060b7606ef5f6496778da32546618697dbe2
BASE_SUBJECT          = Merge pull request #19 from ACB-CORE-Labs/codex/plan-set-6
AUDIT_DATE            = 2026-08-23
```

`origin/main` was refreshed and independently read back at those exact values.
The pre-existing primary checkout is a dirty historical `main`; it was not
stashed, reset, rebased, or reused. This audit was performed in an isolated
worktree created directly from `BASE_SHA`.

This artifact authorizes no implementation, test execution with external
effects, Git/GitHub mutation, capability promotion, tag creation, package
publication, release creation, or rehearsal-PR cleanup. It is the final major
planning artifact in the canonical open-source-v1 completion sequence.

## Governing release claim

Set 7 is release qualification, not another broad feature tranche. The release
claim has one shape:

```text
exact source + lock + built distributions
  -> candidate installs on fresh supported hosts
  -> golden path and integrated sabotage evidence
  -> exact-tip local CI and existing benchmark evidence
  -> one validated release-proof bundle
  -> human capability-promotion decision
  -> separate human tag/publication authorization
```

This strengthens `planned != executed != verified != promoted` and
`artifact != authority`. A wheel is not installation evidence; a passing test
on a development checkout is not release evidence; a release-proof bundle is
not promotion; promotion is not authorization to tag or publish.

## Current-base audit: reuse, repair, and genuinely missing proof

### Reuse without replacement

1. **Canonical contract.** `docs/plan/OPEN_SOURCE_V1_COMPLETION_PLAN.md`
   already defines macOS Apple Silicon and Linux as the supported v1 hosts,
   keeps Windows/WSL2 unsupported, requires wheels, both fresh installs, the
   sabotage list, an exact-candidate bundle, and human promotion/publication
   boundaries.
2. **Packaging foundation.** `pyproject.toml` already uses
   `setuptools.build_meta`, declares package `builder-ii`, pins Python
   `>=3.12.13,<3.13`, discovers `builder_ii*`, and separates the bounded
   `deepagents` extra from the Apple-only `mlx`/`apple` extras. `uv.lock` is the
   canonical dependency lock. These are foundations to qualify, not evidence
   that a wheel contains every runtime asset or installs correctly.
3. **Golden-path harness.** `scripts/clean-clone-smoke.sh` already performs a
   clean clone, platform/setup audits, first-run checks, and the real generic
   `propose -> approve -> verify -> apply -> approve rollback -> rollback`
   loop. It correctly selects MLX only on Darwin arm64 and otherwise uses the
   ordinary sync path. Preserve its scenario and failure-log behavior.
4. **Linux/local-CI substrate.** `scripts/ci-in-container.sh` already provisions
   a real Linux container and runs `scripts/ci.sh --receipt ...` against the
   exact mounted worktree. `scripts/ci.sh` is the sole blocking local gate
   battery and explicitly rejects hosted-workflow/status-check authority.
5. **Existing integrated and refusal evidence.** Sets 1–6 already own approval,
   command-authority, verification, patch/apply/rollback, Deep Agents
   interrupt/resume, Goose/MCP, budget, model gateway, benchmark, delivery,
   remote-custody, forbidden-push, and corrective-delivery tests and receipts.
   Set 7 must compose selected real lanes and validators; it must not duplicate
   their artifact vocabularies or reimplement their executors.
6. **Demo and performance sources.** The flagship/golden-path scripts and docs
   provide rehearsal inputs. The Plan-5 `m1-v1` benchmark contract and physical
   `/usr/bin/footprint` evidence remain the performance authority; Set 7 binds
   their admitted receipts and digests rather than rerunning or weakening the
   benchmark without a concrete invalidation.
7. **Release evidence primitives.** The artifact index, chain verification,
   standard governance block, gate-battery receipt, exact Git-state capture,
   repository-identity check, and existing validators are the canonical
   primitives for a release bundle.

### Repair on the current base

1. **Historical V0 release truth is false for v1.**
   `builder_ii/core/release_manifest.py` hard-codes kind
   `builder_ii.v0_release_manifest`, repository `AssetOverflow/builder-II`,
   lineage `v0 release lineage`, and default version `v0.1.0`. Its proof status
   can express only no-runtime/no-write passive-chain claims.
   `scripts/verify_v0_release.py` calls itself the anti-handwave V0 harness,
   prints the stale repository, and proves only the earlier passive prepare
   package/spine. This family must be migrated into the canonical v1
   release-proof owner, not retained as a competing release truth system.
2. **Generated completion truth is stale.** The typed source in
   `builder_ii/core/platform_completion_audit.py` still describes release proof
   as passive and waiting for B1, and its human summary still says commit/push
   automation is unpromoted. `builder_ii/lifecycle/setup/known_limitations.py`
   generates “No commit or push automation, ever” and the committed
   `docs/KNOWN_LIMITATIONS.md` repeats it, despite Set 6's separately approved
   delivery lanes. Several older blockers also say verification, Goose, MCP,
   Deep Agents, and operator-loop work is missing after those lanes exist.
   Repair the typed rows/blockers/summary first, regenerate all derived docs,
   and preserve honest assurance distinctions. Do not hand-edit generated
   output and do not promote a row merely to make prose green.
3. **Public installation truth is checkout-centric.** `README.md`,
   `FIRST_SESSION.md`, and STRATUM docs primarily describe `uv sync` in a source
   checkout. They do not document or prove `uv tool install` from the candidate
   wheel, and current non-Mac wording still calls Linux parity post-beta.
4. **Release-facing historical audits remain discoverable as present truth.**
   Files such as `docs/RUNTIME_GOVERNANCE_RELEASE_AUDIT.md`,
   `docs/BUILDER_PLATFORM_RELEASE_AUDIT.md`, old release tests, and
   `scripts/capture_hardening_evidence.py` contain intentionally historical
   no-runtime/old-upstream assertions. Classify them explicitly as immutable
   historical evidence, revise their current-facing framing, or retire their
   release authority; do not silently rewrite sealed evidence.
5. **Wheel contents are unproved.** Package discovery covers Python packages,
   but repository-root scripts, recipes, images, templates, and documentation
   referenced by installed commands need an inventory and installed-wheel
   test. Source-checkout success must not mask missing package data or
   `Path(__file__)` assumptions.

### Genuinely missing release proof

1. A built sdist/wheel set with recorded SHA-256 digests, metadata inspection,
   clean-install validation, and `uv tool install` smoke for base and
   `deepagents` extra.
2. A fresh Apple Silicon install from the exact candidate wheel, including the
   Apple/MLX path and the complete governed golden path.
3. A genuine Linux install from the same wheel and complete governance golden
   path. Linux need not load MLX or claim Apple performance parity.
4. One release-level successful-loop/sabotage runner that selects and composes
   existing subsystem fixtures and real canonical services while recording the
   integrated terminal behavior and artifact refs.
5. One typed exact-candidate release-proof bundle and validator binding source
   commit/tree, lock, distributions, supported runtimes, host proofs, local CI,
   docs/matrix audits, Plan-5 benchmark evidence, demo/rehearsal evidence,
   limitations, and every constituent digest.
6. A final release-candidate review packet that stops before promotion, tagging,
   GitHub Release creation, or registry publication.

## Proposed public candidate identity

No hosted tags exist at the audited base. `pyproject.toml` currently declares
`0.1.0`, while the ratified completion target is explicitly open-source v1.
Therefore the Set-7 candidate identity is:

```text
PYTHON_PACKAGE_VERSION = 1.0.0
PROPOSED_GIT_TAG       = v1.0.0
RELEASE_LINEAGE       = open-source-v1
```

This is proposed release identity, not a claim that version metadata changed or
that the tag exists. An implementation approval may authorize changing package
metadata to `1.0.0` and constructing an untagged exact candidate. It does not
authorize `git tag`, GitHub Release mutation, or package publication. Any version
change before candidate construction requires an explicit amendment to this
source-bound plan so manifests, wheels, docs, and evidence cannot disagree.

## Implementation tranches, ranked by structural leverage

### Tranche 1 — Release truth, package contract, and current documentation

Name one canonical typed family in `builder_ii/core/release_manifest.py` (or a
more accurately named replacement module) with a version-neutral implementation
and a v1 schema/kind. Prefer a migration/compatibility validator for admitted
historical V0 artifacts over keeping V0 as a second active proof owner. Update
the artifact registry and chain verifier through their existing extension
points.

The release manifest/bundle schema must bind at least:

- canonical repository, release lineage, package version, proposed tag;
- exact candidate commit, parents, tree, clean-state assertion, and source
  archive digest;
- `uv.lock` digest and declared Python/platform support;
- sdist/wheel filenames, sizes, SHA-256 digests, normalized wheel metadata, and
  package-data inventory;
- exact refs/digests for macOS, Linux, local-CI, docs, matrix, benchmark,
  sabotage, demo/rehearsal, known-limitations, and artifact-index evidence;
- recorded result states that distinguish `PASS`, `FAIL`, `SKIP`, and
  `NOT_RUN`, with no omitted required lane interpreted as green;
- governance pins stating that the bundle is evidence, not approval, promotion,
  tag authority, or publication authority.

Replace/generalize `scripts/verify_v0_release.py` into the canonical release
proof builder/validator command surface. Preserve a narrow historical V0
validation path only if repository evidence still consumes it. Remove the V0
harness from current golden-path authority once the v1 path is qualified.

Set package metadata to the approved candidate identity, inventory installed
runtime resources, and make resource lookup installation-safe. Build with the
existing backend; add only the lightest standard build tooling needed. Test both
the base install and `builder-ii[deepagents]`; Apple-only extras remain separate.

Reconcile current truth in this order:

1. update typed capability rows, blockers, assurance summaries, and current
   authority statements from actual Sets 1–6 evidence;
2. regenerate `docs/KNOWN_LIMITATIONS.md`, completion/matrix reports, and other
   source-derived docs using their canonical commands;
3. update install, five-minute start, CLI/STRATUM, Goose/Deep Agents, HITL,
   model/budget, recovery/resume, GitHub delivery, extension, supported-host,
   and release documentation;
4. pin tests to the corrected typed sources and generated bytes.

Do not compress every incomplete matrix row into `OPERATIONALLY_VERIFIED`.
Capability promotion still requires the eight gates and a later human decision.
Set 6 should be described precisely: builder-II has governed, separately
approved commit/push/PR lanes; it does not have ambient or autonomous Git
authority.

### Tranche 2 — Candidate build and two-platform installation/golden path

Refactor `scripts/clean-clone-smoke.sh` only enough to separate source acquisition
from installed command execution. Preserve its existing checkout-mode regression
lane, then add a candidate-distribution mode that:

1. verifies the supplied wheel digest before installation;
2. installs into a fresh isolated `uv tool` environment, with an explicit
   base or `deepagents` extra selection;
3. invokes installed console scripts without relying on the source checkout or
   its `.venv`;
4. executes the same platform audits and complete generic governed
   patch/apply/rollback loop;
5. records OS/architecture, Python/uv/Git/Goose/container/runtime versions,
   exact wheel identity, command results, elapsed time, skips, logs, and an
   independently validated host-proof artifact.

The macOS lane must run on real Darwin arm64 from the exact candidate wheel,
install the Deep Agents and Apple/MLX extras, prove MLX readiness without
downloading an unbounded model, and run the documented golden path. Any model
execution used for release proof must use the already governed route/budget and
admitted Plan-5 profile.

Extend `scripts/ci-in-container.sh` (or add a thin sibling that reuses its image
and volumes) for a real Linux candidate-wheel install. It must use the same wheel
bytes/digest as macOS, install `deepagents` but not MLX, run the golden path and
CLI smoke, and emit a Linux host proof. Container CI may remain a separate
exact-tip receipt, but no Linux-root `.venv` or build output may contaminate the
host checkout. Do not add GitHub Actions.

Supported v1 runtime truth is exactly:

```text
macOS Apple Silicon = supported; primary performance target; MLX lane
Linux               = supported governance/runtime lane; no MLX parity claim
Windows             = unsupported for v1
WSL2                = unsupported for v1
Python              = >=3.12.13,<3.13
```

### Tranche 3 — Integrated release sabotage battery

Create one release-scenario manifest/runner that calls canonical services and
validators and references existing lower-level tests. It must not recreate
subsystem artifact kinds or use synthetic success receipts where real local
services are available. Every scenario declares expected terminal state,
expected refusal/recovery reason, allowed mutations, restoration check, and
evidence refs.

The battery must cover one successful complete loop plus:

- denied tool and denied write with zero unauthorized mutation;
- forged approval, stale/expired approval, and substituted digest;
- model/obligation budget exhaustion without hidden retry or provider widening;
- native Deep Agents interruption/crash and exact checkpoint resume;
- Goose disconnect and MCP disconnect/refusal with durable terminal evidence;
- failed verification blocking patch/delivery advancement;
- patch/target drift refusing before apply and preserving the target;
- remote identity/head mismatch and forbidden direct-main/force push;
- approved apply followed by distinct approved rollback and exact restoration;
- post-push corrective delivery through a new commit, never amend/reset/history
  rewrite.

Where a live network/runtime would make the battery non-deterministic, use the
existing transport seam with a deterministic disconnect or bounded local/bare
remote, and state that exact limitation. Release-level proof is the integrated
state transition and refusal behavior, not a claim that every external vendor
was live.

### Tranche 4 — Exact-candidate release-proof bundle

After the candidate source is settled, build the bundle once from an exact clean
commit/tree. The builder must consume only validated evidence under admitted
namespaces, reject symlinks/substitution/duplicate ambiguity, independently
recompute every digest, and validate source/lock/wheel/host identity
cross-bindings. It must refuse development-snapshot evidence, mismatched wheel
bytes, a dirty or moved candidate, wrong OS/architecture, skipped required lanes,
stale benchmark evidence, non-green CI, stale generated docs, or an unlisted
limitation.

Required contents/references:

1. candidate Git/source/archive identity and dependency-lock digest;
2. sdist/wheel metadata, RECORD/package inventory, and artifact digests;
3. exact-tip `scripts/ci.sh --receipt` result with no unacknowledged skips;
4. macOS Apple Silicon install/golden-path host proof;
5. Linux install/golden-path host proof;
6. release sabotage battery report and constituent evidence index;
7. `builder-platform matrix` and `builder-platform audit-docs` outputs plus
   generated-doc byte/digest checks;
8. admitted Plan-5 M1 benchmark report, physical-footprint method/evidence, and
   validity/readback result;
9. supported runtime/tool versions and explicit unsupported-host statement;
10. current known limitations and capability assurance states;
11. flagship demo/rehearsal transcript/evidence and artifact digests;
12. hosted custody refs for rehearsal PRs #1/#2 before they are cleaned up;
13. canonical artifact index and chain-verification report for the whole bundle.

The release validator must be independently invocable against a copied bundle
and the exact candidate checkout. A second validation from clean bytes is the
exit evidence; merely generating the bundle is not proof that it validates.

### Tranche 5 — Final review and authority stop

When every required lane is green, prepare a review packet containing the exact
candidate SHA/tree, proposed `v1.0.0` tag target, wheel digests, bundle digest,
validation commands/results, known limitations, matrix deltas proposed for
promotion, and all remaining human decisions. Then stop.

The following are distinct later decisions:

1. human review of exact candidate and release-proof bundle;
2. human promotion/ratification of each capability row, with all eight gates;
3. human authorization to create tag `v1.0.0` at the reviewed exact commit;
4. human authorization for each publication effect (GitHub Release and any
   package registry), including destinations and credentials;
5. hosted readback of tag/release/package bytes and digests;
6. declaration `OPEN-SOURCE V1 COMPLETE` only after those authorized effects
   and readbacks actually occur.

Set-7 implementation approval is not any of those decisions.

## Expected implementation ownership and file envelope

Exact filenames may narrow after the required pre-edit caller sweep, but work
must stay within these owners:

- release schema/builder/validator: `builder_ii/core/release_manifest.py` or
  one clearly named replacement, plus canonical registry/chain modules;
- release CLI/script: generalized `scripts/verify_v0_release.py` and the
  existing `builder-platform`/specialist command architecture;
- packaging: `pyproject.toml`, package-resource locations, and focused wheel
  tests; no unrelated dependency or build-backend migration;
- platform proof: `scripts/clean-clone-smoke.sh`,
  `scripts/ci-in-container.sh`, and small shared shell helpers where duplication
  would otherwise create divergent lanes;
- sabotage composition: one release scenario owner plus focused integration
  tests that call existing canonical services;
- truth: `builder_ii/core/platform_completion_audit.py`,
  `builder_ii/lifecycle/setup/known_limitations.py`, canonical generators, and
  their generated documents/tests;
- release docs: README/first-session/getting-started/STRATUM/operator,
  architecture, delivery, recovery, support, limitations, and release-proof
  surfaces only where current claims require change.

Before editing any load-bearing owner, trace imports, CLI entrypoints, registry
hooks, chain extraction, tests, and downstream docs. If implementation discovers
that an existing canonical owner can express a requirement, extend it; do not
introduce a parallel manifest, validator, evidence store, or authority path.

## Qualification order and exact claims

During implementation, use focused tests for each owner. At the settled release
candidate, qualify in this order:

1. package metadata/resource inventory and V0-migration/v1-schema tests;
2. source-derived matrix, limitations, command-authority, registry, chain, and
   docs-truth tests; regenerate derived docs and prove byte equality;
3. wheel/sdist build, metadata inspection, RECORD inventory, and fresh base +
   Deep Agents `uv tool install` smoke;
4. integrated successful-loop and sabotage battery;
5. fresh Linux candidate-wheel install and golden path;
6. fresh macOS Apple Silicon candidate-wheel install and golden path;
7. Plan-5 benchmark evidence validation/readback;
8. exact settled-tip `bash scripts/ci.sh --receipt <fresh-path>` locally;
9. release-proof bundle construction;
10. independent bundle validation from copied clean bytes;
11. final `git diff --check`, clean-state, SHA/tree, wheel, bundle, and hosted
    base readbacks.

Do not rerun the expensive full local battery merely because another nominal
phase began. Run it once on the settled candidate tip, and rerun only if a
material repair changes that tip. Linux and macOS host proofs are independently
required and cannot substitute for each other or for exact-tip local CI.

The proof claims are narrow:

- both supported platforms installed the exact wheel and completed the
  documented governed golden path;
- the integrated battery produced the pre-registered success/refusal/recovery
  outcomes without unauthorized effects;
- the candidate's local CI, docs/matrix truth, lock, wheel, benchmark, and demo
  evidence are digest-bound in one independently valid bundle;
- no capability was promoted and no tag/package was published by qualification.

## Rehearsal PR custody and cleanup

Do not spend an implementation tranche on rehearsal PRs #1/#2. Preserve them as
Set-7 source evidence until the exact-candidate bundle records their repository,
number, state, head/base SHA, URL, and relevant receipt/evidence digests through
hosted readback. Only after that custody is in the validated bundle may a
separately authorized housekeeping action close them unmerged. Closing them is
not part of release qualification and must not mutate or rewrite their heads.

## Explicit non-goals and denied authority

```text
BROAD_FEATURE_BUILD             = OUT_OF_SCOPE
WINDOWS_OR_WSL2_PARITY          = OUT_OF_SCOPE
HOSTED_GITHUB_ACTIONS           = FORBIDDEN_AS_RELEASE_EVIDENCE
SECOND_RELEASE_TRUTH_SYSTEM     = FORBIDDEN
SUBSYSTEM_EXECUTOR_REWRITE      = OUT_OF_SCOPE
CAPABILITY_PROMOTION            = NOT_AUTHORIZED
TAG_CREATION                    = NOT_AUTHORIZED
GITHUB_RELEASE_PUBLICATION      = NOT_AUTHORIZED
PACKAGE_REGISTRY_PUBLICATION    = NOT_AUTHORIZED
REHEARSAL_PR_CLOSURE            = NOT_AUTHORIZED
MERGE_OR_HISTORY_REWRITE        = NOT_AUTHORIZED
APPROVAL_MINTING_BY_MODEL       = FORBIDDEN
```

## HITL implementation boundary and exit contract

Implementation must halt until a human supplies a digest-bound approval artifact
or equally explicit repository-recognized approval binding this plan's exact
bytes/digest, `BASE_SHA`, `BASE_TREE`, permitted file/effect envelope,
qualification sequence, and denied operations.

After that approval, Set 7 implementation is complete only when the exact
candidate wheel installs and completes the documented golden path on fresh
macOS Apple Silicon and Linux hosts; the integrated sabotage battery reaches
its registered outcomes; exact-tip local CI passes; current truth docs match
their typed sources; and the canonical release-proof bundle independently
validates from the exact proposed `v1.0.0` tag target. The engineer then stops
for final review, human promotion, and separate tag/publication authorization.

At plan time:

```text
PLAN_SET_7_IMPLEMENTATION = PLANNED_ONLY
RELEASE_CANDIDATE         = NOT_BUILT
MACOS_RELEASE_PROOF       = NOT_RUN
LINUX_RELEASE_PROOF       = NOT_RUN
SABOTAGE_BATTERY          = NOT_RUN
LOCAL_EXACT_TIP_CI        = NOT_RUN_FOR_SET_7
RELEASE_PROOF_BUNDLE      = NOT_CREATED
CAPABILITY_PROMOTION      = NOT_AUTHORIZED
TAG_V1.0.0                = NOT_CREATED_OR_AUTHORIZED
PUBLICATION               = NOT_AUTHORIZED
OPEN_SOURCE_V1            = NOT_COMPLETE
```
