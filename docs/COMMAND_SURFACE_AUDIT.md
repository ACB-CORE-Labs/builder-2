# Command Surface Audit

This document lists current CLI command surfaces from `pyproject.toml`, grouped by category.

## Platform Setup / Runtime Policy
- `builder`
- `builder-runtime`
- `builder-lanes`
- `builder-tools`
- `builder-mcp`
- `builder-git-state`
- `builder-platform`
- `builder-memory`
- `builder-config`
- `builder-setup`
- `builder onboarding`

Governed platform subcommands:

- `builder-platform matrix`
- `builder-platform status`
- `builder-platform audit-docs`
- `builder-platform r1-closure`
- `builder-platform validate-r1-closure`

Governed memory subcommands:

- `builder-memory atom`
- `builder-memory index`
- `builder-memory search`
- `builder-memory reconstruct`
- `builder-memory validate-atom`
- `builder-memory validate-index`
- `builder-memory validate-search-result`
- `builder-memory validate-reconstruction`

Governed setup subcommands:

- `builder-setup plan`
- `builder-setup validate-plan`
- `builder-setup overlay-plan`
- `builder-setup validate-overlay-plan`
- `builder-setup rollback-snapshot`
- `builder-setup validate-rollback-snapshot`
- `builder-setup init`
- `builder-setup wizard`
- `builder-setup validate-onboarding-intent`

## Target/Profile/Context
- `builder-context`
- `builder-profile-pack`
- `builder-model-policy`
- `builder-wrp` — passive Workload–Router–Pool control plane (classify/plan/allocate/gate/evaluate/replay); Tier 1 recommendation/plan/validation only; no model, shell, MCP, Goose, deepagents, or live multi-agent execution authority
- `builder-targets`
- `builder-session`
- `builder-workflow`
- `builder-ledger`
- `builder-code-vault` — governed read-only CodeVault hierarchical frame, extractor manifest declaration, lint, recall, context projection, determinism demo, StructuralField schema validation, and validation; Tier 1 artifact-only; no shell, model, Goose, deepagents, or target-repo writes

## Artifact Chain / Governance Records
- `builder-records`
- `builder-receipt`
- `builder-chain`
- `builder-index`
- `builder-state-index`
- `builder-snapshot`
- `builder-hitl`
- `builder-govern`

## Promotion/Readiness/Decision
- `builder-preflight`
- `builder-promotion`
- `builder-promotion-decision`

## Inspection/Read-Only Candidate
- `builder-readonly`
- `builder-stratum` — experimental STRATUM operator console (observe + compose; console-script alias of `builder stratum`)
- `builder-semantic` — V.1 semantic/structural read-only lane (doctor/map/preview/validate); no model, shell, Goose start, or target writes
- `builder-tui-inspection` — read-only TUI status/inspection surface


Root read-only TUI inspector subcommands:

- `builder tui`
- `builder hitl`
- `builder profile`
- `builder model`
- `builder promote`
- `builder postflight`
- `builder goose`
- `builder code-vault`
- `builder stratum`

These root inspector groups are Tier 0 observer surfaces. They read existing
governed artifacts from `$BUILDER_DIR`, render terminal diagnostics, and do not
write artifacts, start runtimes, invoke models/tools/MCP, activate Goose or
deepagents, apply patches, mutate git, or change source/target repositories.

## Research/Performance/Verification
- `builder-agent`
- `builder-bundle`
- `builder-quality`
- `builder-research`
- `builder-performance`
- `builder-verification`
- `builder-verify`

## Notes/Handoff/Intake
- `builder-handoff`
- `builder-intake`
- `builder-notes`

## Deepagents/Goose Optional Bridge Surfaces
- `builder-bridge`
- `builder-goose`
- `builder-deepagents`

## Runtime Policy & Architectural Invariants

- no shell execution is enabled
- no ambient model execution is enabled; native Deep Agents model calls require the approved candidate and `ModelExecutionGateway`
- no patch application is enabled
- no autonomous writes are enabled
- no Goose runtime activation is enabled
- native deepagents runtime is enabled only inside an approved bounded envelope; readiness and policy artifacts remain passive
- setup apply is enabled only for digest-bound explicit approval through `builder-setup apply`
- setup rollback execution is enabled only for digest-bound explicit approval through `builder-setup rollback`; generic/B2 rollback remains disabled
- legacy `builder setup` performs no writes and only redirects to the governed R1 path
- no Goose config writes, `.goosehints` writes, skill copying, or recipe installation writes are enabled by the legacy `builder setup` redirect path
- builder-II is not CORE Workbench/UI
- CORE is only a target profile

