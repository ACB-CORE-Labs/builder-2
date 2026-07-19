# Last-mile release checklist (W5.4)

Operator playbook for proving the governed execution muscle on real targets.
This is a **checklist**, not a promotion grant.

## Preflight

- [ ] `uv sync --all-groups`
- [ ] `bash scripts/ci.sh` — ALL BLOCKING GATES PASSED
- [ ] Confirm `BUILDER_ALLOW_CLOUD_MODELS` only when intentionally testing cloud
- [ ] No raw API keys in artifacts (token refs only)

## Local seam demo (generic / builder)

```bash
# Record mode (always safe)
uv run builder-wrp --help  # surface present

# Invoke-local seam (stub provider; offline)
uv run pytest tests/test_wrp_invoke_local_seam.py tests/test_subagent_step_via_seam.py -q

# Subagent multi-step loop
uv run pytest tests/test_subagent_loop.py -q
```

## Cost honesty

```bash
uv run pytest tests/test_price_book.py tests/test_gateway_measured_cost.py tests/test_model_budget.py -q
uv run pytest tests/test_cost_aware_routing.py -q
```

## Cloud (gated)

```bash
uv run pytest tests/test_invoke_cloud_seam.py tests/test_cloud_chat.py -q
# Live cloud (operator only): set GROQ_API_KEY / OPENAI_API_KEY + BUILDER_ALLOW_CLOUD_MODELS=true
```

## Class U + S3 ceremony path

```bash
uv run pytest tests/test_wrp_class_u_harness.py tests/test_s3_enablement.py -q
# Session-scoped S3 enable requires Class U proof held + human approval decision
```

## Replay / OTel / secrets

```bash
uv run pytest tests/test_replay_harness.py tests/test_otel_ledger_export.py tests/test_secret_redaction.py -q
```

## Target demos

| Target | Command |
| --- | --- |
| generic | Class U harness `target=generic` |
| builder | Class U harness `target=builder` (default) |
| core | Class U harness `target=core` (CORE_REPO_PATH when needed) |

```bash
uv run python -c "from builder_ii.wrp.class_u_harness import run_class_u_harness; r=run_class_u_harness(target='builder'); print(r['summary'])"
```

## Release honesty pins

- [ ] Permanent non-goal: HITL arbitrary command exec remains disabled
- [ ] AgentFactory default lifecycle records still `spawn_executed=false`
- [ ] Subagent **loop** may set `spawn_executed=true` only under budget+HITL+kill-switch
- [ ] Global registry `s3_enabled` default remains false; session binding is separate
- [ ] PR body cites local `bash scripts/ci.sh --receipt`, not remote honor-system alone
