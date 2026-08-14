# builder-II Ecosystem — Code-Grounded Architectural Audit

**Date:** 2026-07-24 · **Rev audited:** `aeff091` on `claude/setup-cloud-env-script-e3qx44`
**Method:** three parallel deep-read passes (governance/determinism spine; Goose/deepagents adapter seams; verification/HITL lanes + UX), every claim anchored to `file:line` read this session. No claim below is inferred from file names or docs alone.

---

## 0. Scope honesty (anti-confabulation preamble)

The audit directive named four repos (`builder-II`, `goose`, `orchestrator`, `deepagents`) and three CORE pillars. What was actually auditable:

| Directive target | Status |
|---|---|
| `builder-II` | **Fully audited** (this repo, at HEAD). |
| `goose`, `deepagents` (external repos) | **Not in session access scope.** Audited *as consumed*: builder-II's adapter seams, projections, launch paths, and readback surfaces. |
| `orchestrator` | No such standalone repo/module is present. The closest in-repo analogue is the CLI root (`builder_ii/cli/main.py`), `builder-orchestration`, and the lane runners; audited as such. |
| Pillar 1 — Zero-allocation Rust/Zig critical loops | **Not present in open core.** The only Rust is the optional PyO3 validation accelerator (`builder_ii_validation_rs/`), a measurement-gated side track, not a critical-loop execution path. Assessed for what it is (§4.7). |
| Proprietary upgrade internals | **Out of scope.** CodeVault is maintained in a separate commercial repository; open core retains only the fail-closed optional-plugin seam. |
| Pillar 3 — Deterministic governance & traceability | **Fully assessed.** This is builder-II's actual identity, and it is where both the real strength and the real gaps live. |

**Executive verdict.** builder-II's governance grammar — *planned ≠ executed ≠ verified ≠ promoted*, *artifact ≠ authority* — is held with unusual rigor **inside** each artifact family: validators hard-pin `grants_runtime_authority=False`, promotion is a reviewed source edit rather than an artifact-driven flip, and the bounded verification runner is genuinely bounded. The structural weaknesses are all **seam failures**: the governed artifact chain narrates execution but does not gate it; the riskiest lanes (cloud egress, autonomous Goose) carry the least governance; and several approval checkpoints accept an artifact's *existence* as authority without validating it. The friction users feel is not caused by the rigor — it is caused by the CLIs ignoring a chain-resolver the TUI already has.

---

## 1. The Delta of Excellence — where the architecture fails its own invariants

Ranked by structural leverage (invariant damage × fix cheapness).

### D1. The governed Goose artifact chain never gates the live launch
Two disconnected lanes exist. The artifact lane (`session_config.py:54` → `goose_projection.py:33` → `goose_wrapper_plan.py:13` → `goose_session.py:81` → `goose_readonly.py:68`) builds the full PLANNED_ONLY ceremony — the wrapper plan even computes the exact `argv` and marks `"executes_now": False`. The live lane (`goose_launcher.py:305-353`, `goose_runtime_harness.py:69,121`) calls `derive_goose_environment` and `subprocess.Popen(argv, cwd, env)` directly. `builder start` (`main.py:463-484`) goes routing → spawn without creating or consulting **any** artifact from the governed chain. The ceremony is parallel narration, not a precondition.

Compounding it: `launch_goose_session` has **no authority gate at the function boundary** — the only `enforce_command_authority("builder start", ...)` lives at the CLI edge (`main.py:458`). `hitl_patch_apply.py:358-362` documents exactly this failure mode ("if only the CLI enforced authority, any direct caller … would bypass the gate") and fixed it for the patch lane; the Goose lane — the highest-authority effect in the system (`GOOSE_MODE=auto`, `GOOSE_MAX_TURNS=1000`, API keys in env, `--with-builtin developer,skills,summon`, `goose_launcher.py:221-236,350-351`) — never received the same fix.

**Invariant broken:** planned ≠ executed (the "planned" artifact has no bearing on what executes); artifact ≠ authority cuts both ways — here the artifact has *no* authority even as a check.