## R1.4 Legacy Setup Reconciliation Audit

| Surface | Current behavior | Reconciled behavior | Mode | Authority tier | Write/runtime boundary |
|---|---|---|---|---|---|
| `builder setup` | Legacy compatibility entrypoint | Fails closed and prints governed `builder-setup` sequence | `disabled_redirect` | Tier 1 compatibility redirect | No setup writes, no Goose start, no subprocess/shell, no model/tool/runtime promotion |
| `builder_ii/adapters/goose/goose_setup.py` | Passive Goose config and skill-source metadata | Passive-only setup/config-overlay helper | `passive_only` | Tier 1 passive metadata | No direct writes, no recipe validation, no skill copying |
| `builder start` | Operator-managed runtime helper | No longer auto-runs legacy setup writes | `runtime_decoupled` | Tier 2 operator-managed runtime helper | Runtime state only; setup must go through governed artifacts |
| `builder_ii/adapters/goose/goose_launcher.py` | Runtime launcher | Runtime-only helper with session-context write | `runtime_only` | Tier 2 operator-managed runtime helper | No Goose setup delegation, no config writes, no skill installs |


## Reconciliation additions

These command surfaces are registered in `pyproject.toml` and remain governed by builder-II's default no-autonomous-execution boundary unless their specific documentation states a narrower read-only or artifact-only behavior.

- `builder-orchestration`
- `builder-wrp`

## R1.4 command surface delta

- `builder-setup apply` adds digest-bound governed setup apply from a validated overlay/snapshot pair and requires explicit `--approve-digest` plus explicit receipt `--output`.
- `builder-setup validate-receipt` validates `builder_ii.setup_apply_receipt` artifacts.
- `builder-setup rollback` adds digest-bound governed setup rollback from an applied setup receipt plus matching rollback snapshot.
- R1.5 adds `builder-setup init`, `builder-setup wizard`, `builder onboarding`, and `builder-setup validate-onboarding-intent` as passive onboarding wrappers.
- R1.5 does not add B1 verification execution, runtime/model/tool/MCP/Goose/deepagents/shell/subprocess/patch authority, or autonomous apply.

## R1.6 command surface delta

- `builder-platform r1-closure` runs the full passive R1 config/setup/onboarding pipeline, emitting canonical chain evidence and `r1-closure-report.json`.
- `builder-platform validate-r1-closure` validates the closure report and referenced evidence files on disk.
- R1.6 completes R1 golden-path proof without executing setup mutation or promoting B1/B2/runtime/model/tool/MCP/Goose/deepagents/patch authority.

## B8 command surface delta

- `builder-memory atom` wraps one explicit validated source artifact as a governed memory atom.
- `builder-memory index` builds a deterministic index from explicit memory atoms only.
- `builder-memory search` emits explainable lexical search results without hidden retrieval or vector-store behavior.
- `builder-memory reconstruct` emits replay-stable review context from an explicit index.
- `builder-memory validate-*` validates emitted memory artifacts only.
- B8 does not add hidden memory, autonomous memory writes, model authority, shell execution, runtime authority, MCP/tool execution, Goose runtime, deepagents runtime, or target-repo mutation.

## B1.1 command surface delta

- `builder-verify plan` writes a passive `builder_ii.verification_execution_plan` artifact only to explicit `--output` and prints the same JSON.
- `builder-verify validate-plan` validates that artifact without executing verification.
- `builder-verify plan` accepts any compatible `(target_profile, verification_profile)` pair — a verification profile that lists the target in its compatible targets (e.g. `generic`/`generic_basic`, `core`/`core_smoke`, `builder`/`builder_full`); incompatible pairs fail closed. A non-builder target's plan offers only the `pytest_full` profile that runs the target repository's own suite. The builder-II self-verification profiles (`platform_status`/`docs_audit`/`builder_full`) run builder-II's own matrix/docs checks and are refused for any non-builder verification profile at the runner boundary.
- B1.1 does not run tests, execute shell/subprocess, call models/tools, invoke MCP, start Goose/deepagents, apply patches, mutate git, or promote B2 patch authority.

