# Capability promotion registry

builder-II capabilities must move through explicit, documented promotion states. A capability is never enabled merely because code exists, a dependency imports, an artifact validates, or an agent profile can be rendered.

builder-II is:
`builder-II — Generic governed platform for local agent-assisted development.`

CORE is only a target profile / lineage context, not the global platform identity. Conflating builder-II with CORE Workbench/UI is strictly forbidden.

This canonical registry records current implemented capabilities, the command authority registry, the ConventionKernel platform spine, governed prepare-package workflows, repo map and context pack foundations, artifact index ledgers, artifact chain verification, and the gates required before any future runtime promotion.

## 1. Promotion state definitions

Every capability across the platform operates under one of the following explicit promotion states:

| State | Meaning |
| --- | --- |
| `unavailable` | No supported command, artifact, or implementation exists. |
| `spec_only` | builder-II can render a specification, prompt, plan, or profile, but cannot run it. |
| `smoke_only` | builder-II can inspect import/readiness status without constructing or running the dependency. |
| `artifact_only` | builder-II can emit an explicit output artifact requested by the user. |
| `validation_only` | builder-II can validate artifact schema and governance invariants, but cannot execute artifact contents. |
| `read_only_runtime_candidate` | A design candidate for read-only runtime behavior exists, but it is not an enabled runtime. |
| `operator_managed` | A setup, helper, or local runtime interface invoked explicitly by the operator; delegates to subcommands or local server endpoints without granting autonomous authority. |
| `hitl_runtime_candidate` | A future HITL-gated runtime design candidate exists, but it is not enabled for autonomous execution. |
| `forbidden_unpromoted` | The capability or command attempts active automation that is explicitly disabled, unpromoted, or forbidden by default. |
| `enabled` | The capability is fully enabled by documented command surface, tests, failure modes, human approval boundary, output artifact, rollback path, and verification path. |

## 2. Promotion gate requirements

A capability can move from disabled or candidate state to `enabled` only when it provides verified evidence across all eight promotion gates:

1. **Docs**: Complete architectural and operator documentation describing boundaries and intent.
2. **Tests**: Automated unit and governance enforcement test suites proving compliance and boundary defense.
3. **Command surface**: A stable CLI console script or subcommand entrypoint.
4. **Failure mode**: Explicit error handling that fails closed and leaves target systems unchanged on violation.
5. **Human approval boundary**: Clear definition of required human sign-off before action occurs.
6. **Output artifact**: Predictable, structured JSON or markdown records emitted upon completion.
7. **Rollback path**: Documented instructions and artifacts for reverting changes if errors arise.
8. **Verification path**: Concrete test or check commands to confirm expected outcomes.

Missing any single item keeps the capability below `enabled`.

## 3. Explicit relationship to command authority tiers

The capability promotion registry operates in strict alignment with the source-backed command authority tier registry (`docs/COMMAND_AUTHORITY.md`, `builder_ii/command_authority.py`).

- **Command authority tier** tells what a command surface may represent (Tier 0 read-only, Tier 1 artifact-only, Tier 2 operator-managed helper, Tier 3 HITL candidate, Tier 4 forbidden).
- **Capability promotion state** tells whether a capability is promoted for use across the platform.
- **Metadata is not permission**: A command being present in `pyproject.toml` or registered in Python scripts does not imply the capability is enabled.
- **Spine boundary**: Tier 2+ commands are never invoked by the ConventionKernel platform spine.
- **Passive candidates**: Tier 3 HITL artifacts do not execute by themselves.
- **Forbidden default**: Tier 4 automation remains forbidden and unpromoted.

## 4. Explicit relationship to ConventionKernel

The ConventionKernel (`docs/CONVENTION_LAYER_KERNEL.md`, `builder_ii/convention_kernel.py`) is the canonical platform spine that unifies session workflow planning and verification specifications.

