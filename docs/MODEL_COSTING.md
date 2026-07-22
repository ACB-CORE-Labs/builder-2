# Model costing (price book + measured tokens)

**State:** RECORDED_ONLY metering substrate for model receipts and cost-aware routing.  
**Not** billing authority. **Not** execution authority. Planned ≠ executed ≠ verified ≠ promoted.

## Artifacts

| Kind | Module | Role |
| --- | --- | --- |
| `builder_ii.price_book` | `builder_ii/routing/price_book.py` | Per-model `$/1k` in+out, tokenizer id/version, latency class |
| `builder_ii.model_budget` | `builder_ii/routing/model_budget.py` | Session/task token+USD limits; immutable debit versions |
| receipt `cost_report` | `builder_ii/routing/model_execution_gateway.py` | Measured tokens + USD on every call |

## Token accounting honesty

- Default path uses the pinned pure-Python tokenizer `builder_ii.whitespace_v1` (`token_accounting: "measured"`).
- Optional `tiktoken.cl100k_base` when installed for OpenAI-family model ids.
- `token_accounting: "estimated"` is **only** valid with an explicit `estimated_reason` — silent word-count-as-measured is rejected by validators.

## CLI

```bash
uv run builder-model-policy price-book -o .builder/artifacts/price_book.json
uv run builder-model-policy validate-price-book .builder/artifacts/price_book.json
uv run builder-model-policy validate .builder/artifacts/price_book.json
```

## Budget (seam)

The WRP `invoke_local` gateway mode requires a `builder_ii.model_budget` (or `auto_budget=true` for demos).  
Overspend raises `BudgetExceededError` / gateway node failure before the provider call.

Distinct from Ladder-4 `budget_partition` (events/bytes) on deepagents obligations.

## Routing

`create_model_routing_recommendation` may re-rank by cost class and price-book blended rate when `prefer_cheapest_capable` is true. Recommendations remain `RECOMMENDATION_ONLY`.
