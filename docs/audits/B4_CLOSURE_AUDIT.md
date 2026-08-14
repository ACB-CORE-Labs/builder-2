# B4 Closure Audit — HITL Patch Application + Rollback Execution

B4 is closed for the **operator-invoked, approval-gated** patch application and rollback lane. This
audit is the receipts-backed evidence that authorizes flipping two completion-matrix rows — "HITL
patch application" and "rollback execution" — from `MERGED_BUT_NOT_OPERATIONAL` to
`OPERATIONALLY_VERIFIED` (assurance state `MUTATION_WITH_ROLLBACK_VERIFIED`).

It is **not** a promotion of autonomous or automatic source mutation. The `builder-hitl apply-patch`
and `builder-hitl rollback` commands remain Tier 3 `hitl_runtime_candidate` — approval-gated,
operator-invoked, never `enabled` for unattended execution. The distinction this whole platform rests
on holds here: *operator-invoked-with-approval is verified; autonomous apply stays forbidden.*

Scope: the two matrix rows above only. No change to command promotion tiers, to the verification
lane, to Goose/deepagents/model/MCP promotion, or to the `enabled` state of any command.

## Eight-gate evidence

Each gate is mapped to the code, artifact, or test that satisfies it. Every referenced test passes on
the flipped tree (`uv run pytest -q`).

| Gate | HITL patch application | Rollback execution |
| --- | --- | --- |
| **Docs** | `docs/HITL_PATCH_PROPOSAL.md`, this audit | `docs/HITL_PATCH_PROPOSAL.md`, this audit |
| **Tests** | `tests/test_hitl_patch_apply.py`, `tests/test_hitl_patch_cli.py`, `tests/scenarios/test_hitl_patch_lane_unmocked.py` | `tests/test_hitl_patch_rollback.py`, `tests/test_hitl_rollback_drift.py` |
| **Command surface** | `builder-hitl propose-patch` → `approve-patch` → `apply-patch` | `builder-hitl approve-rollback` → `rollback` |
| **Failure mode** | Refuses + exits non-zero on unclean tree, invalid/expired/unbound approval, digest mismatch, or failed `git apply`; writes a patch-apply-failure receipt with the pre-apply HEAD for recovery | Refuses **before touching the tree** on working-tree drift (HEAD moved or post-apply fingerprint mismatch) or failed reverse apply; writes a rollback-failure receipt carrying a recovery block (pre-apply HEAD, exact `git reset --hard <sha>` + data-loss warning, chain-invalidation) |
| **Human approval boundary** | Schema-valid, unexpired `builder_ii.hitl_patch_approval` bound to the proposal content + patch digests, minted only through the interactive digest-prefix TTY prompt of `approve-patch` (no non-interactive approval mode) | Distinct `builder_ii.hitl_rollback_approval` bound to the rollback-plan content + patch digests, minted only through the interactive `approve-rollback` prompt |
| **Output artifact** | `patch_apply_receipt.json`, `postflight_record.json`, `rollback_bundle.json` | `rollback_receipt.json` (success) or `rollback_failure_receipt.json` (refusal) |
| **Rollback path** | Apply auto-generates a bound reverse patch + `rollback_plan.json` and records a post-apply working-tree fingerprint | The rollback command itself, drift-hardened; failure instructs rather than strands |
| **Verification path** | Requires a schema-valid `builder_ii.verification_execution_receipt` before it writes (gate inside `apply_hitl_patch`) | Reverse-patch digest binding + drift preflight verified before `git apply -R` |
| **Command authority registry** | `builder-hitl apply-patch` (Tier 3, `hitl_runtime_candidate`, `MODE_HITL_ARTIFACT_REQUIRED`), gate enforced at the execution boundary inside `apply_hitl_patch` | `builder-hitl rollback` (Tier 3, `hitl_runtime_candidate`, `MODE_HITL_ARTIFACT_REQUIRED`), gate enforced inside `rollback_hitl_patch` |
| **Ledger integration** | Emits `builder_ii.hitl_patch_ledger_record` (`patch_applied`) binding the governing chain's digests; validates through the artifact index + chain-verification registries | Emits `builder_ii.hitl_patch_ledger_record` (`patch_rolled_back`); standalone, chain-verifiable |

