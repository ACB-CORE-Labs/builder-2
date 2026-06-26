# Promotion decisions

Promotion decision records consume a promotion readiness record and record an approved or blocked decision.

They are metadata-only records. They do not enable a capability or grant authority.

An approved decision requires a ready promotion readiness record and a decision maker.

If the readiness record is blocked, the decision record is also blocked.

Validation also checks the stored readiness reference shape, blocker consistency, check-list shape, and disabled governance boundary.

## CLI

```text
builder-promotion-decision record PROMOTION_READINESS_JSON --decision approved --decided-by operator --reason reviewed --output promotion-decision.json
builder-promotion-decision validate promotion-decision.json
```

## Verification

```bash
uv run pytest tests/test_promotion_decision_records.py tests/test_promotion_decision_cli.py -q
uv run pytest -q
```