- ConventionKernel composes planned artifacts into unified platform spine bundles (`builder_ii.convention_kernel_platform_bundle`).
- It **does not grant authority** or execute any runtime commands.
- It **does not run verification** suites or convert planned checks into completed evidence.
- It **does not start Goose** or activate Goose runtime sessions.
- It **does not start deepagents** or delegate to autonomous subagents.
- It **does not run models** or perform LLM inference.
- It **does not mutate target source** files or working trees.
- It **validates command authority and governance boundaries**, ensuring every referenced command belongs to Tier 0 or Tier 1 (or is explicitly marked operator-managed).

## 5. Explicit relationship to artifact validation / chain verification

Validated artifacts are passive evidence and design objects, not runtime authority.

- **Artifact index**: Tracks generated JSON files across local workspace ledgers (`docs/ARTIFACT_INDEX.md`). It records path, digest, byte count, kind, and schema validation flags without granting runtime permission.
- **Artifact chain verification**: Traces hash and cryptographic linkage across evidence sequences (`builder-chain`). A valid chain verification report proves that proposal, approval, request, receipt, postflight, and verification records link together correctly.
- **Non-authoritative evidence**: A valid artifact or chain verification report does not authorize model execution, agent construction, command execution, shell execution, source mutation, memory mutation, commits, pushes, or PR creation.

## 6. Current implemented capability table

The following table categorizes all current first-class capabilities across builder-II, detailing their exact promotion state, command tier, boundaries, output artifacts, verification paths, human boundaries, and failure/rollback notes.

