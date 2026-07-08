# Changelog

All notable changes to builder-II are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/) starting from its first tagged release. Prior
to the `v0.1.0` tag, schema and artifact-format changes are made freely without a compatibility
policy ("Ledger Genesis" — no dual-version parsers pre-1.0; see
[`docs/CAPABILITY_PROMOTION.md`](docs/CAPABILITY_PROMOTION.md)). After `v0.1.0`, schema changes
require an explicit versioning policy.

## [Unreleased]

Work below is tracked against the "CORE par" master completion plan (governance-hardening pass
toward a beta release). Dates are merge dates on `main`.

### Security

- Closed a weak-approval gap in HITL patch application: any JSON file with a matching
  `patch_digest` could previously authorize mutation, and command authority accepted any non-empty
  `approval_ref`. Added a generic, digest-bound `builder-hitl approve-patch` artifact/CLI with an
  interactive TTY confirmation (operator types the first characters of the patch digest) and routed
  apply/rollback through the command-authority gate at execution time.
- Scrubbed personal paths, names, and tooling references from tracked docs and fixtures ahead of
  eventual open-sourcing.

### Added

- Bounded, schema-enforced `pytest_full`/`builder_full` verification execution envelope: commit
  identity in git state, a required per-profile timeout (replacing a hardcoded 30s default), and a
  schema-enforced execution-risk acknowledgment gate before spawning target-code-executing profiles.
- Generic pre/post-apply verification receipt lane for arbitrary target repositories.

### Changed

- Reconciled `builder-goose start-readonly`'s documented promotion state with its actual registry
  tier and behavior; replaced a `MockPlan` placeholder with a named launch plan and made
  `close-readonly` an honest (non-decorative) stub.
- Dropped `gh` (GitHub CLI) from the required install-tools tier — this repository is hosted on a
  private Forgejo instance, not GitHub — and pinned the Goose installer by checksum.
- Documented the reasoning-and-problem-solving discipline agents should follow for design/R&D work
  touching load-bearing modules (see `AGENTS.md` §6).

### Fixed

- Phase 0 truth-and-safety hardening: corrected a dangling `rollback_plan_ref` in apply-failure
  receipts, removed a phantom CLI command reference, reconciled docs-truth drift, closed a
  typing-gate gap, added missing test coverage for the HITL command runner, removed stale
  presentation claims, and deleted dead code.

## Prior history

Pre-`v0.1.0` development history before this changelog was established (the CORE-born foundation,
governed artifact spine, CLI/TUI surface, and the ~40 `builder-*` command families) is available in
full via `git log`. This changelog begins tracking forward from the start of the "CORE par" master
completion plan.