## B1.2/B1.3A command surface delta

- `builder-verify approve-plan` writes a passive `builder_ii.verification_execution_approval` artifact only to explicit `--output` and prints the same JSON.
- `builder-verify validate-approval` validates that approval artifact against a referenced passive plan without executing verification.\n- `builder-verify validate-receipt` validates a passive B1.3A receipt contract against its referenced plan and approval without executing verification.\n- `builder-verify run-approved` runs the first bounded B1.3B verification profile (`platform_status`) only after validating plan and approval artifacts. It uses fixed in-code argv with `shell=False`, writes only an explicit receipt artifact, and does not grant patch/model/MCP/Goose/deepagents/B2 authority.
- B1.2 binds human approval to an exact verification plan digest only; it does not become runtime authority or authorize direct execution.
- B1.2 does not run tests, execute shell/subprocess, call models/tools, invoke MCP, start Goose/deepagents, apply patches, mutate git, or promote B2 patch authority.
- B1.3 is still required before any approved verification can execute.


## B1.4A command surface delta

- `builder-ledger index-receipt` passively indexes an existing validated B1.3 verification execution plan/approval/receipt chain into a deterministic `builder_ii.verification_execution_ledger_record` under `.builder/ledger/`.
- `builder ledger index-receipt` is the root-command equivalent surface.
- B1.4A does not replay execution, run subprocesses, execute shell, call models/tools, invoke MCP, start Goose/deepagents, apply patches, mutate git, or promote B2 authority.

## B1.4B command surface delta

- `builder-ledger query-receipts` reads existing `builder_ii.verification_execution_ledger_record` artifacts under `.builder/ledger/`, validates records before inclusion, reports rejected records as JSON diagnostics, filters by receipt digest, chain digest, receipt status, and runner mode, and emits stable summary counts.
- `builder ledger query-receipts` is the root-command equivalent surface.
- B1.4B is passive/read-only only: it does not replay execution, run verification, run subprocesses, execute shell, call models/tools, invoke MCP, start Goose/deepagents, apply patches, mutate source/target repo files, mutate git, mutate memory, or promote B2 authority.

## B1.4C command surface delta

- `builder-ledger validate-receipts` emits a deterministic `builder_ii.verification_execution_ledger_integrity_report` over existing `builder_ii.verification_execution_ledger_record` artifacts under `.builder/ledger/`.
- `builder ledger validate-receipts` is the root-command equivalent surface.
- The report validates native record digests, rejected records, duplicates, required plan/approval/receipt subject refs, chain-digest consistency, and optional index-chain continuity when index-chain fields are present.
- B1.4C is passive/read-only only: it does not write report artifacts, replay execution, run verification, run subprocesses, execute shell, call models/tools, invoke MCP, start Goose/deepagents, apply patches, mutate source/target repo files, mutate git, mutate memory, or promote B2 authority.

## B1.4D command surface delta

- `builder-ledger reconstruct-receipts` emits a deterministic `builder_ii.verification_execution_ledger_reconstruction_report` over existing `builder_ii.verification_execution_ledger_record` artifacts under `.builder/ledger/`.
- `builder ledger reconstruct-receipts` is the root-command equivalent surface.
- The report reconstructs passive receipt-chain projections, summary counts, invalid/rejected record diagnostics, chain continuity status, and evidence refs.
- B1.4D is passive/read-only only: it does not write report artifacts, replay execution, re-run verification, run subprocesses, execute shell, call models/tools, invoke MCP, start Goose/deepagents, apply patches, mutate source/target repo files, mutate git, mutate memory, or promote B2 authority.

## CodeVault G1 PR-1 command surface delta