### D2. Governance is inversely correlated with risk: cloud lanes bypass the artifact lane entirely
`session_config.py:18` allows only `{"rapid-mlx", "mlx-lm", "ollama"}` as provider backends, and `_model_id_for_alias` (`session_config.py:22-33`) knows only local MLX aliases — so a valid session-configuration artifact is structurally local-only. Meanwhile `derive_goose_environment` (`goose_launcher.py:154-186,235-258`) happily mints env for groq/xai/google/anthropic/openai **and injects live API keys**. Every cloud launch therefore reaches Goose *only* through the ungoverned path: no projection, no wrapper plan, no manifest, no readonly audit, no operator-review handoff. The safest flows (local Ollama/MLX) carry the full ceremony; the credential-bearing, cost-bearing, network-egressing flows carry none. The projection artifact and the launched process can also name different models for the same session (`goose_projection.py:45` vs `goose_launcher.py:188`).

### D3. Approval checkpoints that accept existence as authority
Three separate gates treat an unvalidated reference as approval:

- **The command-authority gate itself:** `policy_evaluator.py:142-144` — `MODE_HITL_ARTIFACT_REQUIRED` is satisfied by any truthy `approval_ref` string or `hitl_bound=True`. The gate never opens the file, checks its `kind`, its `valid` flag, or its binding to this command/subject.
- **The model execution gateway (cost-bearing cloud egress):** `model_execution_gateway.py:422` — `human_approval_supplied = approval_path is not None and approval_path.is_file()`. An **empty file** authorizes a `cloud_external`/`cost_bearing` call; the bytes are digested into the receipt (`:722-730`) but never validated or bound to `model_id`/`prompt_digest`.
- **The tool invocation gateway:** `tool_invocation_gateway.py:94-96` — risk classes require only a truthy `approval_ref` in the envelope.

The safe counter-example proving the fix is cheap: `hitl_patch_apply.py:431-455` independently validates approval schema, binding, and expiry after passing the weak gate. That logic belongs *inside* the gate so every caller inherits it. **Invariant broken:** artifact ≠ authority, model output ≠ approval — at the exact checkpoints built to hold them.

### D4. Verification approvals are replayable against changed code, and receipts aren't bound to what they gate
- The approval binds to the **plan digest** only (`verification_execution_approval.py:145-170,488-501`); the plan contains `target_repo` as a path string with no HEAD/worktree pin (`verification_execution_plan.py:649-650`). The runner records `head_sha` in the receipt (`verification_execution_runner.py:939`) but **never compares** it to anything approved. `expires_at` is optional and unenforced (`verification_execution_approval.py:436-438`) — contrast the patch lane's mandatory 24h TTL enforced at apply (`hitl_patch_approval.py:72`, `hitl_patch_apply.py:454`). Result: approve once, rewrite the repo, mint fresh "verified" receipts forever.
- `apply-patch`'s required `--verification-receipt` is validated **without** `target_repo` on the general path (`hitl_patch_apply.py:237-247`; the comment at `:183-187` admits only the demo fallback is repo-bound) and is never bound to the proposal/patch digest or pre-apply HEAD. A receipt from verifying repo A can authorize a patch to repo B.

**Invariant broken:** verified ≠ promoted decays into "verified once, somewhere ≈ verified now, here."

### D5. Traceability dies at launch: no readback from Goose into any ledger
After `Popen`, builder-II observes Goose two weak ways: `builder start` just `proc.wait()`s (`main.py:484-485`) — no receipt, no ledger event; the harness diffs file SHA-256s (`goose_runtime_harness.py:86,209-217`) but its "transcript path" is a **guess that is never opened** — `session_id = f"goose_{int(time.time())}"` (`:64`) has no relation to Goose's real session filename, and the close receipt records the phantom path with no content digest (`goose_receipts.py:61`, `goose_runtime_harness.py:227`). The diff also excludes `.git`/`.builder` by construction (`:45`), so Goose commits are invisible, and a write-then-revert defeats it. Goose receipts are plain files, never appended to a hash chain — unlike model calls, which get `append_model_call_event` into a chained ledger (`model_execution_gateway.py:787-800`). The traceability pattern exists in-repo; the Goose lane just doesn't use it. **Invariant broken:** subagent output ≠ truth has no evidence stream to adjudicate against.