The unmocked end-to-end scenario (`tests/scenarios/test_hitl_patch_lane_unmocked.py`) exercises the full
chain — propose → approve → apply → approve-rollback → rollback — against a real git tree using a real
`verification_execution` plan/approval/receipt, with no validator mock, and confirms the ledger records
chain-verify natively. That scenario is the operational proof behind this flip.

## Non-interactive-mint containment (promotion gate)

`create_hitl_patch_approval` and `create_hitl_rollback_approval` are public library functions: an
in-process caller can compute the digest prefix and mint a schema-valid approval without a human at a
TTY. This is contained, and the containment must survive promotion:

- The only **promoted, operator-facing** mint path is the interactive `approve-patch` / `approve-rollback`
  CLI, which requires the operator to transcribe the digest prefix. There is no non-interactive
  approval mode on those commands by design — scripting the prompt would collapse `planned ≠ approved`.
- The only **in-process** minter is the CORE demo loop, which is bounded to a temporary detached
  worktree with a mandatory auto-rollback and a final postflight, and is a separate `DEMO_ONLY_VERIFIED`
  capability row — not this one.
- The approval artifact is evidence, not authority (`artifact_is_authority` is always False); the
  execution boundary re-checks the binding and expiry inside `apply_hitl_patch` / `rollback_hitl_patch`
  regardless of how the artifact was produced.

The promotion is therefore scoped to operator-invoked apply/rollback through the TTY approval boundary.
No non-interactive mint reaches a real target on the promoted path.

## Still disabled (unchanged by this flip)

- autonomous or automatic source patch application (no unattended apply exists);
- git commit, push, or pull-request automation;
- arbitrary repository writes outside the explicit artifact output directory;
- any command moving to the `enabled` promotion state — every command here stays Tier 3
  `hitl_runtime_candidate`;
- model/provider execution, MCP/tool invocation, Goose runtime start, deepagents runtime, memory
  mutation.

## Non-authority statement

A valid patch approval, rollback approval, apply receipt, rollback receipt, or ledger record is
evidence, not permission. The human approval boundary is the interactive digest-prefix prompt; the
execution boundary re-verifies the bound digests and expiry and the command-authority gate before any
source write. Ledger records index that an event occurred; they never re-execute it.

## Matrix flip authorized by this audit

This audit authorizes, as one atomic change, the following pinned-site edits (all consistency-checked by
`scripts/b4_flip_assistant.py`):

- `builder_ii/core/platform_completion_audit.py`: "HITL patch application" and "rollback execution" rows →
  `OPERATIONALLY_VERIFIED`; evidence/tests/scope statements updated.
- `tests/test_platform_completion_truth.py`: `operationally_verified_count` 15 → 17; the two assurance
  asserts `BLOCKED_BY_EVIDENCE` → `MUTATION_WITH_ROLLBACK_VERIFIED`.
- `builder_ii/governance/hitl/hitl_patch_apply.py`: the three receipt/postflight/bundle governance self-stamps →
  `OPERATIONALLY_VERIFIED`, in lockstep with the matrix.
- `docs/CAPABILITY_PROMOTION.md` and `docs/RUNTIME_PROMOTION.md`: reconciled so the operator-invoked
  lane reads as `OPERATIONALLY_VERIFIED` while autonomous apply stays not enabled.

## Next gate

B4.9 (plan item 1.8) generalizes the CORE demo loop to arbitrary generic targets and decides whether the
`core_demo_verification_receipt` fallback survives. R1 (plan item 2.6) owns the next matrix flip. This
audit does not authorize either.
