# DRAFT — builder-II CORE-par Master Completion Plan (for adversarial review)

GOAL: builder-II to "CORE par" — mastery-grade completion for beta, presentation, open-sourcing.
Definition of done: a stranger can clone, onboard in 30 min, and run one complete governed patch loop
(propose→approve→apply→verify→rollback) on their own repo with receipts; repo legally giftable;
demo credible to skeptical senior engineers.

## M0 TRUTH & SAFETY HARDENING (parallel, low risk)

- Fix apply failure-receipt dangling rollback_plan_ref (failure receipt references a rollback_plan.json that is only written on the success path); add rollback failure receipt
- Harden patch approval boundary NOW (today any JSON file with matching patch_digest authorizes mutation via apply_hitl_patch line ~237; command authority MODE_HITL_ARTIFACT_REQUIRED accepts any non-empty approval_ref string)
- Add 5 already-mypy-passing authority modules (hitl_command_execution, hitl_patch_proposal, verification_execution_plan, tool_invocation_gateway, readonly_inspection_promotion) to CI mypy gate; add types-PyYAML dev dep; fix goose_command_proposal.py 7 union-attr NoneType errors; add [tool.mypy] config to pyproject as single source of typing scope
- Add tests for hitl_command_runner.execute_hitl_command (subprocess path, zero test coverage today)
- README credibility fixes (remove "rock-solid/flawlessly supports" cloud claims contradicting the Not-yet-promoted list); fix splash tagline ("CORE-native" contradicts generic-first doctrine) + remove Swift compile-run subprocess from TUI splash launch path
- Docs drift reconciliation: 5 docs contradicting merged patch-apply reality (docs/HITL_PATCH_PROPOSAL.md says DESIGN_ONLY / "no patches applied by any current code path"; docs/CAPABILITY_PROMOTION.md references nonexistent "builder-hitl plan-patch"; docs/RUNTIME_PROMOTION.md non-promotion statement); B1 docs say one-profile runner while runner supports two (platform_status + docs_audit)
- Dead code: delete agent_tui.py (1,173 lines, no importer) after confirming palette-contract intent

## M1 THE LOOP — B4 generic promotion (critical path)

- B4.1 Generic builder_ii.hitl_patch_approval artifact kind + `builder-hitl approve-patch` CLI (fields: patch_digest, proposal_digest, approver, reason, expiry); register in artifact index + chain verification; closes the weak-approval hole
- B4.2 Generic pre/post-apply verification receipt lane for arbitrary target repos ← depends on M3 ladder slice (pytest profile promotion + plan validator extension beyond builder/builder_full + commit identity in receipts)
- B4.3 Distinct rollback human approval + rollback failure receipt
- B4.5 Unmocked E2E tests (real schema-valid approval + verification artifacts; CLI-level command-authority denial tests; today tests monkeypatch VALIDATORS and mock receipt validation)
- B4.6 Ledger event emission for apply/rollback (currently zero ledger integration)
- B4.7 Receipts-backed live closure audit (docs/audits/B4_CLOSURE_AUDIT.md) → B4.8 atomic matrix flip + pinned-test updates (operationally_verified_count==15 at tests/test_platform_completion_truth.py:162, BLOCKED_BY_EVIDENCE asserts) + docs truth reconciliation
- B4.9 Generalize core demo loop to generic targets (parameterize marker patch + CORE-specific sensitive-path checks, generalize worktree prep beyond _ensure_core_repo, replace core_demo_approval with generic approval kind, drop target.name=='core' restriction in demo-receipt acceptance)

## M2 THE DOOR — R1 onboarding (claimed parallel with M1)

