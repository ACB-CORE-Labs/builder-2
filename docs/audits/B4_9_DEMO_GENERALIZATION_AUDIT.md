# B4.9 Demo Generalization Audit — Governed Demo Loop (plan item 1.8)

This audit records the pin edit that renamed the completion-matrix row "CORE demo loop" to
"governed demo loop" and widened its promoted surface from AssetOverflow/core-only to a temporary
detached worktree of any operator-designated local git repository. The row's state does not change:
it stays `OPERATIONALLY_VERIFIED` with assurance `DEMO_ONLY_VERIFIED`, and the
`operationally_verified_count` pin stays 17 — this is a scope re-statement backed by new evidence,
not a state flip.

It is **not** a promotion of anything autonomous. `builder-platform demo-loop` and
`builder-platform wow` remain Tier 3 `hitl_runtime_candidate`, operator-invoked, never `enabled`
for unattended execution. No command changes promotion state.

## What generalized (mechanism)

- `builder_ii/core_demo_loop.py` became `builder_ii/core/demo_loop.py`. A frozen `DemoTargetSpec`
  parameterizes the marker patch path, the sensitive-path-prefix policy, and the repo identity
  check. `target_name="core"` selects the CORE profile with its original
  `AssetOverflow/core`-remote/dirname identity check and its eight sensitive-module prefixes;
  any other target name runs the generic spec, which requires only an existing local git checkout.
- Artifact kinds renamed as a pre-v0.1.0 hard cut (D9; no dual-version parsers, no committed
  artifacts to migrate): `builder_ii.demo_deterministic_planner`, `builder_ii.demo_preflight`,
  `builder_ii.demo_verification_receipt`, `builder_ii.demo_loop_report`.
- The narrative `builder_ii.core_demo_approval` kind was **deleted**, not renamed. The demo's
  `--approve` gate now mints the one real authorization artifact directly — the generic
  `builder_ii.hitl_patch_approval` (plan item 1.1), bound to the proposal content and patch
  digests. On the unapproved path no approval artifact is minted at all: the absence of a valid
  approval IS the unapproved state, which keeps planned ≠ approved sharp instead of blurring it
  with a "rejected approval" record.
- Demo verification got strictly stronger for every target: an `only_demo_marker_mutated` check
  requires the worktree's entire porcelain status (untracked-files=all) to consist of the marker
  path alone, in addition to the CORE profile's sensitive-prefix check. The marker path itself is
  fail-closed validated (relative, no traversal, never `.git/`, never under a sensitive prefix).

## Evidence

Every gate below is exercised by `tests/test_demo_loop.py` on a plain generic fixture repo (no
CORE identity) and on the CORE profile; the full suite passes on the edited tree.

| Gate | Generalized demo lane |
| --- | --- |
| **Docs** | `docs/CORE_DEMO_WALKTHROUGH.md` (CORE profile walkthrough + generic-target section), this audit |
| **Tests** | `tests/test_demo_loop.py` — generic end-to-end, CORE-profile end-to-end, identity-check refusal, no-approval refusal, marker-path fail-closed cases, extra-mutation verification failure, receipt binding |
| **Command surface** | `builder-platform demo-loop` (`--target-repo`, `--target-name`, `--marker-path`), `builder-platform validate-demo-loop`, `builder-platform wow` |
| **Failure mode** | Fails closed on missing target repo, failed CORE identity check, invalid marker path, dirty worktree, missing approval, digest mismatch, verification-check failure (writes a FAILED receipt and raises), rollback failure, or final dirty worktree |
| **Human approval boundary** | Explicit operator `--approve` mints the generic `builder_ii.hitl_patch_approval`; without it no approval artifact exists and apply refuses |
| **Output artifact** | Preflight, planner, proposal, approvals, demo verification receipts, apply/rollback receipts, final postflight, chain report, artifact index, `demo-loop-report.json`, `DEMO_EVIDENCE.md` |
| **Rollback path** | Mandatory: the marker patch is always rolled back through the governed rollback lane (distinct `builder_ii.hitl_rollback_approval`), with a final clean postflight that raises if the worktree is not returned clean |
| **Verification path** | Pre- and post-apply `builder_ii.demo_verification_receipt` with marker-state, only-marker-mutated, and (CORE) sensitive-prefix checks; final chain verification over the whole artifact set including both approvals |

## Fallback decision (`demo_verification_receipt` in the apply gate)

The plan item required deciding whether the demo-receipt fallback in
`hitl_patch_apply._verification_receipt_errors` survives. **Decision: it survives**, renamed to
`builder_ii.demo_verification_receipt`, for these reasons:

- A real `builder_ii.verification_execution_receipt` is profile-bound: the runnable profiles are
  builder-self checks (which the 1.3 hardening deliberately refuses to run against foreign repos)
  and `pytest_full` (which requires the target to be a trusted local Python-with-pytest repo). An
  arbitrary demo target satisfies neither, so requiring a real receipt would either make the demo
  unrunnable or launder an unrelated builder-self receipt through the gate — worse, not better.
- The fallback is **narrower than the general path**, not looser: the demo receipt must be bound to
  the exact proposal target repo (`target.repo` match), labeled `before_apply`, fully `EXECUTED`
  with every check `PASS`, and it self-describes demo scope in its kind and governance block.
- The known gap that a general verification receipt is not target-bound remains the recorded 2.x
  follow-up from the 1.3 review; this fallback does not widen it.

## Containment (unchanged)

The demo loop remains the single sanctioned in-process minter of `hitl_patch_approval` /
`hitl_rollback_approval` recorded by `docs/audits/B4_CLOSURE_AUDIT.md`. Generalizing the target
does not widen the mutation surface: mutation is still exactly one temporary documentation marker
file, inside a disposable detached worktree, always rolled back, with the source checkout untouched
and checked untouched. The command-authority gate and the approval binding/expiry re-checks inside
`apply_hitl_patch` / `rollback_hitl_patch` apply to the demo identically to any other caller.

## Still not promoted (unchanged by this edit)

- autonomous or automatic source mutation of any target;
- git commit, push, or pull-request automation;
- model/provider execution, MCP/tool invocation, Goose runtime start, deepagents runtime,
  memory mutation;
- any command moving to the `enabled` promotion state.

## Pin edit set authorized by this audit

Consistency-checked by `scripts/b4_flip_assistant.py` (extended with the "governed demo loop" row):

- `builder_ii/core/platform_completion_audit.py`: row renamed to "governed demo loop"; evidence,
  tests, scope statements, and `next_pr` updated; `assurance_state_for_row` mapping renamed;
  human-summary sentence generalized.
- `tests/test_platform_completion_truth.py`: the assurance assert keyed by the renamed row.
- `docs/PLATFORM_COMPLETION_AUDIT.md`: the mirror table row and demo-loop prose.
- `builder_ii/governance/authority/`: the three demo command records' narrative boundaries
  (tier and promotion state untouched); `docs/COMMAND_AUTHORITY.md` regenerated.

## Next gate

R1 (plan item 2.6) owns the next matrix flip. This audit does not authorize it, and it does not
change `operationally_verified_count`.
