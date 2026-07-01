# builder-II Completion Truth Report + Master Completion Plan

Date: 2026-06-29

Scope: source-grounded audit of AssetOverflow/builder-II on detached `HEAD` tracking current `main`.

Verification evidence gathered:

- GitHub open PRs: `gh pr list --repo AssetOverflow/builder-II --state open ...` returned `[]`.
- Recent merged PRs: #138 through #154 are passive/candidate/foundation slices by title and source inspection.
- Full tests: `CORE_REPO_PATH=. uv run pytest -q` passed.
- Baseline test caveat: `uv run pytest -q` without `CORE_REPO_PATH=.` fails because this worktree has no sibling `../core` target repo.
- v0 proof harness: `CORE_REPO_PATH=. uv run python scripts/verify_v0_release.py --output-dir /private/tmp/builder-ii-v0-proof-audit` passed and emitted 13 artifacts with runtime authority, model execution loops, shell execution, source writes, and autonomous agent authority disabled.

## 1. Executive truth state

builder-II is passive-foundation-complete for a large governed artifact spine, but the builder-II platform is operationally incomplete as a local agent/developer platform: profiles, context packs, profile packs, passive routing, passive orchestration, HITL candidate artifacts, workflow ledger, chain verification, read-only metadata reports, and a readonly founder demo exist and are tested, while a governed config/onboarding kernel, HITL verification execution, patch application/rollback execution, Goose runtime promotion, deepagents runtime, model/provider gateway, MCP/tool invocation gateway, artifact memory, coherent operator status/doctor truth, and machine-enforced docs truth are not operationally verified.

## 2. Capability state matrix

State labels used: `NOT_STARTED`, `DESIGN_ONLY`, `ARTIFACT_ONLY`, `PASSIVE_FOUNDATION`, `IMPLEMENTED_ON_BRANCH`, `PR_OPEN`, `MERGED_BUT_NOT_OPERATIONAL`, `OPERATIONALLY_VERIFIED`.