| Capability | Current State | Command Tier | Authority Boundary | Output Artifact | Verification Path | Human Approval Boundary | Failure Mode / Rollback Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Target profiles | `spec_only` / `validation_only` | Tier 0 (`builder-targets`) | Metadata resolution only; no execution. | Profile definition / JSON spec | `pytest tests/test_target_profiles.py` | Operator selects profile before session initiation. | Exits non-zero on unknown profile name; no changes made. |
| Agent profiles | `spec_only` / `validation_only` | Tier 2 (`builder-agent`) | Static profile rendering; no agent run. | Agent profile JSON | `pytest tests/test_agent_profiles.py` | Operator selects agent role and inspects boundaries. | Exits non-zero on invalid profile schema; no changes made. |
| Verification profiles | `validation_only` | Tier 1 (`builder-verification`) | Defines planned checks; does not run tests. | `verification-profile.json` | `pytest tests/test_verification_profiles.py`, `builder-verification validate` | Operator reviews verification commands. | Exits non-zero on schema error; delete artifact. |
| Command authority registry | `validation_only` | Tier 1 (`builder-tools`) | Declarative classification; does not grant runtime permission. | Registry audit report / JSON | `pytest tests/test_command_authority.py` | Passive boundary enforcement. | Unregistered or Tier 2+ commands fail closed in spine generation. |
| Repo map | `artifact_only` | Tier 1 (`builder-session repo-map`) | Read-only scanning; writes explicit artifact path only. | `repo-map.json` | `pytest tests/test_repo_map.py` | Operator initiates scan and reviews map structure. | Delete emitted artifact; working tree untouched. |
| Context pack | `artifact_only` | Tier 1 (`builder-session context-pack`) | Read-only file gathering; writes explicit artifact path only. | `context-pack.json` | `pytest tests/test_context_pack.py` | Operator specifies bounded file inclusions. | Delete emitted artifact; working tree untouched. |
| Governed prepare-package | `artifact_only` | Tier 1 (`builder-session prepare-package`) | Generates package manifests and session plans; no runtime or repo mutation. | `prepare-package.json` and package files | `pytest tests/test_governed_prepare_package.py` | Operator inspects package directory contents. | Delete package directory; target repo untouched. |
| Prepare-package validation | `validation_only` | Tier 1 (`builder-session validate-prepare-package`) | Structural and hash checks on package files; no execution. | None (stdout audit confirmation) | `pytest tests/test_governed_prepare_package.py` | Passive validation check before package transfer. | Exits non-zero on missing or corrupt package files. |
| Prepare-package summary | `validation_only` | Tier 1 (`builder-session summarize-prepare-package`) | Passive summary report generation; does not convert planned checks to evidence. | `prepare-package-summary.json` (optional) | `pytest tests/test_prepare_package_summary.py` | Operator reviews summary metrics. | Exits non-zero if read fails; delete summary artifact. |
| ConventionKernel classic bundle | `artifact_only` / `validation_only` | Tier 1 (`builder-bundle create` / `validate`) | Packages target bundle metadata; no execution. | `target-bundle.json` | `pytest tests/test_bundle.py`, `builder-bundle validate` | Operator confirms bundle contents. | Delete emitted artifact; no source mutation. |
| ConventionKernel platform spine bundle | `artifact_only` / `validation_only` | Tier 1 (kernel invocation) | Planned-only spine composition; checks authority registry; forbids runtime run. | `platform-bundle.json` | `pytest tests/test_convention_kernel_platform_spine.py` | Operator reviews unified platform spine. | Fails closed if unregistered or Tier 2+ commands referenced; delete artifact. |
| Goose projection | `artifact_only` | Tier 1 (`builder-session goose-readonly-plan`) | Deterministic env/recipe mapping; does not start Goose. | `goose-projection.json` | `pytest tests/test_goose_projection.py` | Operator verifies read-only tool constraints. | Delete projection artifact; no Goose session started. |
| Goose wrapper plan | `artifact_only` | Tier 1 | Describes CLI invocation wrapper plan; does not execute wrapper. | `goose-wrapper-plan.json` | `pytest tests/test_goose_wrapper_plan.py` | Operator reviews invocation parameters. | Delete plan artifact; no subprocess launched. |
| Goose read-only session plan | `artifact_only` | Tier 1 (`builder-goose manifest`) | Specifies session config with read-only tool boundaries. | `goose-readonly-session.json` | `pytest tests/test_goose_session.py`, `builder-goose validate` | Operator confirms tool restrictions. | Delete session manifest artifact. |
| Verification profile report | `artifact_only` | Tier 1 (`builder-verification plan`) | Emits planned test commands; does not execute verification. | `verification-profile-report.json` | `pytest tests/test_verification_cli.py` | Operator must manually execute planned verification commands. | Delete report artifact; no verification claims created. |
| Handoff note | `artifact_only` | Tier 1 (`builder-notes handoff`, `builder-handoff create`) | Passive summary of session state and open risks; no automation triggers. | `handoff-note.json` / markdown | `pytest tests/test_handoff_notes.py`, `builder-notes validate` | Operator signs off on handoff summary. | Delete note artifact; no state changes. |
| Deepagents bridge readiness report | `artifact_only` / `validation_only` | Tier 2 / Tier 1 (`builder-deepagents check-readiness`, `builder-bridge deepagents-smoke`) | Checks optional bridge availability; no deepagents construction or active run. | `deepagents-readiness.json` | `pytest tests/test_deepagents_cli.py`, `builder-deepagents validate-readiness` | Operator inspects readiness status passively. | Exits non-zero if bridge unavailable; no runtime started. |
| Artifact index | `artifact_only` / `validation_only` | Tier 1 (`builder-index record` / `validate`) | Records metadata (paths, hashes, kinds) for artifact ledgers; metadata-only. | `artifact-index.json` | `pytest tests/test_artifact_index_records.py` | Passive inventory check across workspace outputs. | Exits non-zero if path outside worktree; delete index artifact. |
| Artifact chain verification | `validation_only` | Tier 1 (`builder-chain`) | Validates cryptographic/hash linkage across evidence records; does not grant authority. | Chain validation report / stdout | `pytest tests/test_artifact_chain_verification.py` | Operator audits evidence trail integrity. | Fails closed if broken links or invalid schemas detected. |
| Read-only inspection report / candidate surfaces | `read_only_runtime_candidate` | Tier 0 (`builder-readonly inspect`, `builder-goose inspect-readonly`) | Bounded relative file reads only; records metadata/digests; no source writes or shell. | `readonly-inspection-report.json` | `pytest tests/test_readonly_inspection.py`, `builder-goose validate-inspection` | Operator explicitly specifies relative paths to inspect. | Exits non-zero if unsafe or write paths targeted; delete artifact. |
| HITL execution request artifact | `hitl_runtime_candidate` | Tier 3 (`builder-hitl request`) | Records proposed command and intent; cannot execute by itself. | `hitl-request.json` | `pytest tests/test_hitl_execution_records.py`, `builder-hitl validate` | Requires explicit operator approval signature. | Delete request artifact; no execution occurs. |
| HITL execution receipt artifact | `hitl_runtime_candidate` | Tier 3 (`builder-hitl receipt`, `builder-receipt generate`) | Records outcome metadata of completed execution; passive proof object. | `hitl-receipt.json` | `pytest tests/test_hitl_execution_records.py` | Operator verifies receipt matches actual outcome. | Delete receipt artifact. |
| HITL patch application spec | `hitl_runtime_candidate` | Tier 3 (`builder-hitl plan-patch`) | Specifies proposed diffs/patches; does not apply patch to target repo. | `hitl-patch-spec.json` | `pytest tests/test_hitl_patch_spec.py` | Operator must review proposed diff before manual application. | Delete patch spec; repository unchanged. |
| Rollback plan | `artifact_only` / `hitl_runtime_candidate` | Tier 1 / Tier 3 | Outlines rollback strategy and related artifacts; does not execute revert. | `rollback-plan.json` | `pytest tests/test_rollback_artifacts.py` | Operator reviews recovery strategy. | Delete plan artifact. |
| Rollback receipt | `artifact_only` / `hitl_runtime_candidate` | Tier 1 / Tier 3 | Records proof of completed manual rollback; passive evidence. | `rollback-receipt.json` | `pytest tests/test_rollback_artifacts.py` | Operator confirms rollback execution. | Delete receipt artifact. |
| Execution postflight record | `artifact_only` / `hitl_runtime_candidate` | Tier 1 / Tier 3 | Records expected vs. observed state after manual run; passive record. | `postflight.json` | `pytest tests/test_execution_postflight_records.py` | Operator validates observed outcome. | Delete postflight record. |
| Execution verification record | `artifact_only` / `hitl_runtime_candidate` | Tier 1 / Tier 3 | Links request, receipt, and postflight records; confirms verification completion. | `verification.json` | `pytest tests/test_execution_postflight_records.py` | Operator signs off on verification completion. | Delete verification record. |
| HITL evidence bundle | `artifact_only` / `hitl_runtime_candidate` | Tier 1 / Tier 3 | Manifest linking proposal, approval, request, receipt, and verification records. | `hitl-evidence-bundle.json` | `pytest tests/test_hitl_evidence_bundle.py` | Chain verifier validates entire evidence trail. | Fails closed if any referenced artifact is corrupt or missing. |
| Legacy builder-context / Repomix path | `operator_managed` | Tier 2 (`builder-context pack`, `builder-context artifact`) | Invokes external repomix or git scanners; no direct write authority beyond artifact output. | Context bundle / files | `pytest tests/test_context_cli.py` | Explicit operator invocation from active terminal. | Exits non-zero if repomix fails; legacy path, prefer `prepare-package`. |
| Root builder start / ask / verify helpers | `operator_managed` | Tier 2 (`builder start`, `builder ask`, `builder verify`, `builder-runtime`) | Interactive terminal helpers for local server control, model query, or local pytest runs. | Local locks, chat logs, test stdout | `pytest tests/test_cli.py`, `pytest tests/test_runtime_control.py` | Explicit operator invocation only; no autonomous loop. | Exits non-zero on error; leaves target repo source unchanged. |

