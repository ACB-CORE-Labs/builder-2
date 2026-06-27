# Research adapter artifacts

`builder_ii.research_adapter` records an explicit bridge from a research plan artifact to a later review process.

It is metadata-only. It records a plan path and digest supplied by the operator.

It does not browse, collect sources, call models, invoke tools, scan files, mutate memory, or grant authority.

## CLI

```text
builder-research adapter --target builder --topic topic --research-question question --plan-path .builder/artifacts/research-plan.json --plan-sha256 DIGEST --output .builder/artifacts/research-adapter.json
builder-research validate-adapter .builder/artifacts/research-adapter.json
```

## Verification

```bash
uv run pytest tests/test_research_adapters.py tests/test_research_plans.py -q
uv run pytest -q
```
