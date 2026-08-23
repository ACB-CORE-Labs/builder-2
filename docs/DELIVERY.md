# Governed GitHub delivery

Plan Set 6 provides one digest-bound delivery lineage with three separate
effect boundaries:

```text
delivery_plan
  -> commit action request + human approval -> commit receipt
  -> exact-tip verification receipt
  -> push action request + human approval -> push receipt/readback
  -> PR create/update action request + human approval -> PR receipt/readback
```

The distinctions are intentional:

```text
LOCAL COMMIT != PUSH != PR CREATION/UPDATE != REVIEW != PROMOTION
```

The artifacts are evidence, not authority. `builder deliver` never mints an
approval. It displays the current stage and, when explicitly invoked with an
exact action request and human approval, calls the single `DeliveryService`
owner for that one effect.

## Operator surface

Inspect the next stage:

```bash
uv run builder deliver --plan <delivery-plan.json>
```

Execute one approved action:

```bash
uv run builder deliver \
  --plan <delivery-plan.json> \
  --action commit \
  --request <commit-action-request.json> \
  --approval <commit-approval.json> \
  --repo <target-repository> \
  --execute
```

Push additionally requires four distinct canonical inputs: the successful
commit receipt, the verification execution plan, its human verification
approval, and the resulting `EXECUTED` verification receipt. The push request
binds both predecessor digests plus the exact local commit/tree, branch,
remote, and expected hosted branch head. The service validates the complete
verification plan/approval/receipt chain, requires every approved process to
have succeeded, and rechecks a clean matching HEAD/tree immediately before
push. A commit receipt is predecessor evidence, never verification evidence.

```bash
uv run builder deliver \
  --plan <delivery-plan.json> \
  --action push \
  --request <push-action-request.json> \
  --approval <push-approval.json> \
  --commit-receipt <commit-receipt.json> \
  --verification-plan <verification-plan.json> \
  --verification-approval <verification-approval.json> \
  --verification-receipt <verification-receipt.json> \
  --repo <target-repository> \
  --execute
```

PR create/update additionally requires the successful push receipt. Its action
request binds the exact hosted head, head/base branches, expected base SHA,
title, body, draft state, and—on UPDATE—the exact PR number. After every CREATE
or UPDATE, the service independently runs fixed-argument `gh pr view --json`
and compares the hosted number, URL, state, head/base custody, metadata, and
draft state before it can emit `SUCCEEDED`. Each later action requires a new
approval artifact.

The service refuses direct `main` delivery, force-push and force-with-lease,
history rewriting, wrong or moved remotes, stale approvals, changed trees,
unexpected dirty paths, arbitrary Git/GitHub arguments, generic shell, and
credential persistence. Failures produce recovery guidance; they do not
produce success receipts.

STRATUM remains read-only. It projects delivery plan/action/approval/receipt
evidence and the next admissible action, but it cannot approve or mutate Git or
GitHub. Review, merge, promotion, release, tags, and publication remain outside
Plan Set 6.