### D6. Determinism drift points (the "exact vs probabilistic" audit)
- **Host path baked into a promotion-feeding digest:** verification receipts embed `sys.executable` argv verbatim (`verification_execution_runner.py:127-142,550-562`), flowing into `receipt_digest` → `chain_digest` (`verification_execution_ledger.py:804-812`) → promotion gate binding (`verification_promotion_gate.py:238-249`). Byte-identical runs on two hosts produce different promotion evidence. The repo already knows this hazard class — `gate_battery_receipt.find_absolute_paths` (`gate_battery_receipt.py:122-141`) exists precisely to reject it — but the verification receipt has no such guard.
- **Unlocked read-modify-write ledger append:** `verification_execution_ledger.py:765-787,973-975` computes `max_index+1` then writes with no `flock`; concurrent appends fork the chain (detected post-hoc at `:537`, not prevented). `tui_audit_ledger.py:233-255,303-337` already paid for and fixed this exact bug with an exclusive lock across read-tail-then-append; the verification ledger reintroduces it.
- **Five hand-rolled JSON canonicalizers** (`config_schema.py:255`, `hitl_chain_binding.py:76-78`, `model_execution_gateway.py:42-44`, `tui_audit_ledger.py:130-138`, `promotion_decision_records.py:22-24`) that agree today only because `ensure_ascii` happens to align (tui_audit sets `False`, the rest default `True`).
- **Four alias→model-id maps** that can silently drift: `config.py:240-295`, `goose_launcher.py:46-118` (byte-for-byte copy of the first), `session_config.py:22-33` (local subset), `model_client_registry.py` entries — plus `model_policy.py:19-70`'s parallel alias→backend map. Nothing pins them to each other.
- **Unverified embedded digest:** `promotion_decision_records.py:126-159` checks the readiness sha256 is *non-empty*, never re-derives it from the referenced file — unlike `hitl_chain_binding.verify_hitl_chain_binding_files` (`hitl_chain_binding.py:310-353`), which does.

### D7. Smaller but real integrity leaks
- **`EXECUTED_ONLY` receipts from a path that executes nothing:** `deepagents_runtime.py:148-228` writes assignment/result/receipt artifacts with `receipt_state="EXECUTED_ONLY"` (`:113`) and a string-interpolated summary while running no backend — the code's own comment (`:216-217`) admits it. An auditor reading the receipt label is misled even though every mutation flag is honestly `False`.
- **Unrecorded side effects on read paths:** `goose env` (read-only report) writes `.builder/session-context.md` with no kind/digest/ledger entry and shells out to `git` (`goose_launcher.py:194`, `goose_runtime_context.py:14-99`). Forge's registry hook imports a symbol that does not exist and silently returns `"skipped"` (`deepagents_forge_emit.py:141-149`) — emitted agents are never actually routable.
- **Routing is not an execution authority:** `model_router.choose_model_alias` (`model_router.py:116`) feeds only Goose session planning; `builder ask` hand-builds its "recommendation" from the already-selected `active_model_id` (`main.py:532-543`), so the gateway's `allowed_models` check (`model_execution_gateway.py:400`) authorizes what was already chosen. Two routing brains, no conversation.
- **Dead timeout:** `tool_invocation_gateway.py:128` computes a timeout and discards it (benign today: stub tools only).

---

## 2. Agent synergy & governance — handoff map