## 7. Current unpromoted / forbidden capability table

The following capabilities are explicitly unpromoted, disabled, or forbidden across the platform. Attempting to invoke automation for these surfaces fails closed.

| Capability | Current State | Command Tier | Authority Boundary | Failure Mode / Enforcement |
| --- | --- | --- | --- | --- |
| Goose runtime start | `forbidden_unpromoted` | Tier 4 (`builder-goose start-readonly`) | Starting active Goose runtime sessions automatically from builder-II is forbidden. | Exits non-zero with explicit error; enforced by `pytest tests/test_goose_cli.py`. |
| Deepagents active delegation | `forbidden_unpromoted` | Tier 4 (`builder-deepagents delegate`) | Autonomous subagent execution or delegation is strictly forbidden. | Exits non-zero with explicit error; enforced by `pytest tests/test_deepagents_cli.py`. |
| Shell execution | `forbidden_unpromoted` | N/A | Shell execution as an automated agent capability is disabled. | Enforced across projection policy and governance validation blocks. |
| Model execution through bridge loops | `forbidden_unpromoted` | N/A | Autonomous model execution loops through the bridge are disabled. | Enforced by bridge artifact validation and governance invariants. |
| Source patch application | `hitl_runtime_candidate` / not enabled | Tier 3 / Tier 4 | Automated mutation of target repository source files is disabled. | Automated write attempts fail closed; patch specs remain review objects only. |
| Commit / push automation | `forbidden_unpromoted` | Tier 4 | Autonomous git commit, push, or PR creation is forbidden. | Automated git mutation attempts fail closed. |
| Arbitrary repository writes | `forbidden_unpromoted` | N/A | Writing to repository source files outside explicit artifact output paths is blocked. | Enforced by no-write governance tests. |
| Memory mutation | `forbidden_unpromoted` | N/A | Persistent agent memory mutation or graph state modification is disabled. | Enforced by governance invariants. |