| Capability | State | Evidence files, command surface, tests | Missing work and promotion blockers | Next PR |
|---|---|---|---|---|
| generic platform identity | PASSIVE_FOUNDATION | `README.md`, `docs/ROADMAP.md`, `docs/adrs/ADR-0003-builder-ii-generic-platform-identity-and-capability-factory.md`, `tests/test_operator_command_surface.py`, `tests/test_command_authority.py`; commands: none dedicated | Identity is documented and tested, but truth-state enforcement is not machine-derived. Legacy root commands still use CORE naming internally in places such as `builder_ii/goose_setup.py`. | R0 |
| target profiles | PASSIVE_FOUNDATION | `builder_ii/target_profiles.py`, `builder_ii/targets_cli.py`, `tests/test_target_profiles.py`; commands: `builder-targets list/show/validate/artifact/demo/readonly-founder-demo` | Profiles are no-runtime artifacts. Need target registration lifecycle with authority state and target-root policy for operational runtime. | B3 |
| agent profiles | PASSIVE_FOUNDATION | `builder_ii/agent_profiles.py`, `builder_ii/agent_cli.py`, `tests/test_agent_profiles.py`; command: `builder-agent validate` | Roles record read/plan/proposal authority only. No runtime agent construction, approval, or receipt path. | B5 |
| verification profiles | PASSIVE_FOUNDATION | `builder_ii/verification_profiles.py`, `builder_ii/verification_cli.py`, `builder_ii/verification_profile_reports.py`, `tests/test_verification_profiles.py`, `tests/test_verification_profile_reports.py`; commands: `builder-verification list/show/artifact/validate` | Profiles propose checks and reject completed evidence claims. Missing HITL-approved runner and receipt binding. | B1 |
| context packs | PASSIVE_FOUNDATION | `builder_ii/repo_map.py`, `builder_ii/context_packs.py`, `builder_ii/session_cli.py`, `tests/test_repo_map.py`, `tests/test_governed_prepare_package.py`; commands: `builder-session repo-map/context-pack/prepare-package` | Canonical path is artifact-only. Legacy `builder-context` uses external scanning and git subprocesses outside governed read authority. Need B3 read authority policy. | B3 |
| profile packs | PASSIVE_FOUNDATION | `builder_ii/profile_pack_manifest.py`, `profile_pack_render_plan.py`, `profile_pack_dry_run.py`, `profile_pack.py`, `tests/test_profile_pack.py`, `tests/test_profile_pack_cli.py`; commands: `builder-profile-pack scaffold/render/dry-run/validate` | Lifecycle is passive (`PLANNED_ONLY`, `RENDERED_ONLY`, `DRY_RUN_ONLY`, `PACKED_ONLY`). No runtime materialization. | R0 then defer runtime materialization |
| config schema | PASSIVE_FOUNDATION | `builder_ii/config_schema.py`, `builder_ii/config.py`, `docs/CONFIG_ONBOARDING.md`, `tests/test_config_schema.py`, `tests/test_config_setup_cli.py`; command: `builder-config schema/validate` | R1.1 adds a generic-first schema with disabled capability defaults and legacy `CORE_*` alias metadata. Setup apply, receipts, rollback, migration tooling, and runtime authority are still missing. | R1 |
| config source precedence | PASSIVE_FOUNDATION | `builder_ii/config_sources.py`, `builder_ii/config_cli.py`, `docs/CONFIG_ONBOARDING.md`, `tests/test_config_sources.py`, `tests/test_config_setup_cli.py`; command: `builder-config resolve/validate` | R1.1 records CLI/env/.env/config-file/profile/built-in precedence with source refs, redaction, warnings, errors, path policy, and deterministic digest. It remains artifact-only. | R1 |
| interactive setup wizard | PASSIVE_FOUNDATION | `builder_ii/setup_onboarding.py`, `builder_ii/onboarding_intent.py`, `builder_ii/setup_cli.py`, `builder_ii/cli.py`, `tests/test_onboarding_intent.py`, `tests/test_setup_onboarding_wizard_cli.py`; commands: `builder-setup wizard`, `builder onboarding` | R1.5 provides an interactive guided setup wizard emitting passive onboarding intent and plan artifacts. Onboarding commands print deferred apply commands only; setup mutation remains exclusively owned by `builder-setup apply`. Target/agent/verification profile editing wizards remain separate unbuilt slices. | R1 |
| non-interactive setup/apply/validate | MERGED_BUT_NOT_OPERATIONAL | `builder_ii/cli.py` setup/onboarding/doctor/status, `builder_ii/goose_setup.py`, `builder_ii/setup_plan.py`, `builder_ii/setup_overlay.py`, `builder_ii/setup_rollback.py`, `builder_ii/setup_onboarding.py`, `builder_ii/onboarding_intent.py`, `builder_ii/setup_cli.py`; commands: legacy `builder setup` redirect, `builder onboarding`, `builder-setup init/wizard/validate-onboarding-intent/plan/validate-plan/overlay-plan/validate-overlay-plan/rollback-snapshot/validate-rollback-snapshot/apply/validate-receipt/rollback/validate-rollback-receipt` | R1.4 reconciles legacy setup surface. R1.5 adds non-interactive `builder-setup init` and intent validation. Runtime promotion remains missing. | R1 |
| Goose config overlay/rollback | PASSIVE_FOUNDATION | `builder_ii/setup_overlay.py`, `builder_ii/setup_rollback.py`, legacy `builder_ii/goose_setup.py`, `tests/test_setup_overlay.py`, `tests/test_setup_rollback.py`, `tests/test_goose_setup.py`, `tests/scenarios/test_config_to_goose_projection_flow.py` | R1.2 describes Goose config overlay keys, recipe registration, secrets-preservation policy, prior-state markers, and future rollback operation metadata. No Goose config writes, apply, rollback execution, approved write boundary, or audit receipt exists. | R1 |
| recipe generator/wizard | ARTIFACT_ONLY | `recipes/`, `builder_ii/goose_recipe_context_projection.py`, `tests/test_goose_recipe_context_projection.py`, `tests/test_session_wiring.py`; command surface through setup/projection paths | Recipe assets and projections exist. No generator/wizard, operator preview, apply receipt, rollback path, or target/profile compatibility check. | R1 |
| skill generator/installer/validator | MERGED_BUT_NOT_OPERATIONAL | `.agents/skills/`, `builder_ii/setup_overlay.py`, `builder_ii/goose_setup.py`, `tests/test_setup_overlay.py`, `tests/test_goose_setup.py`; commands: `builder-setup overlay-plan`, legacy `builder setup` redirect | R1.2 adds passive install-plan entries with source/destination digests and conflict notes. R1.4 disables legacy skill copying from `builder setup`. Operational skill install/copy, setup receipt promotion, rollback execution, and target-scoped approval are still missing. | R1 |
| target profile wizard | NOT_STARTED | `builder_ii/target_profiles.py`, `builder_ii/targets_cli.py`, `tests/test_target_profiles.py`; command surface validates existing profiles | No guided target profile creation/editing, dry-run preview, source precedence binding, or setup receipt. | R1 |
| agent profile wizard | NOT_STARTED | `builder_ii/agent_profiles.py`, `builder_ii/agent_cli.py`, `tests/test_agent_profiles.py`; command surface validates existing profiles | No guided agent profile creation/editing with authority preview and disabled runtime defaults. | R1 |
| verification profile wizard | NOT_STARTED | `builder_ii/verification_profiles.py`, `builder_ii/verification_cli.py`, `tests/test_verification_profiles.py`; command surface validates existing profiles | No guided verification profile creation/editing, command allowlist preview, target compatibility check, or no-execution proof. | R1 |
| deepagents/researcher setup wizard | NOT_STARTED | `builder_ii/deepagents_policy.py`, `builder_ii/deepagents_readiness.py`, `builder_ii/deepagents_bridge_readiness.py`, tests around readiness/policy; commands: `builder-deepagents policy/readiness/validate*` | Optional dependency readiness exists, but no setup wizard for researcher/deepagents capability selection, denied defaults, receipts, or no-runtime proof. | R1 |
| setup receipt + rollback artifact | PASSIVE_FOUNDATION | `builder_ii/setup_rollback.py`, generic records in `builder_ii/receipt_records.py` and `builder_ii/rollback_artifacts.py`, `tests/test_setup_rollback.py`, `tests/test_receipt_records.py`, `tests/test_rollback_artifacts.py`; command: `builder-setup rollback-snapshot` | R1.2 adds setup rollback snapshot planning with setup/overlay digests, prior existence markers, content digests, redacted previews, and future rollback operations. Setup receipt, changed-path receipt, rollback execution, ledger event, and replay binding are missing. | R1 |
| model registry | PASSIVE_FOUNDATION | `builder_ii/model_client_registry.py`, `tests/test_model_client_registry.py`; command: `builder-model-policy validate/render/dry-run` | Registry says `RECORDED_ONLY`, `current_state=DISABLED`, `executes_model=False`, `provider_calls=DISABLED`. Missing execution gateway. | B6 |
| model routing | PASSIVE_FOUNDATION | `builder_ii/model_routing_policy.py`, `builder_ii/model_policy_cli.py`, `tests/test_model_routing_policy.py`; command: `builder-model-policy render/dry-run` | Recommendation is `RECOMMENDATION_ONLY`; no provider calls, cost budgets, prompt digests, receipts, replay declaration. | B6 |
| model/provider execution | MERGED_BUT_NOT_OPERATIONAL | Legacy live path: `builder_ii/direct_chat.py` uses `httpx.post`; `builder_ii/backends.py` can `subprocess.Popen`; root commands `builder ask/start`; tests: `tests/test_direct_chat.py` | Live local model calls exist, but not as governed provider execution. Missing proposal, approval if needed, envelope digest, prompt/context digest, cost/token/rate limits, receipt, ledger, replay statement. | B6 |
| tool registry | PASSIVE_FOUNDATION | `builder_ii/tool_registry.py`, `builder_ii/tools_cli.py`; commands: `builder-tools list/check/missing` | Registry and version probes exist; no invocation envelope or effect classification. `check` uses subprocess version probes as operator-managed tooling. | B7 |
| MCP/tool invocation | DESIGN_ONLY | `docs/plan/MCP_POLICY_ARTIFACT_RFC.md`, `docs/plan/MCP_TOOL_INVENTORY_RFC.md`, `docs/plan/GOOSE_DEEPAGENTS_MCP_SEAM.md`; command: none | No MCP server inventory implementation, policy validator, tool call envelope, approval, receipt, rollback/no-rollback classification, or audit. | B7 |
| passive orchestration assignment | PASSIVE_FOUNDATION | `builder_ii/orchestration_assignment.py`, `builder_ii/orchestration_cli.py`, `tests/test_orchestration_assignment.py`; commands: `builder-orchestration plan/render-assignment/dry-run/validate` | Assignment binds artifacts by digest but starts no agents. Runtime assignment execution must wait for B1/B5. | B5 |
| workflow/event ledger | PASSIVE_FOUNDATION | `builder_ii/workflow_orchestrator.py`, `workflow_records.py`, `event_ledger.py`, `workflow_cli.py`, `ledger_cli.py`, `tests/test_workflow_ledger.py`; commands: `builder-workflow *`, `builder-ledger *` | Ledger records passive workflow events only. Missing runtime event kinds for actual reads, execution, model/tool calls, rollback, memory mutation. | B1 then B6/B7/B8 |
| replay/audit | PASSIVE_FOUNDATION | `builder_ii/event_ledger.py`, `builder_ii/artifact_chain_verification.py`, `tests/test_workflow_ledger.py`, `tests/test_artifact_chain_verification.py`; commands: `builder-ledger replay/audit/export`, `builder-chain verify` | Replay validates passive event order and artifact links, not operational side effects. Need replay policy for non-deterministic execution receipts. | B1 |
| readonly founder demo | PASSIVE_FOUNDATION | `builder_ii/readonly_founder_demo.py`, `builder_ii/targets_cli.py`, `tests/test_readonly_demo.py`, `tests/test_readonly_demo_idempotence.py`; command: `builder-targets readonly-founder-demo` | Demo writes passive inspection, patch proposal, verification plan, events, status. It does not inspect live content beyond artifacts or run verification. | defer after R0 |
| orchestration founder demo wrapper | PASSIVE_FOUNDATION | `builder_ii/readonly_founder_demo.py`, `docs/demos/CORE_READONLY_FOUNDER_DEMO.md`; command: `builder-targets readonly-founder-demo` | Wrapper is a passive workflow/event demonstration. Missing operator golden path that runs real governed read/verify loops. | B9 |
| HITL promotion bridge | PASSIVE_FOUNDATION | `builder_ii/hitl_promotion_artifacts.py`, `builder_ii/hitl_promotion_cli.py`, `tests/test_hitl_promotion_artifacts.py`; commands: `builder-hitl promotion-request/review/decision/approval-boundary/rejection-record/validate-promotion` | Approval boundary is for candidate design only and requires a separate execution candidate. No execution authority. | B1 |
| execution candidate manifests | PASSIVE_FOUNDATION | `builder_ii/execution_candidate_manifest.py`, `builder_ii/execution_candidate_manifest_cli.py`, `tests/test_execution_candidate_manifest.py`; commands: `builder-hitl candidate-manifest/validate-candidate-manifest` | Manifest validates intent, rollback requirements, verification requirements, and command previews; it never activates. Missing executor. | B1 |
| HITL-approved verification execution | PASSIVE_FOUNDATION | `builder_ii/verification_execution_plan.py`, `builder_ii/verification_execution_approval.py`, `builder_ii/verification_execution_receipt.py`, `builder_ii/verification_execution_runner.py`, `builder_ii/verification_execution_ledger.py`, `builder_ii/verification_execution_plan_cli.py`, `builder_ii/hitl_command_execution.py`, `builder_ii/hitl_execution_records.py`, `builder_ii/hitl_verification_candidate.py`, `builder_ii/hitl_execution_cli.py`, `tests/test_verification_execution_plan.py`, `tests/test_verification_execution_plan_cli.py`, `tests/test_verification_execution_approval.py`, `tests/test_verification_execution_approval_cli.py`, `tests/test_verification_execution_approval_authority.py`, `tests/test_verification_execution_receipt.py`, `tests/test_verification_execution_receipt_cli.py`, `tests/test_verification_execution_runner.py`, `tests/test_verification_execution_ledger.py`, `tests/test_hitl_command_execution.py`, `tests/test_hitl_execution_records.py`, `tests/test_hitl_verification_candidate.py`; commands: `builder-verify plan/validate-plan/approve-plan/validate-approval/validate-receipt/run-approved`, `builder-ledger index-receipt/query-receipts/validate-receipts/reconstruct-receipts`, `builder-hitl request/receipt/validate` | B1.1 adds a digest-stable passive verification execution plan artifact only. B1.2 adds a digest-bound HITL approval artifact only. B1.3A/B add a receipt contract and bounded `platform_status` runner. B1.4A/B/C/D add passive verification ledger indexing, query, integrity reporting, reconstruction reporting, and closure docs. Broader execution profiles, live read authority, patch authority, model/MCP/Goose/deepagents runtime, and B2 write authority remain unpromoted. | B2.0 |
| HITL patch proposal | DESIGN_ONLY | `builder_ii/hitl_patch_proposal.py`, `builder_ii/goose_command_proposal.py`, `tests/test_hitl_patch_proposal.py`, `tests/test_goose_command_proposal.py`; commands: `builder-goose propose-command` exists for commands, not patches | No diff/patch proposal artifact with exact patch digest, target profile, approval binding, rollback spec, and verification profile. | B2 |
| HITL patch application | DESIGN_ONLY | `builder_ii/hitl_patch_proposal.py`, `docs/HITL_PATCH_APPLICATION.md`, `tests/test_hitl_patch_proposal.py`; command: none active | Patch apply is explicitly denied. Must wait for B1 verification execution and then bind patch digest, clean git state, approval, rollback, postflight diff, receipt, ledger. | B2 after B1 |
| rollback execution | ARTIFACT_ONLY | `builder_ii/rollback_artifacts.py`, `tests/test_rollback_artifacts.py`; command surface through record/chain helpers | Rollback plan and receipt templates exist; receipt is `NOT_EXECUTED`. Missing rollback executor and mutation proof. | B2 |
| postflight verification | ARTIFACT_ONLY | `builder_ii/execution_postflight_records.py`, `tests/test_execution_postflight_records.py`; command surface through HITL records/chain | Postflight is `NOT_RUN`, verification may record `PASS/FAIL` text but performed actions remain empty. Missing generated postflight from real execution. | B1 |
| Goose setup | MERGED_BUT_NOT_OPERATIONAL | `builder_ii/goose_setup.py` now provides passive setup metadata and redirect payloads; `builder_ii/cli.py setup/start`; tests cover launcher/setup | R1.4 removes legacy setup writes from `builder setup`, but Goose runtime promotion, recipe execution receipts, and governed runtime activation remain missing. | B4 after R0/B3 |
| Goose readonly runtime | MERGED_BUT_NOT_OPERATIONAL | Passive governed surface: `builder_ii/goose_session.py`, `goose_readonly.py`, `goose_inspection.py`, `goose_cli.py`, `tests/test_goose_readonly.py`, `tests/test_goose_inspection.py`; legacy launcher: `builder_ii/goose_launcher.py`; commands: `builder-goose manifest/readonly-audit/inspect-readonly/validate-*` | Governed CLI does not start Goose. Legacy `launch_goose_session` can start Goose but not under receipts/ledger/no-mutation proof. | B4 |
| Goose command proposals | PASSIVE_FOUNDATION | `builder_ii/goose_command_proposal.py`, `tests/test_goose_command_proposal.py`; command: `builder-goose propose-command` | Proposal records require approval and say `executed=False`; no execution envelope or receipt. | B1/B4 |
| deepagents policy/readiness | PASSIVE_FOUNDATION | `builder_ii/deepagents_policy.py`, `deepagents_readiness.py`, `deepagents_bridge.py`, `tests/test_deepagents_policy.py`, `tests/test_deepagents_readiness.py`, `tests/test_deepagents_bridge.py`; commands: `builder-deepagents policy/readiness/validate*` | Policy/readiness may inspect import metadata but construct no agents. Missing runtime harness. | B5 |
| deepagents passive work artifacts | PASSIVE_FOUNDATION | `builder_ii/deepagents_work_artifacts.py`, `builder_ii/deepagents_cli.py`, `tests/test_deepagents_work_artifacts.py`; commands: `builder-deepagents work-plan/assign-subagent/record-result/review-result/request-human-gate/record-blocked-action/proposal-result/validate-work-artifact` | Work plan, assignment, result, review, gate, blocked-action, and proposal-result artifacts all deny model/tool/shell/Goose/deepagents/MCP/network/writes. | B5 |
| deepagents runtime/subagents | DESIGN_ONLY | `builder_ii/deepagents_cli.py` has `delegate` fail-closed; `docs/DEEPAGENTS_POLICY.md`, `docs/plan/DEEPAGENTS_WORK_ARTIFACTS_RFC.md`; tests assert disabled runtime | No actual `create_governed_deep_agent` invocation, subagent execution, model/tool receipt, or review-to-result bridge. | B5 |
| notes/handoff artifacts | PASSIVE_FOUNDATION | `builder_ii/notes_cli.py`, `handoff_artifacts.py`, `handoff_notes.py`, `handoff_bundle_records.py`, `tests/test_handoff_notes.py`, `tests/test_handoff_bundle_records.py`; commands: `builder-notes handoff/validate`, `builder-handoff` | Handoffs summarize and reference evidence; they do not mutate a memory store or prove execution. | defer operational memory |
| artifact memory | PASSIVE_FOUNDATION | `builder_ii/artifact_memory.py`, `builder_ii/memory_cli.py`, `docs/ARTIFACT_MEMORY.md`; commands: `builder-memory atom`, `builder-memory index`, `builder-memory search`, `builder-memory reconstruct` | Explicit memory atoms, indexes, deterministic search, and replay-stable reconstruction now exist. Hidden memory, opaque vector stores, autonomous writes, and runtime authority remain disabled. Remains PASSIVE_FOUNDATION by design; docs and UX do not imply operational memory mutation. | defer operational memory |
| operator quickstart/golden path | OPERATIONALLY_VERIFIED | `docs/OPERATOR_QUICKSTART.md`, `builder_ii/workflow_orchestrator.py`, `tests/test_prepare_package_quickstart.py`, `tests/test_workflow_ledger.py`; commands: `builder-session *`, `builder-workflow *` | Golden path UX generated from truth matrix, command authority, and B8 memory artifacts. Demonstrates a complete governed local workflow without runtime execution. Does not promote runtime execution or operational memory authority. | B9 complete |
| platform doctor/status/audit | MERGED_BUT_NOT_OPERATIONAL | `builder_ii/cli.py doctor/status`, `docs/PLATFORM_COMPLETION_AUDIT.md`, `tests/test_platform_completion_audit.py`; commands: `builder doctor`, `builder status` | Doctor/status check local backend/Goose/model environment, not truth matrix. Existing audit doc is static and phrase-tested, not source-derived. | R0 |
| release proof/quality gates | PASSIVE_FOUNDATION | `scripts/verify_v0_release.py`, `docs/RELEASE_PROOF.md`, `builder_ii/quality_gates.py`, `builder_ii/quality_cli.py`, tests pass; commands: `builder-quality plan/validate`, proof harness | Proof harness proves passive artifact chain and no target mutation. It does not prove operational runtime. Quality gates are plans, not runners. | R0 then B1 |
| command authority as runtime gate | MERGED_BUT_NOT_OPERATIONAL | `builder_ii/command_authority.py`, `docs/COMMAND_AUTHORITY.md`, `tests/test_command_authority.py`; command surface: registry docs only | Registry is explicit metadata and docs say metadata is not runtime permission. No dynamic interceptor prevents legacy commands or future commands from crossing authority. | R0 then B1/B6/B7 |
| docs truth enforcement | MERGED_BUT_NOT_OPERATIONAL | `docs/PLATFORM_COMPLETION_AUDIT.md`, `docs/FOUNDATION_STATUS.md`, `docs/ROADMAP.md`, `tests/test_platform_completion_audit.py`, `tests/test_foundation_status.py` | Existing tests lock phrases like "foundation is complete"; no test compares doc claims against capability states. README stale line says model routing RFC exists although implementation exists. | R0 |

