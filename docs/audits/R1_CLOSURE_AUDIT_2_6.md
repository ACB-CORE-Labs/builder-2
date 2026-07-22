# R1 Closure Audit — Interactive Setup Wizard Flip (plan item 2.6)

This audit records the evidence for, and the full pinned-site edit set of, the R1 matrix flip:
the completion-matrix row "interactive setup wizard" moves `NOT_STARTED` →
`OPERATIONALLY_VERIFIED` (assurance `PASSIVE_ARTIFACT_VERIFIED`), and
`operationally_verified_count` moves 17 → 18. Per the master plan this flip is tier C —
evidence first, operator-applied second: this document plus the accompanying diff **is** the
edit set; the flip is applied only by the operator merging it.

It is **not** a promotion of setup mutation, runtime, model, shell, Goose, deepagents, MCP, or
patch authority. The wizard is and remains a plans-only surface: `builder init` is registered
TIER_1 / `STATE_ARTIFACT_ONLY` / `MODE_NONE` in the command-authority registry and never applies.

## What closed the gap (mechanism)

The row's original blocker read: *"No wizard plans target repo, artifact root, profiles,
model/backend, Goose writes, recipes, skills, and capability state before apply."* Plan item 2.2
(`builder init`, PR #24) closed it:

- `builder init` composes the governed onboarding pipeline (setup plan → overlay plan → rollback
  snapshot → onboarding intent report). Four wizard decisions (output directory, target profile,
  model backend, model alias) are prompted when not flag-provided; **every** answer is validated
  against the live registry for that decision — never accepted as free text — with a 3-attempt
  re-prompt then fail-closed exit. Five documented-default decisions (agent profile, verification
  profile, artifact root, runtime mode, allow-artifact-root-inside-target) resolve through standard
  config source precedence and are echoed with their override flags.
- The plan/overlay artifacts cover every element of the blocker: target repo and artifact root
  (canonical paths + declared setup scopes), profiles (target/agent/verification), model backend
  and alias, Goose writes (`goose_config_overlay_candidate`, permanently no-op per R1.7), skills
  (`skill_install_plan`, denied at apply per R1.7), and capability state (the overlay
  `capability_map`, all-disabled). Recipes are represented by their explicit absence: recipe
  installation is recorded `False` in `no_mutation_proof` and remains a manual/unpromoted lane.
- The wizard never applies. The rendered follow-up `builder-setup apply` command carries **no
  inline digest**; approval happens only in the separately invoked apply step — `--approve-digest`
  (scripted) or an interactive typed digest-prefix confirmation (the plan-1.1 grammar shared with
  `builder-hitl` approvals). Receipts record which path was used in `approval_mode`.

## Evidence

The full suite passes on the edited tree; the covering lanes are:

| Claim | Covering lane |
|---|---|
| Interactive wizard E2E (prompt → artifacts), invalid answer re-prompts, 3-attempt abort | `tests/test_init_cli.py` (CliRunner-driven prompts against the real pipeline, real artifact writes) |
| Registry-invalid flag answer exits 2 before any write | `tests/test_init_cli.py::test_init_rejects_invalid_flag_answer_before_writing` |
| Rendered apply command has no inline digest | `tests/test_init_cli.py::test_init_renders_apply_command_without_inline_digest` |
| init never writes a receipt | `tests/test_init_cli.py` + `tests/test_setup_onboarding_init_cli.py` / `test_setup_onboarding_wizard_cli.py` |
| Interactive digest-prefix apply/rollback: correct prefix applies and records `approval_mode`; wrong/empty prefix refuses with no writes and no receipt | `tests/test_setup_interactive_approval.py` |
| Wizard mode truthfully recorded (`onboarding_mode` = "wizard" only when a prompt actually happened) | `tests/test_init_cli.py` intent-report assertions |
| Command-authority containment (`builder init` TIER_1 artifact-only) | `tests/test_command_authority.py` registry + docs-table pins |
| Clean-clone onboarding + governed patch loop unaffected | `scripts/clean-clone-smoke.sh` (run green on the 2.2 tree; the interactive prompt paths are covered by the CliRunner tests above, which drive real stdin through the real CLI) |

## Audited amendment of `validate_r1_config_onboarding_mapping`

The validator previously hard-failed if **any** R1 config/onboarding row reached
`OPERATIONALLY_VERIFIED` — correct while R0 was the truth, and the reason this flip requires an
audited amendment rather than a silent edit. The amendment introduces
`R1_OPERATOR_FLIPPED_CAPABILITIES`, an explicit allowlist naming exactly the rows an operator has
flipped with a closure audit ("interactive setup wizard" is its only member). Every other R1 row
keeps the original fail-closed rule: `next_pr` must stay `R1` and the state must remain
non-operational. A future R1 flip therefore requires touching the allowlist in the same reviewed
diff as its own closure audit — the default stays refusal.

## Pin edit set authorized by this audit

- `builder_ii/core/platform_completion_audit.py` — row flip (state, evidence files, command surfaces,
  tests, caveat blockers, `next_pr` "R1 complete (2.6)"); `R1_OPERATOR_FLIPPED_CAPABILITIES`
  allowlist + `validate_r1_config_onboarding_mapping` amendment.
- `tests/test_platform_completion_truth.py` — wizard state pin (`NOT_STARTED` →
  `OPERATIONALLY_VERIFIED`), `operationally_verified_count` 17 → 18, new assurance pin
  (`PASSIVE_ARTIFACT_VERIFIED`), and `test_config_onboarding_rows_exist_and_point_to_r1`
  amended to mirror the allowlist (flipped rows asserted `OPERATIONALLY_VERIFIED`; all other
  R1 rows keep the fail-closed rule).
- `scripts/b4_flip_assistant.py` — "interactive setup wizard" added to `FLIP_CAPABILITIES`
  (assurance + mirror checks; the assistant still never writes).
- `docs/PLATFORM_COMPLETION_AUDIT.md` — matrix table row, truth-state kernel line, flip paragraph,
  "R1 closure update (2.6)" section.
- `docs/audits/R1_CLOSURE_AUDIT_2_6.md` — this document.

## Still not promoted (unchanged by this flip)

- Setup mutation stays exclusively with digest-approved `builder-setup apply`; rollback with
  digest-approved `builder-setup rollback`.
- Goose config merge, skill copying, and recipe installation remain manual operator steps (R1.7).
- The remaining R1 wizard rows — recipe generator/wizard, target/agent/verification profile
  wizards, deepagents/researcher setup wizard — remain non-operational and fail-closed in
  `validate_r1_config_onboarding_mapping`.
- No runtime, model/provider, shell, MCP/tool, Goose, deepagents, patch, or autonomous-write
  authority changes.

## Next gate

2.6 closes the R1 pins. The v0.1.0 tag (plan item 3.10, currently deferred) requires both flips
(1.7 and 2.6) plus the release-proof harness; the known-limitations document (plan item 4.2)
should be generated from the post-flip truth matrix.
