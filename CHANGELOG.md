# Changelog

All notable changes to builder-II are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/) starting from its first tagged release. Prior
to the `v0.1.0` tag, schema and artifact-format changes are made freely without a compatibility
policy ("Ledger Genesis" — no dual-version parsers pre-1.0; see
[`docs/CAPABILITY_PROMOTION.md`](docs/CAPABILITY_PROMOTION.md)). After `v0.1.0`, schema changes
require an explicit versioning policy.

## [Unreleased]

Nothing yet.

## [0.1.0] - 2026-07-08

The first tagged release: the complete "CORE par" beta backlog (governance-hardening pass toward a
beta). Dates are merge dates on `main`.

Release verification: the annotated `v0.1.0` tag records the tagged commit together with the
release-proof harness result on that exact tree (`uv run python scripts/verify_v0_release.py` —
artifact chain valid; runtime, model, shell, source-write, and autonomous authority all disabled)
plus the sha256 of the generated chain-verification report. The full CI gate (Rust build, bytecode
compile, docs truth audit, secret scan, ruff, targeted mypy, targeted bandit, full pytest) and the
clean-clone smoke gate (`scripts/clean-clone-smoke.sh`) were green on the tagged tree.

### Security

- Closed a weak-approval gap in HITL patch application: any JSON file with a matching
  `patch_digest` could previously authorize mutation, and command authority accepted any non-empty
  `approval_ref`. Added a generic, digest-bound `builder-hitl approve-patch` artifact/CLI with an
  interactive TTY confirmation (operator types the first characters of the patch digest) and routed
  apply/rollback through the command-authority gate at execution time.
- Made rollback a first-class governed mutation: a distinct digest-bound
  `builder-hitl approve-rollback` approval artifact (no longer authorized by the machine-generated
  rollback plan itself), a working-tree drift fingerprint captured at apply time and re-verified
  before rollback touches the tree, and rollback-failure receipts that carry an explicit recovery
  block instead of stranding the operator.
- Scrubbed personal paths, names, and tooling references from tracked docs and fixtures ahead of
  eventual open-sourcing.

### Added

- Bounded, schema-enforced `pytest_full`/`builder_full` verification execution envelope: commit
  identity in git state, a required per-profile timeout (replacing a hardcoded 30s default), and a
  schema-enforced execution-risk acknowledgment gate before spawning target-code-executing profiles.
- Generic pre/post-apply verification receipt lane for arbitrary target repositories.
- HITL patch ledger records (`builder_ii.hitl_patch_ledger_record`) emitted on apply and rollback,
  binding the governing artifact chain's on-disk digests, plus unmocked end-to-end tests for the
  full propose → approve → apply → rollback loop.
- `builder init`: a unified governed onboarding orchestrator — four prompted wizard decisions
  validated against live registries (never free text), five documented-default decisions echoed
  with their override flags, and the full passive setup artifact chain emitted without ever
  applying. `builder-setup apply`/`rollback` gained an interactive digest-prefix confirmation when
  `--approve-digest` is omitted; receipts record which approval path was used.
- `FIRST_SESSION.md`: the single validated onboarding path (clone to one complete governed patch
  loop), with a zero-edit `.env.example` default and a collapsed README first-run section.
- `scripts/clean-clone-smoke.sh`: a repeatable clean-clone onboarding and governed-patch-loop smoke
  gate.
- The flagship 15-minute demo script (`docs/demos/FLAGSHIP_DEMO_SCRIPT.md`) with a live
  tamper-detection beat, backed by a new integrity re-check: `builder-platform validate-demo-loop`
  re-verifies every evidence artifact's sha256 from disk, so an edited receipt or approval is named
  explicitly instead of passing silently.
- First recorded demo assets (`docs/recordings/*.cast`) and a headless asciinema recording harness
  (`scripts/record-demo.sh`) with a timestamp-pinning option for reproducible takes.
- `docs/BETA_CHARTER.md` (what feedback the beta wants) and `docs/KNOWN_LIMITATIONS.md`, generated
  from the completion truth matrix by the new `builder-platform known-limitations` command and
  pinned against drift by test — including the verification-lane scope statement (trusted local
  Python-with-pytest repositories only; the bounded runner constrains invocation, never what
  invoked code can do; it is not a sandbox).
- `docs/README.md` reference index and the three-tier documentation entry path
  (README → FIRST_SESSION → reference), plus host-neutral CONTRIBUTING / SECURITY /
  CODE_OF_CONDUCT drafts and this changelog.

### Changed

- Promoted two capability groups in the completion truth matrix, each behind an evidence-first,
  operator-applied flip with a closure audit and a pinned-site consistency checker
  (`scripts/b4_flip_assistant.py`): operator-invoked HITL patch application and rollback execution
  (`docs/audits/B4_CLOSURE_AUDIT.md`), and the interactive setup wizard after `builder init`
  landed (`docs/audits/R1_CLOSURE_AUDIT_2_6.md`). Both lanes remain operator-invoked candidates —
  autonomous execution stays unpromoted.
- Generalized the governed demo loop from CORE-only to any operator-designated local git
  repository (`--target-repo`/`--target-name`; the CORE profile keeps its identity check and
  sensitive-module policy), deleted the narrative demo-approval artifact kind in favor of the real
  governed approval, and strengthened demo verification so nothing beyond the approved marker may
  change.
- Gated the experimental STRATUM TUI behind `--experimental` with an honest refusal describing its
  display-only state.
- Moved `mlx-lm`/`rapid-mlx` to optional dependency extras (Mac-first boundary documented).
- Reconciled `builder-goose start-readonly`'s documented promotion state with its actual registry
  tier and behavior; replaced a `MockPlan` placeholder with a named launch plan and made
  `close-readonly` an honest (non-decorative) stub.
- Dropped `gh` (GitHub CLI) from the required install-tools tier — this repository is hosted on a
  private Forgejo instance, not GitHub — and pinned the Goose installer by checksum.
- Documented the reasoning-and-problem-solving discipline agents should follow for design/R&D work
  touching load-bearing modules (see `AGENTS.md` §6), and the manual (by-design) Goose
  config/skills installation step.

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