## 3. False-completion audit

| Location | Claim pattern | Classification | Why it matters | Required fix |
|---|---|---|---|---|
| `docs/PLATFORM_COMPLETION_AUDIT.md` | "Completed Foundation" and "fully completed and verified" over many artifacts | must-fix before next release | The document is static and tests only assert phrase presence. It does not derive capability state from code, commands, tests, registry, or ledger. | Replace with generated/validated truth matrix or reword all rows to state labels. |
| `tests/test_platform_completion_audit.py` | `test_lists_completed_artifacts` locks the old completion wording | must-fix before next release | The test enforces documentation shape, not truth. It would pass while docs overstate runtime readiness. | Convert to matrix validation and doc/code consistency tests. |
| `docs/FOUNDATION_STATUS.md` | "The artifact-first foundation is complete" and "ready for the next phase" | confusing wording | Acceptable only if scoped to passive artifacts. Current file is too short to preserve the boundary. | Reword to "passive foundation state: PASSIVE_FOUNDATION" and list disabled runtime gates. |
| `tests/test_foundation_status.py` | Asserts the "foundation is complete" sentence | must-fix before next release | Locks ambiguous status language as an invariant. | Replace with exact state-label assertions. |
| `docs/ROADMAP.md` | "v0 release" and "full governed artifact platform is built, tested, and proven" | confusing wording | The same paragraph says runtime execution remains ungated, but "full platform" can be read as operational platform. | Add "passive artifact platform" everywhere and link to R0 matrix. |
| `README.md` | "builder-II v0 includes the full governed artifact platform" | confusing wording | The list mixes legacy live helpers (`builder ask`, backend startup) with passive governance artifacts. | Split "legacy operator-managed helpers" from "canonical governed passive lane." |
| `README.md` | "Model routing policy artifact (RFC exists, artifact not yet built)" under Not Yet Promoted | must-fix before next release | PR #142 and `builder_ii/model_routing_policy.py` implement passive model routing artifacts. The README is stale. | Update to "passive model routing exists; provider execution gateway missing." |
| `README.md` and `builder setup` docs | Productized setup language around `.env`, Goose config, skills, and doctor/status | confusing wording | Legacy direct-setup wording must be replaced with governed `builder-setup` guidance and an explicit statement that `builder setup` is now a fail-closed redirect. | R1 must split legacy operator-managed setup from the governed onboarding kernel. |
| `docs/OPERATOR_QUICKSTART.md` | "first complete operator lane" | harmless wording if scoped | The doc clearly says no execution/model/runtime authority and no completed verification. | Prefer "first passive operator lane." |
| `docs/RUNTIME_GOVERNANCE_RELEASE_AUDIT.md` | "runtime-governance foundation complete" | harmless wording if scoped | It explicitly says all execution capabilities are disabled and not enabled. | Link to R0 matrix once available. |
| `docs/BUILDER_PLATFORM_RELEASE_AUDIT.md` | "platform closure checkpoint" | harmless wording if scoped | It says no hidden runtime authority and no command execution by default. | Preserve but add state labels. |
| `docs/plan/MASTERPIECE_PLAN.md` | "artifact foundation is complete" and "complete through PR #..." | confusing wording | The plan is future-looking, but "complete" is overloaded across passive and operational states. | Convert history sections to state labels. |
| `docs/plan/PASSIVE_EXECUTION_CANDIDATE_MANIFEST_RFC.md` | "Goal 2/3/4 complete" | harmless wording if scoped | It repeatedly says passive and candidate-only. | Add "PASSIVE_FOUNDATION" labels. |
| PR #151 title | `feat(core): implement passive read-only founder demo gate` | confusing wording | Uses `core` scope even though builder-II is generic-first; implementation is passive target demo. | Future PR titles should avoid CORE scope unless code is CORE-target-specific. |
| `docs/CAPABILITY_PROMOTION.md` rows | HITL receipt "Records outcome metadata of completed execution"; rollback receipt "completed manual rollback" | dangerous false promotion | Current receipt modules create `NOT_EXECUTED` templates. Docs describe future/manual evidence, which can be mistaken for platform execution. | Split current `ARTIFACT_ONLY` from future/operator-supplied evidence semantics. |

