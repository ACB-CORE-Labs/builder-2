# Performance measurement records

`builder_ii.performance_measurement` records operator-supplied performance observations for a candidate capability.

It is explicit-input-only. It does not run benchmarks, inspect hardware, execute shell commands, call models, or grant authority.

## CLI

```text
builder-performance record --target builder --candidate-name readonly_inspection_candidate --metric-name planning_latency_ms --metric-value 12.5 --unit ms --method "operator supplied dry-run note" --source-ref notes/perf.md --output .builder/artifacts/perf.json
builder-performance validate .builder/artifacts/perf.json
```

## Verification

```bash
uv run pytest tests/test_performance_measurements.py tests/test_artifact_index_records.py -q
uv run pytest -q
```