## 8. Clear “what is currently safe to use” operator guidance

For developers and operators using builder-II today, the following workflows are fully validated and safe to use:

1. **Profile discovery & inspection**: Run `builder-targets list`, `builder-tools list`, and `builder-index list` to inspect platform metadata and available profiles.
2. **Session preparation**: Use `builder-session prepare-package --target <target> --task "<task>" --output-dir <dir>` to generate clean, governed local session packages containing repo maps, context packs, workflow plans, Goose read-only session manifests, and verification profile reports.
3. **Package validation & summarization**: Run `builder-session validate-prepare-package` and `builder-session summarize-prepare-package` to verify package integrity and audit contents before starting work.
4. **Artifact verification & lineage tracking**: Use `builder-goose validate`, `builder-verification validate`, `builder-notes validate`, `builder-records validate`, and `builder-chain` to audit schema compliance and cryptographic/hash evidence chains.
5. **Operator-managed helpers**: Run `builder start` to control local background runtime processes, `builder ask` to query local model providers directly from the terminal, and `builder verify` to run local test suites manually via subprocess.

## 9. Clear “what is not enabled yet” boundary

Operators and future agents must recognize the exact boundaries where builder-II stops:

- **No autonomous execution**: Planned session workflows, Goose session manifests, and HITL request artifacts do not execute themselves.
- **No unprompted source writes**: builder-II will never automatically edit source files in your target repository. Patch proposals must be applied manually by the operator.
- **No Goose runtime activation**: While builder-II generates Goose session manifests and projection plans, starting the active Goose runtime loop remains the operator's responsibility.
- **No deepagents delegation**: Subagent delegation and autonomous multi-agent orchestration remain forbidden and unpromoted.
- **No completed evidence conversion**: Generating a summary report or a planned verification profile report does not convert planned checks into completed execution evidence. Actual execution receipts require manual running and recording.
- **No CORE identity conflation**: builder-II is a generic platform. Do not assume CORE Workbench or CORE UI runtime behaviors apply to builder-II.