## 4. Operational gap analysis

### Missing config/onboarding authority

- No versioned builder-II config schema exists. `builder_ii/config.py` loads `.env` plus process env and still exposes legacy `CORE_*` names as the primary operator knobs.
- No explicit source precedence artifact defines which input wins across CLI flags, env, `.env`, target profile, profile pack, generated Goose config, and session config.
- No interactive setup wizard or non-interactive plan/apply/validate contract exists for target repo, artifact root, model/backend, profiles, recipes, skills, Goose writes, and capability state.
- Before R1.4, `builder setup` could write Goose config, `.goosehints`, session context, and skill installs without setup receipt, rollback artifact, approved write boundary, or ledger event.
- Execution authority should not be promoted until target root, artifact root, active profiles, config source, and setup rollback semantics are canonical and auditable.

### Missing execution authority

- No B1 verification runner exists. `builder_ii/harness.py` runs legacy CORE verification through `subprocess.run` without envelope digest, bounded capture, timeout, env allowlist, git mutation detection, approval artifact, receipt artifact, postflight, or ledger event.
- `builder_ii/hitl_execution_records.py` creates request and `NOT_EXECUTED` receipt templates only.
- `builder_ii/hitl_verification_candidate.py` constrains intent but explicitly sets `executes_now=False`.

### Missing read authority

- `builder_ii/readonly_inspection_reports.py` can hash explicit files and `builder_ii/goose_inspection.py` can record bounded metadata, but there is no unified target-bound read authority with mandatory allowlist, budgets, secret/path traversal guards, artifact-root separation, content receipt policy, and ledger event.
- Legacy context path `builder_ii/context_pack.py` and `builder-context` remain operator-managed external scan surfaces.

### Missing write/patch authority

- `builder_ii/hitl_patch_proposal.py` is design-only and forbids patch application.
- No patch digest, clean-state binding, approved apply, postflight diff, rollback execution, or verification binding exists.
- No direct commit/push automation should be added; commit/push remains out of scope until separately promoted.

### Missing model authority

- Passive `builder-model-policy` exists.
- Legacy `builder ask` and `builder start` can call/start local model backends, but no governed provider gateway records model call envelope, prompt/context digest, cost/token/rate limits, receipt, failure mode, replay declaration, or approval boundary.

### Missing tool/MCP authority

- `builder-tools` can inventory/check installed tools.
- MCP is design-only RFC. No MCP inventory artifact, policy validator, tool call envelope, approval, receipt, or rollback/no-rollback classification exists.

### Missing runtime/session authority

- Goose setup/launcher is operational in legacy Tier 2 helpers.
- Governed `builder-goose` emits manifests/audits/proposals and does not start Goose.
- Deepagents runtime and subagent construction are explicitly denied.

### Missing memory authority

- Handoffs and notes are artifacts.
- Artifact memory now exists as a passive foundation: explicit memory atoms, indexes, deterministic search, and replay-stable reconstruction artifacts are implemented.
- Hidden memory, opaque vector stores, autonomous durable memory writes, and runtime authority remain disabled.

### Missing status/UX/operator authority

- `builder doctor/status` report local environment and runtime health, not platform completion state.
- Existing completion audit is static. Docs truth is not machine-enforced.
- No single golden path command walks a user from target registration through context, model route, orchestration, HITL approval, verification, patch/rollback, ledger, and handoff.

## 5. Master completion architecture

### Data flow

