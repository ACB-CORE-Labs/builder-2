# Plan Set 6 R1 — Exact-tip verification and hosted PR custody

STATUS: `PLANNED_ONLY_AWAITING_DIGEST_BOUND_HITL_APPROVAL`

## Exact binding

- Repository: `https://github.com/ACB-CORE-Labs/builder-2`
- Branch: `codex/plan-set-6`
- PR #19 head: `a347890a6fb9b902734e5a5549d0e5d9593703b2`
- PR #19 tree: `74931273dcbad7c032a6a81596e8602303ef9d0e`
- Frozen base: `a8d926d557e357e21d54e925f1afc76f0bad4c12`

This is a passive correction plan only. It grants no implementation, Git,
GitHub, approval-minting, verification, rehearsal, promotion, merge, or Plan
Set 7 authority.

## Established findings

1. `DeliveryService.execute_push()` accepts a successful
   `builder_ii.delivery_receipt` for `commit` or `push`; the deterministic
   happy path supplies the commit receipt. The service therefore does not
   require `builder_ii.verification_execution_receipt` evidence bound to the
   exact committed tip.
2. `DeliveryService.execute_pr()` emits success from `gh pr create/edit`
   output. CREATE has no independent post-operation `gh pr view`; UPDATE has
   only a partial pre-operation read. The service does not own hosted PR
   custody before success.
3. `validate_delivery_action_request()` validates only the generic envelope
   and digest, not mandatory action-specific predecessor/live-state bindings.

## Governing shape

Preserve one vocabulary and one effect owner:

```text
commit request + approval -> commit receipt
commit receipt + exact-tip verification -> push request + approval -> push receipt/readback
push receipt/readback -> PR request + approval -> hosted PR readback -> PR receipt
```

This strengthens `planned != executed != verified != promoted` and
`artifact != authority`. A commit receipt remains predecessor evidence and is
never verification evidence.

## Bounded correction after separate HITL approval

### Canonical action requests

In `builder_ii/core/delivery.py`, require `bindings` to be an object with exact
action-specific keys and types:

- COMMIT: expected HEAD/tree/branch, planned paths/diff, remote identity.
- PUSH: commit receipt digest, exact commit SHA/tree, verification receipt
  digest, feature branch/remote identity, expected remote head.
- PR_CREATE: push receipt digest, hosted head SHA, head/base branches, expected
  base SHA, title/body/draft.
- PR_UPDATE: all PR_CREATE bindings plus a positive exact PR number.

Missing, malformed, stale, or substituted bindings are schema-invalid. Do not
infer required bindings from defaults. Preserve canonical digests, non-authority
pins, registries, and the existing artifact family.

### Exact-tip PUSH verification

In `builder_ii/core/delivery.py` and thin CLI wiring in
`builder_ii/cli/delivery_cli.py`:

- Require commit receipt and verification evidence separately.
- Validate a real `builder_ii.verification_execution_receipt` and its canonical
  plan/approval chain with the existing artifact and cross-binding validators.
- Require `valid == true`, `receipt_status == EXECUTED`, exact target repo,
  `target_commit == current HEAD == request commit SHA`, matching verification
  digest, and successful required process results.
- Re-capture source/workspace state and require clean HEAD/tree equality with
  the verified commit immediately before push.
- Preserve fixed Git argv, feature-branch/remote/remote-head controls, and
  hosted branch readback.

### Hosted PR custody

In `builder_ii/core/delivery.py`:

- After CREATE or UPDATE, run fixed-argv `gh pr view <exact identity> --json`
  for number, URL, state, head branch/SHA, base branch/SHA, title, body, and
  draft state.
- Parse fail-closed and compare every field to the request, plan, validated
  push receipt, and expected base binding.
- Preserve UPDATE preflight custody and require matching post-operation custody.
- Mint `SUCCEEDED` only after exact readback; record that hosted custody in the
  receipt. Malformed, missing, or mismatched readback refuses.

### Lesions and truth surfaces

In `tests/test_delivery.py`, replace the false commit-receipt-as-verification
happy path with canonical verification fixtures and add refusals for:

- commit receipt without verification; previous-commit verification;
  FAILED/non-EXECUTED verification; digest substitution; HEAD/tree drift;
- PR create head mismatch; base SHA mismatch; title/body/draft mismatch;
  malformed/missing readback; externally changed UPDATE custody;
- missing action-specific predecessor bindings for every action.

Update only affected Set 6 command/operator truth if concrete artifact inputs
change. Do not flip promotion state or widen authority.

## Requalification and delivery

1. Focused Set 6 delivery, artifact-chain, CLI, authority, projection, docs
   truth, and matrix tests.
2. Deterministic delivery qualification with temporary/local bare remotes and
   fixed mocked `gh` custody responses.
3. Final diff/scope review.
4. One settled-tip `bash scripts/ci.sh --receipt <fresh-path>`.
5. Precise commit; push corrected PR #19 head only after local CI passes.
6. Repeat the live rehearsal using fresh branch
   `codex/rehearsal-delivery-r2`; create rehearsal PR #2 and leave it unmerged.
7. Update PR #19 with corrected SHA/tree and new evidence; stop for hosted
   review. Do not merge.

## Denied scope and HITL stop

No Plan Set 7, merge, promotion, release, publication, tags, force-push,
history rewrite, generic shell/arbitrary argv, approval minting, credential
persistence, or unrelated cleanup. Preserve the dirty primary checkout.

Implementation must halt until a human supplies a digest-bound approval
artifact or equally explicit repository-recognized approval binding this exact
plan digest, source head/tree, permitted files/effects, verification sequence,
live rehearsal scope, and denied operations.