- Extract reusable wizard framework from deepagents Forge (decouple step engine from DeepAgentSpec)
- Setup wizard v2: collect all ~9 operator decisions (add target repo path, artifact root, agent profile, verification profile, skills destination policy — today's wizard collects only 4), registry-validated answers against target_profiles.py/agent_profiles.py/models.py
- Wizard→apply HITL bridge: interactive digest review/confirmation step (explicitly NOT one-click; preserves planned≠executed; setup_apply is already digest-gated)
- Implement "merge" (secrets-preserving Goose config) and "copy" (skills) operations in setup_apply SUPPORTED_OPERATIONS with rollback snapshots covering merged files (overlay vocabulary emits them but apply cannot execute them)
- `builder init` unified first-run orchestrator: env bootstrap→doctor→wizard→approve→apply→session package→readonly manifest
- Wire onboarding/session artifacts into `builder-goose start-readonly` (remove hardcoded MockPlan at goose_cli.py:264-270, implement close-readonly stub)
- README "First run" rewrite + FIRST_SESSION.md 30-minute quickstart (tested from clean clone/home sandbox; today README First-run is ~40 commands with 6 duplicated)
- DEFER post-beta: target/agent/verification profile wizards, recipe wizard, deepagents-setup wizard (all NOT_STARTED in matrix; authoring conveniences off the clone-to-session critical path)

## M3 THE LADDER — B2 seed (feeds B4.2 and future CodeVault promotion signal)

- Reconcile pytest profile naming invariant (plan default step_id 'pytest_full' vs runner requirement step_id==profile; ref 'verification_profiles.builder_full.pytest_full' violates _validate_fixed_profile) — blocks everything downstream
- Capture target-repo commit identity (HEAD SHA, branch) in runner git state + receipt schema bump (today only git status porcelain; a receipt cannot assert "tests passed at commit X")
- Promote bounded pytest_full profile: fixed argv, shell=False; mutation-detection policy for pytest byproducts (.pytest_cache/__pycache__/.coverage) via pre-declared ignore globs; timeout policy decision for long suites (current model is fixed 30s per profile, operator_override_enabled=false)
- Record structured test outcomes (pass/fail/skip counts, junit-xml under artifact_root, exact argv not just argv_digest)
- Enforce approval expires_at in runner (field exists, never read)
- Emit ledger_index/previous_ledger_record_digest at index time (today chain_continuity_status permanently 'not_applicable_no_sequence_rule')
- B2.0 machine-checkable promotion gate evaluator (consumes plan/approval/receipt/ledger digests → pass/fail promotion-evidence artifact; named in B1_B2_RUNTIME_GOVERNANCE_COMPLETION_MAP.md line 47, zero implementation)
- Extend plan validator beyond hard-pinned builder/builder_full (target_profile/verification_profile)
- Design-only RFC: CodeVault receipt-consumption bridge (epistemic promotion via verification receipts) — implementation post-beta

## M4 THE CRAFT — CodeVault Tier-1 + bench (claimed parallel post-M0)

- Doctrine amendment FIRST: versor enrichment may be content-derived (analogous to content_digest), center_xyz stays layout-only; new determinism proof for the boundary (docs/CODE_VAULT.md line 5 currently says "never from source content" and demo proof content_edit_changes_digest_not_center enforces it)
- Extend symbol_extractor with structural facts (arity, nesting depth, cyclomatic estimate, decorator count, async flag, class membership — none exist today; AsyncFunctionDef collapsed into 'function'; class bodies never walked)
- Structural lift writing to trivector/4-vector slots 16-30 (grade-1 slots all consumed by conformal embedding; bivector slots 6-15 collide with rotor candidates) with bounded versioned normalization (raw counts like arity=30 would dominate unit-scale conformal terms in the +/-1 metric)
- Grade-1-projection null-cone invariant redefinition + structural-aware reproject policy (is_null_point uses full multivector self-inner-product; null_project_point rebuilds from arr[1:4] only, erasing structural components)
- Projection contract vocabulary extension + frame schema decision (v2 optional per-node structural block vs new artifact kind) + validators + staged-acceptance row (schema bump blast radius: frame validators consumed by artifact_index_records, chain verification, prepare-package, workflow spine, ConventionKernel, TUI)
- Synthetic frame/matrix generator (10k nodes infeasible today: O(N²) pure-Python collision detection ~50M pair distances, repo-map 500-file cap); vectorize recall candidate embedding (currently re-embeds all N per query in Python loop)
- Bench lane CLI + report artifact: latency N={100,1k,10k}, encoder determinism, pure_numpy vs core_rs parity (parity today proven only on a 2-point fixture); report schema separates deterministic sections (digests, parity counts) from measurement sections (latencies) so validate-bench replays don't fail

## M5 THE GIFT — OSS + presentation

- License decision (recommend Apache-2.0) + pyproject license field (no LICENSE file exists; repo legally all-rights-reserved)
- Community files: CONTRIBUTING.md, SECURITY.md (incl. goose-installer curl-pipe supply-chain note), CODE_OF_CONDUCT.md, CHANGELOG.md, Forgejo issue/PR templates (.forgejo/)
- Forgejo Actions CI parity: replace gitleaks-action (GitHub-API-coupled with GITHUB_TOKEN), verify runner labels (ubuntu-latest), address Linux uv sync failure from mlx-lm/rapid-mlx hard deps
- History/PII strategy DECISION: fresh-start public repo (recommended) vs full history rewrite; either way full-refs secret scan (614 commits, 63 local + 172 remote branches incl. backup/main-before-reset, 1 stash) with gitleaks/trufflehog
- PII scrub in 22 tracked files (<developer_name> paths, "<developer_name>", assetoverflow@icloud.com on all commits, hardcoded /Users paths in docs/fixtures); edit agent-instruction files (CLAUDE.md/AGENTS.md/.cursorrules reference private Forgejo host git.acbcontent.org) for public consumption
- Platform gating: move mlx-lm/rapid-mlx to [project.optional-dependencies] so non-Mac uv sync works; document Mac-first boundary honestly in README
- Install consolidation: single bootstrap path, remove gh from install-tools.sh required tier (contradicts repo's own Forgejo-only rule), pin goose installer by checksum
- Docs funnel: docs/README.md index with 3-tier entry path (README → FIRST_SESSION → reference); fix OPERATOR_QUICKSTART hardcoded founder paths (112 top-level docs files, no index)
- v0.1.0 tagged release bound to release-proof harness + CHANGELOG entry (zero tags exist today)
- DEMO: generic-target demo loop (builds on B4.9); canonical 15-minute flagship script with live tamper-detection beat (edit a receipt → chain verification fails); interactive TTY approval prompt at the decision point (replace --approve re-run flag); asciinema/VHS recordings committed (zero recorded assets exist); STRATUM TUI honesty DECISION (gate mockup behind --experimental flag for beta [recommended] vs wire real artifacts — today: fake tier evaluation, fabricated chain digest, notify-only approve/reject); timestamp pinning option for reproducible recording bundles (all CORE demo digests differ between takes due to wall-clock created_at)

## M6 THE BETA

- Beta charter (what feedback is wanted), known-limitations doc generated from truth matrix, Forgejo issue intake templates, weekly triage cadence

## DEPENDENCY SPINE

M0 first (unblocks all, closes the security hole). M3's first four items feed B4.2 inside M1 — they are the same convergence stream. M1 ∥ M2 parallel. M4 parallel after M0. M5 community/license items start immediately; M5 demo items gate on M1 (B4.9). M6 last.

## USER DECISIONS REQUIRED

1. License: Apache-2.0 vs MIT
2. History: fresh-start public repo vs full history rewrite
3. STRATUM TUI: gate behind experimental flag vs wire real artifacts for beta
4. Non-Mac support: optional-extras gating now vs Mac-only beta
5. CodeVault Tier-1 (M4): in beta scope vs first post-beta item