1. Config/onboarding kernel R1 resolves builder-II config from explicit sources, records source precedence, establishes target repo, artifact root, active target/agent/verification profiles, model/backend selection, Goose overlay, installed recipes/skills, and the disabled/passive/operational capability map.
2. Target repo registration creates a `target_profile` and target repo state snapshot with canonical root, clean git state, artifact root outside source mutation paths, ignored paths, secret patterns, and target adapter.
3. Setup apply, when approved, emits a setup receipt, changed-path list, prior-config snapshot, rollback artifact, and ledger event; dry-run emits no mutation proof.
4. Profile/context assembly consumes target profile, agent profile, verification profile, repo map/read receipts, context pack, profile pack, setup refs, and memory reconstruction refs.
5. Model routing produces a passive routing recommendation, then B6 upgrades selected provider calls through a model execution envelope with prompt/context digest and budget.
6. Orchestration planning binds task, agent profile, model recommendation, context, tools, HITL policy, outputs, and handoff refs by digest.
7. Deepagents/subagent planning remains proposal-only until B5 constructs optional governed subagents under a promoted runtime harness.
8. HITL proposal/approval creates a human-visible request, digest-bound approval, and approval boundary. Approval never implies execution.
9. Verification execution B1 consumes the exact approved envelope and writes stdout/stderr artifacts, receipt, postflight, verification record, ledger event, and chain binding.
10. Read-only runtime B3 provides target-bound file metadata/content receipts under explicit policy and budgets.
11. Patch proposal/application B2 consumes B1 capability, exact patch digest, clean target repo state, approval artifact, rollback artifact, verification profile, postflight diff, receipt, and ledger event.
12. Model/tool execution B6/B7 use the same envelope/receipt/ledger grammar, with cost, credential, network, mutation, and rollback/no-rollback classification.
13. Notes/memory/handoff B8 converts validated artifacts into memory atoms and searchable handoff records with staleness and review state.
14. Event ledger/replay/audit records every authority-bearing operation with payload digest, policy snapshot, subject refs, postflight refs, and replay limits.
15. Operator status/doctor/golden path B9 generates product UX from the truth matrix, setup state, and ledger, not from status prose.

### Authority flow

Authority only moves by digest-bound promotion:

`proposal -> human approval -> envelope digest -> execution -> receipt -> postflight -> verification -> ledger -> replay/audit -> handoff`.

Every forward operator has its corrective counterpart:

- setup apply -> setup receipt plus rollback artifact
- read -> read receipt plus secret/path guard
- execute -> postflight plus mutation detector
- patch -> rollback plus verification
- model call -> budget/cost receipt plus replay declaration
- tool/MCP call -> effect classification plus rollback/no-rollback proof
- memory write -> staleness/review state plus source refs

No artifact is authority by itself. No approval is execution. No execution is verification. No verification is promotion unless ledger/replay and rollback/no-mutation evidence close.

## 6. Promotion doctrine

A capability can promote only when it has docs, tests, command surface, failure mode, human approval boundary if authority-bearing, output artifact, rollback or no-mutation proof, verification path, command authority registry entry, and replay/ledger integration if operational.

### DESIGN_ONLY -> ARTIFACT_ONLY

Allowed when an RFC/spec becomes a schema, validator, docs, tests, and CLI that emits or validates an artifact. The artifact must state `artifact_is_authority=false` and all runtime authority disabled.

### ARTIFACT_ONLY -> PASSIVE_FOUNDATION

Allowed when the artifact participates in the platform graph: command authority entry, registry/chain/index coverage where relevant, docs, tests, failure cases, and cross-artifact digest binding. Still no authority-bearing operation.

### PASSIVE_FOUNDATION -> OPERATIONALLY_VERIFIED

Allowed only when a promoted command actually performs the bounded operation under policy and produces receipt, postflight/no-mutation or rollback proof, verification evidence, ledger event, replay/audit support, and command authority promotion. For authority-bearing operations, a human approval boundary must be part of the envelope.

### Forbidden shortcuts

- `approved` does not mean executed.
- `executed` does not mean verified.
- `valid artifact` does not mean authority.
- `receipt template` does not mean outcome.
- `operator-managed legacy helper` does not mean governed runtime promotion.
- `model route recommendation` does not mean provider call permission.

## 7. PR ladder to finish the system

### R0 - Anti-false-completion truth machine

Goal: make the platform status mechanically truthful before any new authority is added.

Files likely touched: `builder_ii/platform_completion_audit.py`, `builder_ii/platform_status_cli.py`, `pyproject.toml`, `builder_ii/command_authority.py`, `docs/COMMAND_AUTHORITY.md`, `docs/PLATFORM_COMPLETION_AUDIT.md`, `docs/FOUNDATION_STATUS.md`, `docs/ROADMAP.md`, `README.md`, `tests/test_platform_completion_truth.py`, `tests/test_docs_truth_enforcement.py`, `tests/test_command_authority.py`.

State change: docs truth enforcement `MERGED_BUT_NOT_OPERATIONAL` -> `PASSIVE_FOUNDATION`; platform doctor/status/audit `MERGED_BUT_NOT_OPERATIONAL` -> `PASSIVE_FOUNDATION`. Config/onboarding rows are added to the machine-readable matrix but remain non-operational until R1.

Command surface changes: add `builder-platform status`, `builder-platform matrix`, `builder-platform audit-docs` or equivalent; add command authority registry entries.

Artifact kinds: `builder_ii.platform_completion_matrix`, `builder_ii.platform_truth_audit_report`.

Command authority changes: new Tier 1 validation/artifact-only commands; no runtime/model/shell/source writes beyond explicit output artifact.

Tests required: exact state-label coverage, all required rows present including config/onboarding, command authority/docs consistency, docs phrase denylist, stale README claim test, fail if docs claim COMPLETE/ready while matrix says DISABLED or non-operational.

Docs required: replace ambiguous completion language with state labels; explain passive-foundation vs operational capability; state that R1 must precede B1 because execution authority depends on canonical, auditable, reversible configuration.

Failure modes: unknown capability row, missing command registry entry, stale docs phrase, unsupported state label, command surface/doc drift.

Rollback/no-mutation proof: output artifacts only; no target repo mutation; delete generated truth report.

Acceptance criteria: `CORE_REPO_PATH=. uv run pytest -q`, `uv run python scripts/verify_v0_release.py --output-dir /tmp/...`, and new truth CLI all pass; no docs claim operational status for disabled capabilities.

Non-goals: no B1 execution runner, no patch apply, no model/tool runtime.

### R1 - Config + Onboarding Kernel

Goal: establish canonical, auditable platform/target/runtime configuration before any execution authority is promoted.

R1.1 files touched: `builder_ii/config.py`, new `builder_ii/config_schema.py`, new `builder_ii/config_sources.py`, new `builder_ii/setup_plan.py`, new `builder_ii/config_cli.py`, new `builder_ii/setup_cli.py`, `builder_ii/command_authority.py`, `pyproject.toml`, `README.md`, `docs/COMMAND_AUTHORITY.md`, `docs/PLATFORM_COMPLETION_AUDIT.md`, new `docs/CONFIG_ONBOARDING.md`, tests.

R1.1 state change: config schema `DESIGN_ONLY` -> `PASSIVE_FOUNDATION`; config source precedence `DESIGN_ONLY` -> `PASSIVE_FOUNDATION`; non-interactive setup/apply/validate stays `MERGED_BUT_NOT_OPERATIONAL` with passive plan/validate evidence only; Goose config overlay/rollback stays `MERGED_BUT_NOT_OPERATIONAL`; interactive setup wizard stays `NOT_STARTED`; setup receipt + rollback artifact stays `NOT_STARTED`.

R1.1 command surface changes: add `builder-config schema`, `builder-config resolve`, `builder-config validate`, `builder-setup plan`, and `builder-setup validate-plan`.

R1.1 artifact kinds: `builder_ii.config_schema`, `builder_ii.config_source_resolution`, and `builder_ii.setup_plan`.

R1.1 command authority changes: all new commands are Tier 1 artifact-only or validation-only. They do not start Goose, call models, construct deepagents, invoke MCP/tools, run shell commands, apply patches, mutate target repos, or add setup apply/rollback authority.

R1.1 tests required: config schema validation, env/`.env`/CLI/profile precedence, legacy alias warnings, generic-over-legacy precedence, redaction of secrets, canonical target root and artifact root checks, unsafe artifact-root policy, setup plan no-mutation proof, deterministic plan digest, disabled capability map, command authority registry entries, platform matrix state, and docs truth integration.

R1.1 docs required: config source precedence, passive setup plan semantics, legacy `CORE_*` compatibility boundary, capability defaults, and no-runtime guarantee. Setup apply, setup rollback, Goose overlay writes, setup receipts, and interactive wizard docs wait for later R1 slices.