**Where the teach → verify → promote lifecycle actually lives.** Promotion states (`PLANNED_ONLY`/`RECORDED_ONLY`/`OPERATIONALLY_VERIFIED`/…) are never consumed at runtime to flip capability. The only execution gate is the static, hand-authored `CommandAuthorityRecord` table (`authority_registry.py:184-4763`) read by `enforce_command_authority` (`policy_evaluator.py:95-178`). Promotion artifacts are validator-pinned to `grants_runtime_authority=False, flips_matrix=False` (`promotion_readiness_records.py:202-204`, `verification_promotion_gate.py:316-318`). A "promotion" is a reviewed source edit gated by `validate_registry_invariants()` + tests. **This is the right design and it is held** — no code path reads a promotion state from an artifact to enable an effect. Note, though: `validate_registry_invariants` is a validator returning an error list (`authority_registry.py:4821-4941`); nothing calls it at process start — CI tests are its only teeth.

**Where state traceability is lost, per handoff:**

| Handoff | Traceability |
|---|---|
| builder-II → model provider (`builder ask`) | **Strong.** Digest-bound envelope, secret-scan fail-closed, redact-before-digest, hash-chained `model_call_executed` event (`model_execution_gateway.py:383-800`). |
| builder-II → deepagents (bounded protocol lane) | **Strong.** Approval guard, output-dir allowlist, event budget, chained events, backend results forced to `PROPOSAL_ONLY` with all mutation flags `False` (`deepagents_execution.py:302-329,2725-2831`). |
| builder-II → deepagents (legacy `run`) | **Misleading label** (D7): `EXECUTED_ONLY` receipts, zero execution. |
| builder-II → Goose (launch) | **Lost** (D1/D5): no artifact precondition, no boundary authority gate, no chained receipt, phantom transcript path. |
| Goose → builder-II (postflight) | **Weak:** content-digest diff only, `.git`/`.builder` excluded, revert-defeatable. |
| Verify lane → patch lane | **Weak coupling** (D4): receipt not bound to repo/patch/HEAD. |

**Are agent actions gated by the lifecycle, or are there un-auditable bypasses?** The bypasses are enumerable and now enumerated: direct `launch_goose_session` callers (D1), all cloud-backend Goose launches (D2), any caller handing a truthy string to the D3 gates, and verification-approval replay (D4). Everything else routes through validators that genuinely fail closed.

---

## 3. UX vs. rigor reconciliation

The friction is not the governance grammar — it is that the CLIs make humans do the chain bookkeeping the system already does.

- **One governed patch = 6 commands** (`builder-verify plan` → `approve-plan` → `run-approved` → `builder-hitl propose-patch` → `approve-patch` → `apply-patch`), with `plan.json → approval.json → receipt.json → proposal.json → patchapproval.json` hand-carried between them. Exactly two steps carry real human semantics: the D7 execution-risk prompt (`verification_execution_plan_cli.py:196-207`) and the digest-prefix attention check (`hitl_patch_cli.py:98-105`). Everything else is path shuttling — and `propose-patch` even *prints* the next command's arguments (`hitl_patch_cli.py:115-118`), proving the chain is mechanically resolvable.
- **The resolver already exists — in the TUI.** `tui/projections/chain.py:84-105,191-194` scans `.builder/{artifacts,session,hitl,receipts}`, indexes by `kind`, prefers newest mtime. The CLIs just don't consult it.
- **`builder X` and `builder-X` mean different things.** 48 console scripts; the umbrella `builder hitl`/`goose`/`model` mount **read-only inspection** apps (`tui_inspection_cli.py:44-106`, `cli/main.py:32-38`) while `builder-hitl`/`builder-goose` are the mutating lanes. Same token, opposite semantics — a genuine operator trap. The verify and patch lanes are not reachable under `builder` at all; there is no workflow entry point that sequences the lanes.
- **TUI coverage:** STRATUM composes CLI lines but executes nothing (`tui/app.py:567-581,911-971`) — correct posture — yet has no affordance at all for the verification lane or the 6-step patch walk.

