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

## Promotion/Readiness/Decision
- `builder-preflight`
- `builder-promotion`
- `builder-promotion-decision`

## Inspection/Read-Only Candidate
- `builder-readonly`

Root read-only TUI inspector subcommands:

- `builder tui`
- `builder hitl`
- `builder profile`
- `builder model`
- `builder promote`
- `builder postflight`
- `builder goose`
- `builder code-vault`

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
- no model execution is enabled
- no patch application is enabled
- no autonomous writes are enabled
- no Goose runtime activation is enabled
- no deepagents runtime is enabled
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
| `builder_ii/goose_setup.py` | Passive Goose config and skill-source metadata | Passive-only setup/config-overlay helper | `passive_only` | Tier 1 passive metadata | No direct writes, no recipe validation, no skill copying |
| `builder start` | Operator-managed runtime helper | No longer auto-runs legacy setup writes | `runtime_decoupled` | Tier 2 operator-managed runtime helper | Runtime state only; setup must go through governed artifacts |
| `builder_ii/goose_launcher.py` | Runtime launcher | Runtime-only helper with session-context write | `runtime_only` | Tier 2 operator-managed runtime helper | No Goose setup delegation, no config writes, no skill installs |


## Reconciliation additions

These command surfaces are registered in `pyproject.toml` and remain governed by builder-II's default no-autonomous-execution boundary unless their specific documentation states a narrower read-only or artifact-only behavior.

- `builder-orchestration`

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

- `builder-code-vault structural-field TARGET --output PATH [--repo-map PATH | --repo-path PATH]` builds, validates, and writes a governed `builder_ii.code_vault.structural_field` artifact carrying five of the six registered fact kinds (`motif` is not emitted — G2 PR-7c decides its normalized form or formally defers it): `signature` (an arity/shape descriptor — parameter counts, never names or text), `nesting` (enclosing scope kinds and depth, never scope names), `ownership` (method membership — carries names, carries no path), `decorator` (an ordered, called-aware list; a callee that is not statically a dotted name normalizes to the declared `<dynamic>` sentinel), and `import_fact` (one fact per imported binding, alias-blind and deduped). Subjects are every definition CPython would see — functions, async functions, classes, methods at any nesting depth, closures (bound to CPython's own `__qualname__`, `outer.<locals>.inner`), and definitions inside `if`/`try`/`with`/`for`/`while`/`match` guards — bounded at 64 subjects per file; `lambda` is refused (no name, so no coordinate); `import_fact`s bind to the frame's **file** node. Facts bind to `subject_layout_id` (top-level defs and top-level classes reproduce the F0 frame's `layout_id` scheme exactly; methods and nested classes extend it — the field is a superset of the frame, never a subset). Facts are structural correspondence *candidates* (hypothesis, R+D), never a claim of verified correspondence. Non-Python files, syntax-error files, and unreadable/non-UTF-8 files in scope become sorted `unsupported[]` residue entries, never a fabricated fact.
- The command reads Python source through a **separate extraction lane** (`builder_ii/code_vault/structural_extractor.py`): it does not import or call `symbol_extractor.py`'s frame-feeding functions (`extract_python_symbols` / `extract_symbols_from_file`), so it cannot change hierarchical-frame bytes (invariant #8 stays closed).
- `extractor_manifest_ref` binds to a **new** `build_structural_extractor_manifest()` declaration (`coverage="structure"`, distinct `extractor_id` from the v0 symbol extractor) — no schema bump; `build_extractor_manifest` (v0) stays byte-identical.
- Facts are **structural correspondence candidates** (hypothesis, R+D vocabulary per the proof program) — never a claim of verified correspondence, and never utility (U) language. This is RECORDED_ONLY: it flips no completion-matrix row and grants no execution, shell, model, Goose, deepagents, or target-repo-write authority. Tier 1 `artifact_only`; `artifact_is_authority` remains false.
- `builder-code-vault validate-structural-field` (landed G1 PR-2) is unchanged and validates this command's output.