R1.2 files touched: new `builder_ii/setup_overlay.py`, new `builder_ii/setup_rollback.py`, updated `builder_ii/setup_plan.py`, `builder_ii/setup_cli.py`, `builder_ii/command_authority.py`, `builder_ii/platform_completion_audit.py`, docs, and tests.

R1.2 state change: Goose config overlay/rollback `MERGED_BUT_NOT_OPERATIONAL` -> `PASSIVE_FOUNDATION` for passive overlay and rollback snapshot planning only; setup receipt + rollback artifact `NOT_STARTED` -> `PASSIVE_FOUNDATION` for rollback snapshot planning only; non-interactive setup/apply/validate remains `MERGED_BUT_NOT_OPERATIONAL`; skill generator/installer/validator remains `MERGED_BUT_NOT_OPERATIONAL`; interactive setup wizard stays `NOT_STARTED`.

R1.2 command surface changes: add `builder-setup overlay-plan`, `builder-setup validate-overlay-plan`, `builder-setup rollback-snapshot`, and `builder-setup validate-rollback-snapshot`.

R1.2 artifact kinds: `builder_ii.setup_overlay_plan` and `builder_ii.setup_rollback_snapshot`.

R1.2 command authority changes: all new commands are Tier 1 artifact-only or validation-only. Runtime execution, model execution, shell execution, source writes except explicit output artifacts, Goose runtime, deepagents runtime, MCP/tool invocation, patch authority, setup apply, and setup rollback execution are disabled.

R1.2 non-goals: no interactive wizard, no setup apply, no setup rollback execution, no Goose config writes, no `.goosehints` writes, no skill copying, no recipe installation writes, no B1 execution runner, no model/provider calls, no MCP/tool calls, no Goose runtime, no deepagents runtime, no patch authority, no autonomous writes, no commit/push automation.

Failure modes: invalid target repo, missing artifact root, artifact root inside source tree, conflicting config sources, stale setup receipt, unsupported profile id, Goose config conflict, skill install conflict, rollback snapshot unavailable, secret detected in artifact, disabled capability requested.

Rollback/no-mutation proof: `builder-setup plan`, `builder-setup validate-plan`, `builder-setup overlay-plan`, `builder-setup validate-overlay-plan`, `builder-setup rollback-snapshot`, and `builder-setup validate-rollback-snapshot` emit no-mutation proof or validation-only reports. No `builder-setup apply` or `builder-setup rollback` command exists in R1.2.

Acceptance criteria: `CORE_REPO_PATH=. uv run pytest -q`; passive setup plan/overlay/rollback-snapshot tests pass in temp dirs; R0 matrix includes all config/onboarding rows; no setup command starts Goose, models, deepagents, MCP, or shell execution; generated docs and command authority registry agree.

Non-goals: no B1 verification execution, no patch application, no provider call, no MCP/tool call, no Goose runtime promotion, no deepagents runtime, no autonomous commit/push.

### B1 - HITL-approved verification execution

B1.1 verification execution plan artifact.

Files likely touched: `builder_ii/verification_execution_plan.py`, `builder_ii/verification_execution_plan_cli.py`, `builder_ii/command_authority.py`, docs/tests.

State change: HITL-approved verification execution `ARTIFACT_ONLY` -> `PASSIVE_FOUNDATION` for passive planning only, not runner authority.

Commands: `builder-verify plan`, `builder-verify validate-plan`.

Artifacts: `builder_ii.verification_execution_plan` with canonical digest, `planned_only` mode, structured command profile refs, passive planned steps, approval-required marker, execution disabled marker, and explicit disabled authority for arbitrary shell, subprocess, source writes, patch/git/model/MCP/Goose/deepagents/autonomous/B2 authority.

Authority changes: Tier 1 artifact-only/validation-only. `builder-verify plan` may write only the explicit output artifact. It does not run tests, execute shell/subprocess, call models/tools, invoke MCP, start Goose/deepagents, apply patches, mutate git, or promote B2 patch authority.

Tests: valid artifact validation, digest drift, execution enabled rejection, approval false rejection, artifact authority rejection, missing disabled authority, raw shell string rejection, shell separator rejection, forbidden patch/model/MCP/Goose/deepagents authority claims, CLI artifact write/JSON output.

Failure modes: invalid plan shape, digest drift, enabled execution, raw shell string, command injection token, forbidden authority overclaim, missing target or verification profile.

Rollback/no-mutation proof: plan is artifact-only and has no mutation authority beyond explicit output artifact creation.

Acceptance: canonical digest stable for identical payloads; no verification execution.

Non-goals: no subprocess execution, no pytest execution, no shell execution, no model/tool call, no MCP/Goose/deepagents runtime, no patch application, no B2 authority.

B1.2 HITL approval binding for verification plans.

Files likely touched: `builder_ii/verification_execution_approval.py`, `builder_ii/verification_execution_plan_cli.py`, `builder_ii/artifact_index_records.py`, `builder_ii/artifact_chain_verification.py`, `builder_ii/command_authority.py`, docs/tests.

State change: HITL-approved verification execution remains `PASSIVE_FOUNDATION`; B1.2 binds human approval to an exact passive plan digest only and does not enable execution.

Commands: `builder-verify approve-plan`, `builder-verify validate-approval`.

Artifacts: `builder_ii.verification_execution_approval` with canonical digest, exact `plan_digest` binding, approved command-profile subset, approved step-id subset, explicit disabled authority, `execution_enabled=false`, `approval_enables_execution=false`, `artifact_is_authority=false`, and `requires_b1_3_runner=true`.

Authority changes: Tier 1 artifact-only/validation-only. `builder-verify approve-plan` may write only the explicit output approval artifact. Neither command runs tests, executes shell/subprocess, calls models/tools, invokes MCP, starts Goose/deepagents, applies patches, mutates git, or promotes B2 authority.

Tests: valid approval validation, digest drift, plan digest mismatch, target/profile mismatch, approved command profile outside plan rejection, approved step id outside plan rejection, execution enabled rejection, approval-enables-execution rejection, artifact authority rejection, missing disabled authority rejection, raw shell string rejection, forbidden patch/model/MCP/Goose/deepagents authority claims, CLI artifact write/JSON output, artifact index registration, artifact chain registration, and authority-row coverage.

Failure modes: invalid plan shape, digest drift, subset drift against plan, enabled execution flags, raw shell string, command injection token, forbidden authority overclaim, or missing disabled authority.

Rollback/no-mutation proof: approval is artifact-only and has no mutation authority beyond explicit output artifact creation.

Acceptance: canonical approval digest is stable for identical payloads; approval binds only to a plan digest; B1.3 runner remains missing.

Non-goals: no subprocess execution, no pytest execution, no shell execution, no model/tool call, no MCP/Goose/deepagents runtime, no patch application, no B2 authority.

B1.3 CLI + command authority + ledger/chain.

Files likely touched: `builder_ii/event_ledger.py`, `workflow_orchestrator.py`, `artifact_chain_verification.py`, docs/tests.

State change: workflow replay/audit becomes operational for B1 event class.

Commands: same as B1.2 plus `builder-ledger replay/audit` support for execution events.

Artifacts: `builder_ii.execution_event`, chain binding with B1 receipt/postflight/verification.

Authority changes: command authority marks B1 command as HITL runtime, not generic shell.

Tests: artifact chain validation, replay order, ledger event payload digest, docs truth.

Non-goals: write/patch authority.

### B2 - HITL patch application and rollback

Goal: apply exact patches under approval after B1 exists.

Files likely touched: `builder_ii/hitl_patch_proposal.py`, `builder_ii/hitl_patch_apply.py`, `builder_ii/rollback_artifacts.py`, `builder_ii/execution_postflight_records.py`, `builder_ii/command_authority.py`, docs/tests.

State change: HITL patch proposal `DESIGN_ONLY` -> `PASSIVE_FOUNDATION`; HITL patch application `DESIGN_ONLY` -> `OPERATIONALLY_VERIFIED` for approved patch apply; rollback execution `ARTIFACT_ONLY` -> `OPERATIONALLY_VERIFIED` for generated rollback.

Commands: `builder-hitl propose-patch`, `builder-hitl apply-patch`, `builder-hitl rollback`.