**Reconciliation spec (rigor-preserving, friction-removing):**
1. `builder_ii/cli/_chain_resolve.py` wrapping `find_artifact_path_for_kind`; add `--from-last` defaults for `--plan/--approval/--proposal/--verification-receipt` on every chained command. All digest bindings and validators still run on the resolved path — this removes re-typing only.
2. A `builder chain` wizard (or TUI walk) sequencing plan → approve → run → propose → approve → apply through the same functions, surfacing only the two real approval moments.
3. Rename umbrella inspection groups to `builder inspect <lane>` so `builder X` never contradicts `builder-X`.

---

## 4. Concrete refactoring specs (per finding)

| # | Refactor | Files | Pattern already in-repo to copy |
|---|---|---|---|
| R1 | `launch_goose_session` requires a validated wrapper-plan artifact; assert artifact argv/cwd/env-keys == spawned values, fail closed on drift. Move `enforce_command_authority` into the function body. | `goose_launcher.py:305-353` | Gate-at-boundary: `hitl_patch_apply.py:358-369` |
| R2 | Either extend `_ALLOWED_PROVIDER_BACKENDS` + `_model_id_for_alias` to cloud lanes (with a `cloud_egress`/approval field) **or** refuse cloud backends in `derive_goose_environment` without a validated cloud-lane artifact. Today it is neither represented nor gated. | `session_config.py:18-33`, `goose_launcher.py:154-186` | Cloud-approval gating: `model_execution_gateway.py:419-429` (after R3 hardens it) |
| R3 | Authority gate takes the approval artifact (or resolver) + `subject_digest`; loads, validates kind/valid/binding. `approval_ref` demoted to metadata. Same for the model gateway (`validate_model_call_approval` with kind, expiry, `approved_model_id`, `approved_prompt_digest`) and tool gateway. | `policy_evaluator.py:142-144`, `model_execution_gateway.py:422-429`, `tool_invocation_gateway.py:94-96` | The exact validation logic: `hitl_patch_apply.py:431-455` |
| R4 | Pin repo state into the verification plan (`target_head_sha`, worktree digest — reuse `_git_commit_identity` at `verification_execution_runner.py:302`); fail-closed HEAD/drift check in `run_approved_verification` after preflight (`:831`); mandatory enforced `expires_at` reusing `approval_is_expired` (`hitl_patch_approval.py:259`). Bind apply-patch's receipt to `target_repo` + pre-apply HEAD + proposal. | `verification_execution_plan.py`, `verification_execution_approval.py`, `verification_execution_runner.py`, `hitl_patch_apply.py:237-247` | Drift preflight: `hitl_patch_apply.py:800-817` |
| R5 | Post-close: resolve Goose's real session log, digest it, append a `goose_session_closed` event (launch-receipt digest + postflight digest + transcript sha256) to the chained event ledger. Route `builder start` through the harness. | `goose_runtime_harness.py`, `goose_receipts.py`, `main.py:484` | `append_model_call_event`: `model_execution_gateway.py:787-800` |
| R6 | Determinism: store argv[0] as a stable token, resolve `sys.executable` at spawn; add a `find_absolute_paths`-style guard to the receipt validator. `flock` the verification-ledger append. One `canonical_json` module. One `routing/model_catalog.py` with `model_id_for(alias, backend)` + a test pinning registry ⇔ catalog for every alias. Re-derive the readiness digest in the decision-record validator. | `verification_execution_runner.py`, `verification_execution_ledger.py`, the 5 canonicalizer sites, the 4 alias maps, `promotion_decision_records.py:126-159` | `gate_battery_receipt.py:122-141`; `tui_audit_ledger.py:233-255`; `hitl_chain_binding.py:310-353` |
| R7 | Rust parity: targeted adversarial case per validation branch (not 50 random mocks); a coverage assertion making the "2 of N kinds" gap explicit; longer-term, generate both validators from one declarative schema. | `builder_ii_validation_rs/src/validation.rs:20-34,80`, `rust_validator.py:59-64`, `tests/test_rust_parity.py:16-24` | — |
| R8 | Honesty labels & leaks: rename legacy deepagents `receipt_state` to `PROJECTED_ONLY`/`NO_EXECUTION` (or delete the path); gate `write_moim_context` behind actual launch or make it a kinded artifact; fail loudly when `register_from_forge_spec` is absent. Extend docs-truth scan to root `*.md`, Typer help text, and TUI string literals; match on `command_surfaces` not name-substring. | `deepagents_runtime.py:113-228`, `goose_runtime_context.py`, `deepagents_forge_emit.py:141-149`, `platform_completion_audit.py:1436-1486` | Scanner core already reusable: `scan_docs_for_false_completion` |
| R9 | UX: `_chain_resolve.py` + `--from-last`; `builder chain` wizard; `builder inspect <lane>` rename. | `builder_ii/cli/*` | `tui/projections/chain.py:84-105,191-194` |