- `builder-code-vault extractor-manifest --language python --output PATH` builds, validates, and writes a governed `builder_ii.code_vault.extractor_manifest` artifact declaring the registered Python extractor's identity (`extractor_id`, `extractor_version`, `parser_id`, `parser_version`), coverage (`structure_partial`), supported/unsupported constructs, and limits. Requesting an unregistered language (v1 registers `python` only) exits non-zero and writes nothing.
- `builder-code-vault validate-extractor-manifest PATH` validates an extractor manifest artifact file, including digest re-derivation and governance conformance.
- This is RECORDED_ONLY declaration of what the existing Python extractor (`symbol_extractor.py`) already does; it changes no extractor behavior, adds no structural-intelligence claim, and flips no completion-matrix row. Tier 1 `artifact_only`; `artifact_is_authority` remains false.

## CodeVault G1 PR-2 command surface delta

- `builder-code-vault validate-structural-field` validates a `builder_ii.code_vault.structural_field` (F2) artifact file: kind/schema_version, `extractor_manifest_ref` shape, `scope`, `facts[]` fact vocabulary and invariance-class vocabulary, `unsupported[]`, governance, and `field_digest`.
- No build/emission subcommand ships with it: no extractor fills this artifact yet, so only the schema and its validator exist (RECORDED_ONLY). Fact emission is G2 work against this settled schema.
- This delta does not add fact emission, extractor changes, structural-correspondence claims, shell/model/Goose/deepagents/runtime authority, or target-repo writes.

## CodeVault G2 PR-7a command surface delta