Artifacts: patch proposal, patch digest, pre-apply git state, rollback patch/artifact, apply receipt, postflight diff, verification binding, ledger event.

Authority changes: Tier 3, approval required, no autonomous commit/push.

Tests: digest mismatch, dirty repo rejection, target mismatch, rollback restore, verification binding, no direct commit/push.

Failure modes: patch conflict, digest drift, unclean target repo, postflight diff mismatch, verification fail, rollback fail.

Rollback/no-mutation proof: rollback artifact required before apply; postflight diff and verification required.

Acceptance: exact approved patch applies, verifies, and can roll back without commit/push.

Non-goals: model-generated patches as authority, network/package install, direct PR creation.

### B3 - Governed read-only runtime

Goal: promote read authority into a unified, target-bound runtime read surface.

Files likely touched: `builder_ii/readonly_authority.py`, `builder_ii/readonly_inspection_reports.py`, `builder_ii/goose_inspection.py`, `builder_ii/event_ledger.py`, command authority, docs/tests.

State change: read-only repo inspection from `PASSIVE_FOUNDATION`/candidate -> `OPERATIONALLY_VERIFIED` for approved read policies.

Commands: `builder-readonly policy`, `builder-readonly read`, `builder-readonly validate`.

Artifacts: read policy, read receipt, file hash/content receipt as policy permits, denied-read record, ledger event.

Authority changes: Tier 0 or Tier 1 for metadata-only; approval required if content capture is enabled.

Tests: target-bound allowlist, path traversal, symlink, `.git`, secrets, max bytes, read budget, artifact-root separation, no shell/subprocess/model/tool calls.

Failure modes: denied path, over budget, secret match, file changed during read, content denied.

Rollback/no-mutation proof: no mutation; receipt states no write path touched.

Acceptance: explicit policy can read allowed metadata/content and ledger records exactly what was read.

Non-goals: arbitrary traversal, source mutation, model summarization.

### B4 - Goose readonly runtime promotion

Goal: launch Goose in a governed read-only session with receipts and close/postflight.

Files likely touched: `builder_ii/goose_runtime_harness.py`, `goose_session.py`, `goose_readonly.py`, `goose_launcher.py`, command authority, docs/tests.

State change: Goose readonly runtime `MERGED_BUT_NOT_OPERATIONAL` -> `OPERATIONALLY_VERIFIED` for no-shell/no-write read-only mode.

Commands: `builder-goose start-readonly`, `builder-goose close-readonly`.

Artifacts: Goose runtime envelope, launch receipt, session transcript refs, close receipt, no-mutation postflight, ledger event.

Authority changes: promoted Tier 3 or dedicated governed runtime tier; human approval required.

Tests: no shell/source writes, target root binding, env allowlist, process lifecycle, timeout, transcript bounds, no model/tool escalation beyond approved provider.

Failure modes: Goose missing, launch failure, runtime drift, transcript overrun, mutation detected.

Rollback/no-mutation proof: close session and no-mutation postflight.

Acceptance: Goose session can start/close under read-only constraints with valid receipts.

Non-goals: command execution, patch apply, autonomous writes.

### B5 - Optional deepagents runtime harness

Goal: execute optional deepagents/subagent planning under HITL without writes.

Files likely touched: `builder_ii/deepagents_runtime.py`, `deepagents_policy.py`, `deepagents_work_artifacts.py`, command authority, docs/tests.

State change: deepagents runtime/subagents `DESIGN_ONLY` -> `OPERATIONALLY_VERIFIED` for proposal-only subagent execution under approved runtime.

Commands: `builder-deepagents run-plan`, `builder-deepagents collect-results`.

Artifacts: runtime envelope, subagent execution receipt, result review, blocked action records, ledger event.

Authority changes: optional dependency; approval required; no autonomous writes.

Tests: dependency unavailable, denied tools, no model/tool/shell unless separately approved, proposal-only results, human review.

Failure modes: import mismatch, denied tool attempt, subagent failure, result schema invalid.

Rollback/no-mutation proof: no target mutation; delete artifacts.

Acceptance: optional harness produces reviewable results without target writes.

Non-goals: autonomous patching, hidden memory, MCP/tool bypass.

### B6 - Model/provider execution gateway

Goal: make model calls governed instead of legacy ad hoc.

Files likely touched: `builder_ii/model_execution_gateway.py`, `model_client_registry.py`, `model_routing_policy.py`, `direct_chat.py`, command authority, docs/tests.

State change: model/provider execution `MERGED_BUT_NOT_OPERATIONAL` -> `OPERATIONALLY_VERIFIED` for approved local/offline provider envelope.

Commands: `builder-model call`, `builder-model validate-receipt`.

Artifacts: model call envelope, prompt/context digest, output receipt, cost/token/rate report, replay declaration.

Authority changes: policy decides local/cloud risk; approval required for cloud/external/cost-bearing calls.

Tests: provider policy, raw secret rejection, budget limits, timeout, prompt digest, output bounds, no tool execution, replay declaration.

Failure modes: provider unavailable, cost limit exceeded, token limit exceeded, secret leak, output invalid.

Rollback/no-mutation proof: model call is no-mutation; receipt records no target writes.

Acceptance: actual model call returns a bounded receipt and ledger event.

Non-goals: model approval authority, patch application, hidden tool calls.

### B7 - MCP/tool invocation gateway

Goal: govern external tool/MCP calls with explicit risk and receipts.

Files likely touched: `builder_ii/mcp_policy.py`, `builder_ii/tool_invocation_gateway.py`, `tool_registry.py`, command authority, docs/tests.

State change: MCP/tool invocation `DESIGN_ONLY` -> `OPERATIONALLY_VERIFIED` for approved low-risk calls.

Commands: `builder-tools invoke`, `builder-mcp inventory`, `builder-mcp policy`, `builder-mcp call`.

Artifacts: tool inventory, MCP inventory, tool call envelope, approval if required, receipt, rollback/no-rollback classification, ledger event.

Authority changes: deny by default; mutation/external/cost/credential-sensitive calls require approval.

Tests: unknown tool denial, schema hash drift, credential redaction, timeout, output size, mutation classification, rollback requirement.

Failure modes: server unavailable, schema drift, denied risk, bad output schema, rollback unsupported.

Rollback/no-mutation proof: per-tool effect classification required.

Acceptance: approved read-only tool call runs and records a receipt; denied mutation tool fails closed.

Non-goals: broad MCP server trust, unbounded resource reads, hidden sampling.

### B8 - Artifact memory and handoff system

Goal: convert artifact continuity into governed memory, not hidden agent memory.

Files likely touched: `builder_ii/artifact_memory.py`, `builder_ii/memory_cli.py`, `handoff_notes.py`, `handoff_bundle_records.py`, command authority, docs/tests.

State change: artifact memory `DESIGN_ONLY` -> `PASSIVE_FOUNDATION`, then limited reconstruction -> `OPERATIONALLY_VERIFIED` if no mutation beyond approved index artifacts.

Commands: `builder-memory atom`, `builder-memory index`, `builder-memory reconstruct`, `builder-memory search`.

Artifacts: memory atom, memory index, reconstruction artifact, stale/superseded records.

Authority changes: no hidden memory; mutation approvals required for durable memory changes.

Tests: hash verification, stale policy, source ref validation, search determinism, no source truth inflation, no model summary as authority.

Failure modes: stale source, broken hash, conflicting atom, unauthorized mutation.

Rollback/no-mutation proof: delete/supersede memory artifacts; no target mutation.

Acceptance: searchable handoffs and replay-stable references reconstruct context from validated artifacts.

Non-goals: opaque vector store, autonomous memory writes, CORE vault runtime.

### B9 - Operator product polish

Goal: one coherent operator UX generated from the truth matrix and ledger.

Files likely touched: `builder_ii/operator_status.py`, `builder_ii/operator_next.py`, `builder_ii/platform_status_cli.py`, docs/tests.

State change: operator quickstart/golden path `PASSIVE_FOUNDATION` -> `OPERATIONALLY_VERIFIED` for a governed local workflow using B1-B8.

Commands: `builder doctor`, `builder status`, `builder next`, `builder demo golden-path`, possibly unified under `builder-platform`.