---

## 5. Calibration — what this codebase does exceptionally well

1. **artifact ≠ authority is structurally held, not aspirationally.** Every promotion-adjacent record hard-pins `grants_runtime_authority=False` in creation *and* validation; promotion is a reviewed source edit; no code path flips capability from artifact state. The audit found seam leaks (D3), not a broken model.
2. **The bounded verification runner is a real envelope:** fixed in-code argv, `shell=False` everywhere, env allowlist, `PYTHONSAFEPATH=1` + pinned import root so the repo-under-test can't shadow the auditor, shell-metacharacter argv scan, plan-declared-but-clamped timeouts, postflight git-capture failure treated as mutation (`verification_execution_runner.py:55-296,428-443,877-916`).
3. **`tui_audit_ledger` is the house-standard hash chain** — two-digest split with documented rationale, `flock` across the critical section, validator that recomputes rather than trusts, and an honest "what this does NOT close" section (`tui_audit_ledger.py:9-72,233-337,443-517`). Findings D6 are mostly "the other ledgers should copy this file."
4. **The rollback lane fails closed and instructs:** HEAD/worktree drift refusal with an exact recovery command, reverse-patch digest checks, and refusal to claim restoration it can't prove (`hitl_patch_apply.py:800-1007`).
5. **Self-correcting culture in the code itself:** the assurance classifier replaced a silent green-default with a no-default raise and documents the incident (`platform_completion_audit.py:152-275`); the pexpect/TTY-scraping ban carries its measurement; `deepagents_execution` forces every backend payload to `PROPOSAL_ONLY`.

The pattern across every finding: **the strong version of each control already exists somewhere in this repo.** The work is not inventing governance — it is making the strongest instance of each pattern the *only* instance.

## 6. Closure Status (Stage 4 Synthesis)

The comprehensive structural audit and subsequent remediation phases have concluded. All findings D1-D7 have been successfully addressed:

- **R1/D1 (Goose Boundary Gates):** Addressed by strictly gating the `launch_goose_session` function with an authority check that requires a valid wrapper plan.
- **R2/D2 (Cloud Egress Governance):** Addressed by validating that cloud models strictly follow the HITL artifact lane.
- **R3/D3 (Existence vs Validation):** Refactored execution gateways (Command Authority, Model Execution, Tool Invocation) to validate the artifact signature, target, and `grants_runtime_authority` flags before proceeding.
- **R4/D4 (Target Drift):** Enforced head SHA validation against the verification execution plan to prevent replaying old approvals against new code.
- **R5/D5 (Execution Traceability):** Resolved phantom transcript path handling and appended closure signatures for bounded sub-agents.
- **R6/D6 (Determinism):** Ensured exact validation matching and canonical JSON generation. Re-derived digest validations across decision records.
- **R9/D9 (UX vs Rigor):** Integrated seamless artifact path resolution via `_chain_resolve.py` using `find_artifact_path_for_kind`, eliminating the friction of manual path passing.

### Validation Matrix
All 2,590 test suite cases pass. The registry correctly holds 360 bounded commands. Zero syntax errors or namespace collisions remain active. Core pillars of architectural integrity are mathematically tight.