- `builder-code-vault structural-field TARGET --output PATH [--repo-map PATH | --repo-path PATH] [--scope full|paths|package|changed] [--scope-path PATH ...] [--base-commit SHA256]` builds, validates, and writes a governed `builder_ii.code_vault.structural_field` artifact carrying five of the six registered fact kinds (`motif` is not emitted — G2 PR-7c decides its normalized form or formally defers it): `signature` (an arity/shape descriptor — parameter counts, never names or text), `nesting` (enclosing scope kinds and depth, never scope names), `ownership` (method membership — carries names, carries no path), `decorator` (an ordered, called-aware list; a callee that is not statically a dotted name normalizes to the declared `<dynamic>` sentinel), and `import_fact` (one fact per imported binding, alias-blind and deduped). Subjects are every definition CPython would see — functions, async functions, classes, methods at any nesting depth, closures (bound to CPython's own `__qualname__`, `outer.<locals>.inner`), and definitions inside `if`/`try`/`with`/`for`/`while`/`match` guards — bounded at 64 subjects per file; `lambda` is refused (no name, so no coordinate); `import_fact`s bind to the frame's **file** node. Facts bind to `subject_layout_id` (top-level defs and top-level classes reproduce the F0 frame's `layout_id` scheme exactly; methods and nested classes extend it — the field is a superset of the frame, never a subset). Facts are structural correspondence *candidates* (hypothesis, R+D), never a claim of verified correspondence. Non-Python files, syntax-error files, and unreadable/non-UTF-8 files in scope become sorted `unsupported[]` residue entries, never a fabricated fact. **Scope (G1b):** `--scope` selects one of the four registered modes from the single shared vocabulary (`builder_ii/code_vault/scope.py`, also used by the hierarchical frame). `changed` is a **declaration, not a capability** — CodeVault runs no `git` and derives no diff; the operator supplies the changed paths (e.g. from `git diff --name-only <base>`) and the `--base-commit` they are relative to, and the artifact records the claim so a reader can check it. `--base-commit` is **required** for `--scope changed` and refused on every other mode: a `changed` scope that cannot say what it changed *from* is a guess, not a scope. A `changed` field is emitted at schema v2 (every other scope stays v1 and byte-identical) and is **partial** — a strict subset of a full build — so it must never be diffed against a `full` field and read as deletions.
- The command reads Python source through a **separate extraction lane** (`builder_ii/code_vault/structural_extractor.py`): it does not import or call `symbol_extractor.py`'s frame-feeding functions (`extract_python_symbols` / `extract_symbols_from_file`), so it cannot change hierarchical-frame bytes (invariant #8 stays closed).
- `extractor_manifest_ref` binds to a **new** `build_structural_extractor_manifest()` declaration (`coverage="structure"`, distinct `extractor_id` from the v0 symbol extractor) — no schema bump; `build_extractor_manifest` (v0) stays byte-identical.
- Facts are **structural correspondence candidates** (hypothesis, R+D vocabulary per the proof program) — never a claim of verified correspondence, and never utility (U) language. This is RECORDED_ONLY: it flips no completion-matrix row and grants no execution, shell, model, Goose, deepagents, or target-repo-write authority. Tier 1 `artifact_only`; `artifact_is_authority` remains false.
- `builder-code-vault validate-structural-field` (landed G1 PR-2) is unchanged and validates this command's output.

## Ratification grants command surface delta

- `builder-govern` adds the standing-ratification-grant lane: `list-points`, `grant-auto`, `list-grants`, `revoke`, `validate-grant`, `ledger`, `validate-ledger`, `trace`, and `consult`. It mints, validates, revokes, and audits `builder_ii.ratification_grant`, `builder_ii.ratification_grant_revocation`, and `builder_ii.ratification_ledger_event` artifacts under the ratification store root, and executes nothing.
- `builder onboard` adds an interactive walkthrough of the onboarding golden path that offers each delegable confirmation in context and writes only the grants the operator explicitly accepts. It recommends the next command and never runs one; `--no-prompt` describes every point and writes nothing.
- A standing grant may satisfy only a `plan_digest_confirmation` ratification point whose owning command carries no capability outside `allows_source_writes`/`allows_artifact_writes`/`allows_state_writes` and does not require HITL artifacts. Points declared `human_approval_mint` (`builder-hitl approve-patch`, `refuse-patch`) or `promotion_decision` (`builder-hitl promotion-decision`) are registered and permanently refused: a grant relocates confirmation friction and never originates approval. Eligibility is recomputed from the command-authority registry at consult time and is never read from a grant artifact.
- `builder-setup apply` and `builder-setup rollback` gain a third approval mode, `standing_ratification_grant`, recorded in their receipts and never conflated with `interactive_digest_prefix_confirmation`. Both append a ratification ledger line only where a ratification store already exists.
- This delta adds no execution, shell, model, Goose, deepagents, MCP, or patch authority, and flips no completion-matrix row.

## Ratification policy and chain-repair command surface delta

- `builder-govern` gains the tightening half of the ratification lane: `policy-show`, `policy-set`, `policy-validate`, `approve`, and `validate-approval`. Policy declares a per-point level on an ordered ladder (`delegable` < `always_prompt` < `require_approval_artifact`) plus an `--no-grants` project-wide kill switch, and mints `builder_ii.ratification_policy` and `builder_ii.ratification_approval` artifacts.
- A policy may only **tighten**. The effective level is `max(registry baseline, declared)`, so a declared level weaker than the baseline is ignored rather than honoured; `policy-set` additionally refuses to write one, so the operator is told rather than silently overridden. No policy can make a `human_approval_mint` or `promotion_decision` point delegable.
- `builder-govern approve` mints a `builder_ii.ratification_approval` bound to one point and one exact subject digest, only after the operator types the subject digest prefix. There is deliberately no `--yes`: the artifact is evidence a human decided. It is replayable within its TTL against that same subject digest, and is re-verified against subject and clock at use time.
- `builder-setup apply` / `rollback` gain `--approval-ref` and a third approval mode, `ratification_approval_artifact`. Above policy level `delegable` they refuse `--approve-digest` outright, because a script can compute a digest and honouring the flag would bypass the level the operator set. Their receipts now also record `approval_point_id`, `approval_grant_digest`, and `approval_ref_digest`, so the authority chain resolves from the receipt alone.
- `builder-govern trace` accepts either a ratification point id or a path to a consuming artifact, and in the latter form walks that artifact's authority chain: point, level in force, satisfying grant or approval, whether the grant is still active, and the point's recorded history.
- `builder chain` is **repaired, and narrowed**. It previously enforced `builder chain` while no record declared that name, so every invocation ended in an unhandled traceback; it also swallowed every failure after step 1 and then printed "completed successfully", and passed argv (`builder-hitl propose-patch --from-last`) that command does not accept. It is now a Tier 0 composing walkthrough with a real authority record: it names each stage's command, that command's live tier and promotion state, and the ratification point where one is registered. The `subprocess` path that reached `builder-hitl apply-patch` is gone, so this delta **removes** execution authority rather than adding any.
- This delta adds no execution, shell, model, Goose, deepagents, MCP, or patch authority, and flips no completion-matrix row.