Artifacts: release proof generated from truth matrix, operator run report, golden path transcript.

Authority changes: status commands remain validation/read-only; demo commands must declare which promoted capabilities they exercise.

Tests: desktop/mobile not relevant; CLI UX snapshots, failure recovery, stale matrix, next-action accuracy, release proof generation.

Failure modes: incomplete capability ladder, stale ledger, missing promoted command, misleading docs.

Rollback/no-mutation proof: no target mutation unless invoking already-promoted B2; demo can run in temp repo.

Acceptance: a new operator can run one path and see target, context, approval, verification, patch/rollback, model/tool if enabled, memory, ledger, and handoff states.

Non-goals: landing page, CORE Workbench/UI, autonomous commit/push.

## 8. PR detail compliance

Each PR item in section 7 includes: goal, files likely touched, exact capability state change, command surface changes, artifact kinds added or changed, command authority changes, tests required, docs required, failure modes, rollback or no-mutation proof, acceptance criteria, and explicit non-goals. R1 sits between R0 and B1 because runtime authority depends on canonical, auditable, reversible setup state. B1 is split into B1.1, B1.2, and B1.3 because passive planning, runner authority, and ledger/chain promotion are separately reviewable authority boundaries.

## 9. Immediate next PR recommendation

Pick exactly one next PR: R0 - Anti-false-completion truth machine.

Why R0: the repo already has substantial passive foundations and a passing v0 proof harness, but it has no source-derived truth matrix. Existing docs/tests can still pass while ambiguous completion language remains. Adding R1 or B1 before R0 would create implementation work on top of a status layer that cannot reliably say what is promoted. R0 must encode the config/onboarding rows and the corrected sequence `R0 -> R1 -> B1 -> B2 -> B3 -> B4 -> B5 -> B6 -> B7 -> B8 -> B9`.

Exact implementation brief:

1. Add `builder_ii/platform_completion_audit.py`.
   - Define the exact allowed state labels.
   - Define required capability rows from this report.
   - Include the R1 config/onboarding rows: config schema, config source precedence, interactive setup wizard, non-interactive setup/apply/validate, Goose config overlay/rollback, recipe generator/wizard, skill generator/installer/validator, target profile wizard, agent profile wizard, verification profile wizard, deepagents/researcher setup wizard, setup receipt + rollback artifact.
   - For each row store evidence files, command surfaces, tests, blockers, and next PR.
   - Validate all rows have required fields and allowed labels.
   - Cross-check command names against `COMMAND_AUTHORITY_REGISTRY`.
2. Add `builder_ii/platform_status_cli.py`.
   - `matrix`: prints JSON matrix.
   - `audit-docs`: scans docs for forbidden operational claims when matching capabilities are not `OPERATIONALLY_VERIFIED`.
   - `status`: prints concise human status and exits non-zero on truth drift.
3. Add a console script, preferably `builder-platform`, and command authority entries.
4. Replace `docs/PLATFORM_COMPLETION_AUDIT.md` with generated or test-checked content.
5. Reword `docs/FOUNDATION_STATUS.md`, `docs/ROADMAP.md`, and `README.md`:
   - use "passive foundation" or state labels;
   - remove stale model routing RFC claim;
   - split legacy operator-managed live helpers from governed canonical passive lane.
   - state that R1 config/onboarding must precede B1 verification execution.
6. Add tests:
   - all required rows present;
   - all config/onboarding rows present and sequenced to R1;
   - all labels valid;
   - no doc says platform/runtime capability is complete/ready/enabled when matrix says disabled/non-operational;
   - command authority registry includes new status CLI;
   - docs table matches registry;
   - README model routing statement matches code.
7. Acceptance commands:
   - `CORE_REPO_PATH=. uv run pytest -q`
   - `CORE_REPO_PATH=. uv run python scripts/verify_v0_release.py --output-dir /tmp/builder-ii-v0-proof-r0`
   - `builder-platform status`
   - `builder-platform audit-docs`

## 10. Optional implementation status

R0 was not implemented in this audit artifact. The safe next action is a dedicated R0 PR because it must intentionally update code, command authority, docs, and tests together. This report is the source-grounded implementation brief for that PR, not a substitute for the truth machine.

Copy-paste prompt for the next implementation agent:

```text
Implement R0 for AssetOverflow/builder-II exactly from docs/BUILDER_II_COMPLETION_TRUTH_REPORT.md.

Do not implement B1 or any runtime authority.

Before implementing R0, ensure the matrix and docs include config/onboarding as a first-class capability area and sequence R1 before B1.

Add a source-derived platform completion truth machine:
- builder_ii/platform_completion_audit.py
- builder_ii/platform_status_cli.py
- console script and command authority entries
- docs truth tests
- capability matrix tests
- command authority/docs consistency tests

Required config/onboarding capability rows:
- config schema
- config source precedence
- interactive setup wizard
- non-interactive setup/apply/validate
- Goose config overlay/rollback
- recipe generator/wizard
- skill generator/installer/validator
- target profile wizard
- agent profile wizard
- verification profile wizard
- deepagents/researcher setup wizard
- setup receipt + rollback artifact

Add PR lane:
R1 - Config + Onboarding Kernel

R1 must come after R0 and before B1 because execution authority should not be promoted until platform/target/runtime configuration is canonical, auditable, reversible, and operator-walkthrough ready.

Use only the allowed state labels:
NOT_STARTED, DESIGN_ONLY, ARTIFACT_ONLY, PASSIVE_FOUNDATION, IMPLEMENTED_ON_BRANCH, PR_OPEN, MERGED_BUT_NOT_OPERATIONAL, OPERATIONALLY_VERIFIED.

Required behavior:
- fail if required capability rows are missing;
- fail if docs imply COMPLETE/ready/enabled for a capability that is disabled or not OPERATIONALLY_VERIFIED;
- fail if README/docs say model routing is only an RFC while passive implementation exists;
- preserve builder-II generic-first identity;
- do not add runtime execution, patch application, model/tool/MCP calls, Goose/deepagents runtime, autonomous writes, or commit/push automation.

Run:
CORE_REPO_PATH=. uv run pytest -q
CORE_REPO_PATH=. uv run python scripts/verify_v0_release.py --output-dir /tmp/builder-ii-v0-proof-r0
```

## R1.3A governed setup apply receipt delta

R1.3A adds a bounded setup apply mechanism and receipt artifact. The new path is digest-bound (`--approve-digest` must match `overlay_plan_digest`), snapshot-bound (rollback snapshot setup/overlay digests must match), and declared-path-only. It supports create, replace, mkdir, and no-op operations and fails closed on unsupported operations, traversal, symlink targets, undeclared paths, mismatched artifacts, or missing approval. It does not execute rollback, B1 verification, shell/subprocesses, models/providers, MCP/tools, Goose, deepagents, patches, or autonomous apply. R1.4 later reconciles legacy `builder setup` into a fail-closed redirect and removes the unmanaged setup bypass.

## R1.5 governed onboarding UX delta

R1.5 implements a governed onboarding UX layer over the R1 setup chain: `builder-setup init`, `builder-setup wizard`, `builder onboarding`, and `builder-setup validate-onboarding-intent`. It records non-interactive and guided inputs into a passive onboarding intent report artifact (`builder_ii.onboarding_intent_report`). Onboarding commands print deferred apply commands only; setup mutation remains exclusively owned by existing `builder-setup apply --approve-digest`. It does not execute B1/B2/runtime/model/tool/MCP/Goose/deepagents/patch authority or claim completion of standalone target/agent/verification profile editing wizards.

## R1.6 closure report and golden-path proof delta

R1.6 completes R1 by introducing `builder-platform r1-closure` and `builder-platform validate-r1-closure`. These commands execute the entire passive config/setup/onboarding chain and emit a canonical, auditable `r1-closure-report.json` alongside the full evidence artifact chain (`config-schema.json`, `config-resolution.json`, `setup-plan.json`, `setup-overlay.json`, `setup-rollback-snapshot.json`, and `onboarding-intent.json`). This turns the R1 chain into a single auditable golden-path proof while ensuring that setup apply/rollback execution remains explicit and B1/B2/runtime/model/tool/MCP/Goose/deepagents/patch authority remain unpromoted.
