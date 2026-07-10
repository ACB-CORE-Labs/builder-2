# Ladder 9 closure audit — the assurance state of the one lane that executes

`HITL-approved verification execution` moves from assurance `PASSIVE_ARTIFACT_VERIFIED` to
`BOUNDED_EXECUTION_VERIFIED`. Its completion state does not move, and
`operationally_verified_count` stays **19**. This is an assurance-only flip, the first of its
kind; a reviewer pattern-matching "promotion ⇒ count + 1" will mis-read it.

The operator's merge is what applies the flip. Everything committed here is `RECORDED_ONLY`.

## Why the row was wrong

`assurance_state_for_row` ended in `return PASSIVE_ARTIFACT_VERIFIED`. The field
`docs/PLATFORM_COMPLETION_AUDIT.md` calls *authoritative for risk interpretation* therefore
assigned its lowest-risk label to any `OPERATIONALLY_VERIFIED` row nobody had classified — eleven
of the nineteen, including the only lane that spawns a subprocess. Not because anyone judged them
passive; because nobody judged them at all, and the default guessed in the green direction.

`builder-platform audit-docs` cannot catch this. That audit detects docs which *overstate*
capability, never records which *understate* risk. Truth is symmetric; the audit is not. The
default is gone: an unclassified `OPERATIONALLY_VERIFIED` row now raises
`UnclassifiedCapabilityError`, and `validate_completion_matrix` reports it.

## What `BOUNDED_EXECUTION_VERIFIED` claims here, and what it does not

> Causes work to run — a subprocess, an external tool, or a sealed backend — inside a fixed,
> pre-approved envelope: fixed argv with `shell=False` or a digest-bound seal, an approval, and a
> digest-bound receipt. **It attests the envelope of the invocation. It never attests the
> behaviour of the code that ran inside it.**

Scoped **exactly** to the `platform_status` and `docs_audit` profiles. `pytest_full` and
`builder_full` execute the target repository's own suite, sit behind the mandatory D7
execution-risk acknowledgement, and stay outside this claim. The row's blocker sentence is
unchanged:

> "The approved verification lane is operationally verified only for fixed platform_status and
> docs_audit profiles; arbitrary argv, broad shell, live read authority, patching,
> model/MCP/Goose/deepagents runtime, and B2 write authority remain disabled."

## The claim was false when this work started

The brief required one sub-claim to be verified rather than repeated: *do `platform-status` and
`docs-audit` execute only builder-II's own code?* At the module level, yes — they call
`validate_completion_matrix`, `validate_command_surfaces`, `scan_docs_for_false_completion`, and
`import pytest` is deferred into `run_pytest_full` so the safe path never loads it.

At the **process** level, no. Three defects, each confirmed by running it:

1. **The subject supplied its own auditor.** The runner spawns children with `cwd=target_repo`, and
   `_minimal_env` set `PYTHONPATH=target_repo`. Python puts the cwd at `sys.path[0]`. A target
   repository shipping `builder_ii/verification_runner_entrypoints.py` had its module dispatched
   instead of builder-II's; a target shipping `sitecustomize.py` had it executed by `site` at
   interpreter startup, before `main()` was reached. Fixed: `PYTHONSAFEPATH=1`, and
   `BUILDER_II_IMPORT_ROOT` always first. The flag that admits the target to the import path is
   derived from `TARGET_CODE_EXECUTING_PROFILES` — the same constant that makes the approval demand
   the D7 acknowledgement.

2. **Containment relaxed what ran inside it.** `DockerBackend.wrap_command` ended with
   `container_env["PYTHONPATH"] = "/workspace"`, unconditionally overwriting the decision above:
   every *isolated* run of the two safe profiles imported the target's code. The backend now
   translates the caller's roots into container paths instead of replacing them, mounting each
   non-target root read-only and dropping none.

3. **`builder_self` is a label check, not an identity check.** It compares the plan's
   `verification_profile` string to `"builder_full"`; `target_repo` is validated only as "a
   non-empty string". Nothing binds the profile label to the target's identity. After fix (1) this
   is no longer a safety hole — a foreign target now gets builder-II's auditor over its own data,
   and executes no code — but the audit it produces is meaningless for a repository that is not
   builder-II. Recorded, not fixed.

Without (1) and (2), `bounded` would have described an envelope the target could step out of. They
land before the flip, in their own commits, for that reason.

## Evidence (`RECORDED_ONLY`)

