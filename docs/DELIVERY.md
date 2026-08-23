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

Push additionally requires a successful receipt bound to the exact local
commit/tree and verification tip. PR create/update additionally requires the
successful push receipt. Each later action requires a new approval artifact.

The service refuses direct `main` delivery, force-push and force-with-lease,
history rewriting, wrong or moved remotes, stale approvals, changed trees,
unexpected dirty paths, arbitrary Git/GitHub arguments, generic shell, and
credential persistence. Failures produce recovery guidance; they do not
produce success receipts.

STRATUM remains read-only. It projects delivery plan/action/approval/receipt
evidence and the next admissible action, but it cannot approve or mutate Git or
GitHub. Review, merge, promotion, release, tags, and publication remain outside
Plan Set 6.
