# Session Handoff - 2026-07-02

## 1. Summary of Changes
Restored governed Goose launch behavior from STRATUM and removed the raw `goose session` bypass.

### Files Changed:
- `builder_ii/goose_launcher.py`: Added `resolve_model_id`, `derive_goose_environment`, updated `goose_env` and `launch_goose_session` (which now checks launch readiness).
- `builder_ii/tui/app.py`: Updated TUI's `action_launch_goose` to use `launch_goose_session` and show a redacted environment preview.
- `builder_ii/goose_cli.py`: Registered `builder-goose env` and `builder-goose status --env` commands.
- `tests/test_goose_launcher.py`: Appended unit tests covering the environment projection, launcher, diagnostic propagation, and TUI adapter calls.
- `docs/GOOSE_CONVENTION_LAYER.md`: Updated documentation describing the launcher behavior, configurations, and environment variables.

---

## 2. Invariants Verification Table

| Invariant | Checked | Status |
|---|---|---|
| `versor_condition(F) < 1e-6` | Yes | PASS (No core math files modified, full suite passed) |
| Exact CGA recall only | Yes | PASS (No cosine/ANN/HNSW used) |
| No stochastic paths | Yes | PASS |
| Secrets redacted | Yes | PASS (Validated via tests and git diff checking) |
| Canonical adapter only | Yes | PASS (Both `builder start` and STRATUM use the same adapter) |

---

## 3. Exact Pytest Output
```
846 passed, 2 warnings in 17.65s
```

---

## 4. Architectural Decisions
- Centralized model/provider resolution into `derive_goose_environment` in `goose_launcher.py`.
- TUI and CLI both consult the same module, ensuring identical environment variables are set and the same diagnostic command is called.
- Kept `goose configure` optional.

---

## 5. Next Steps / Open Tasks
- Submit PR for review.
- Close this hotfix.