Four fresh chains on the promoting host, each through the real CLI — `builder-verify plan →
validate-plan → approve-plan → validate-approval → run-approved → validate-receipt`,
`builder-ledger index-receipt`, `builder-verify evaluate-promotion`. All four reached
`receipt_status: EXECUTED`, `valid: true`, `workspace_mutation_detected: false`,
`shell_enabled: false`.

| chain | profile | isolation_backend | isolation_status | isolation_policy_digest |
|---|---|---|---|---|
| plain | `platform_status` | `none` | `not_applied` | `null` |
| plain | `docs_audit` | `none` | `not_applied` | `null` |
| isolated | `platform_status` | `docker` | `applied` | `0b9aa40035cbf9872a7a1bb1a08f2f18c0fce8bdd72b32e974e840e486e6ba2a` |
| explicit-none | `platform_status` | `none` | `not_applied` | `null` |

Absence is recorded as absence: `null`, never `""`, never a plausible default.

Committed B2.0 machine evidence, pinned by `tests/test_ladder9_promotion_evidence.py`, which
re-derives each self-digest rather than comparing a pasted hash:

- `planning/evidence/ladder9-b2-platform-status-pass.json`
- `planning/evidence/ladder9-b2-docs-audit-pass.json`
- `planning/evidence/ladder9-b2-platform-status-isolated-pass.json`

Each is `PASS` with `failed_gates: []` over all **eleven** machine gates, enumerated so that a gate
which quietly disappears cannot leave an empty failure list looking green: `plan_valid`,
`approval_valid`, `approval_bound_to_plan`, `receipt_valid`,
`receipt_bound_to_plan_and_approval`, `receipt_executed`, `workspace_unmutated`,
`commit_identity_recorded`, `approval_unexpired`, `ledger_chain_consistent`,
`profile_matches_capability`. Each carries `evidence_state: RECORDED_ONLY`, `flips_matrix: false`,
and grants neither action nor runtime authority.

## Isolation is containment, not attestation

The flip **does not depend on isolation**, and nothing here should be read as saying it does.
`docs/plan/VERIFICATION_ISOLATION_RFC.md`:

> "There is nothing an isolated run can evidence that an unisolated run could not forge…
> Local isolation is containment, not attestation."

The isolated chain is evidence that the containment path works and records itself honestly. It is
not evidence that the unisolated chain is trustworthy, and the unisolated chains carry the flip on
their own. If a sentence in this document read "isolation makes this safe to promote," it would be
wrong.

Two consequences of that principle, recorded rather than papered over:

- **A receipt with `isolation_status: "applied"` records the approved fixed profile argv, not the
  container-wrapped argv that executed.** `_process_result_from_completed` uses `profile.argv` by
  design, so the receipt stays self-describing and bound to the approved profile rather than to a
  host-specific `docker run` line. The consequence is that `isolation_status` is the runner's own
  assertion about itself, corroborated by nothing inside the receipt. This audit's `applied` row
  was checked against the daemon's own container `create`/`start`/`die` events, out of band. A
  future schema revision may add an `executed_argv_digest`; today it does not exist, and the RFC's
  sentence above is the reason that is tolerable.
- **The B2.0 promotion-gate evaluator is isolation-blind.** None of its eleven gates inspect the
  receipt's isolation triple. That follows from the same principle — the gates evaluate the
  chain's integrity, not its containment — but it means an isolated chain and an unisolated one
  produce structurally identical evidence, and only the receipt distinguishes them.

## Open, recorded, not fixed here

- `builder-verify plan` exposes **no isolation flag**. Ladder 9 shipped `isolation_policy` in the
  plan schema, the runner, and the receipt, but no governed CLI surface can request it: the two
  isolation plans above were built through `finalize_verification_execution_plan` directly. The
  isolation lane is unreachable from the command surface an operator actually has.
- `builder_self` remains a label check (see defect 3 above).

## Files

| file | why |
|---|---|
| `builder_ii/verification_execution_runner.py` | `PYTHONSAFEPATH`, builder-II import root first, roots keyed to `TARGET_CODE_EXECUTING_PROFILES` |
| `builder_ii/verification_isolation_backend.py` | container import-path translation instead of overwrite |
| `builder_ii/assurance.py` | the eight assurance states now have definitions |
| `builder_ii/platform_completion_audit.py` | fall-through deleted; explicit classification; the flip |
| `scripts/b4_flip_assistant.py` | the promoted row registered for assurance + mirror reconciliation |
| `tests/test_platform_completion_truth.py` | assurance pin, no-fall-through pin, twin-row pin |
| `tests/test_ladder9_promotion_evidence.py` | gate-8 pin over the committed evidence |
