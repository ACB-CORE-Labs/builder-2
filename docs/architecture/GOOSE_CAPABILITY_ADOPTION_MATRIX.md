# Goose capability adoption matrix

Status: source-grounded design matrix. An adoption decision is not runtime
qualification, approval, or promotion.

Current local observation on 2026-08-24: Goose `1.47.0` is installed. Current
builder-II compatibility policy is `>=1.45.0,<1.47.0`; therefore that binary is
not admitted until the exact compatibility battery passes and policy changes are
reviewed. Builder-II never auto-updates or downgrades Goose.

| Goose capability | Decision | Canonical boundary |
| --- | --- | --- |
| Named sessions | ADOPT | one logical Goose session per builder run |
| Resume and history display | ADOPT | validate run/checkpoint/target/policy first |
| Export and diagnostics | ADOPT | bind bytes as evidence refs; diagnostics are not proof |
| Fork | ADOPT | creates a new builder run lineage |
| In-place history edit | FORBID | edit only after fork with transcript digests |
| Max turns/repetition bounds | ADOPT | values derive from WRP run policy |
| Context revision/compaction | QUALIFY | governance-critical facts require exact retention |
| Recipes and parameters | ADOPT | interaction/configuration only, never topology |
| Structured outputs/retry | QUALIFY | retry format/transport only; never denial or drift |
| Sub-recipes | DEFER | may not become a second orchestration graph |
| Skills | PROJECT/QUALIFY | builder guidance service first; native skill loading only after isolated proof |
| Custom roles/agents | PROJECT | project canonical profiles; no native delegation authority |
| Goose-native subagents | FORBID | Deep Agents through builder-II is the canonical orchestrator |
| MCP extension | ADOPT | exactly builder-II's admitted MCP surface |
| Developer/shell builtins | FORBID | no ambient filesystem, shell, Git, or write authority |
| Permission modes | NON-AUTHORITATIVE | builder services decide; UI labels runtime BUILDER-GOVERNED |
| Adversary reviewer | DEFER/ADVISORY | fail-open output cannot gate or prove safety |
| Hooks | DEFER/OBSERVATIONAL | never approval, receipt, ledger, or mutation custody |
| ACP server/provider | RESEARCH LATER | no canonical nesting or second session owner |
| Desktop-only activities | DEFER | terminal-first program |

## Current lifecycle custody

The canonical governed launch now targets one run namespace:

```text
<artifact-root>/sessions/<run>/goose/{launch,postflight,close}.json
<artifact-root>/sessions/<run>/goose/transcript.json
<artifact-root>/sessions/<run>/events/
```

Launch and close artifacts must pass their owning validators and be persisted
before `goose_session_started` or `goose_session_closed` may bind them. The
close receipt binds the launch receipt, postflight, and exact transcript digest.
Target-local receipt mirrors remain compatibility projections and are not the
run registry's authority source. This is implemented start/close custody, not
resume, cancellation, orphan recovery, context retention qualification, or
Goose-version promotion.

## Compatibility gate

For each candidate Goose version:

1. Probe semantic version and binary SHA-256 in isolated writable state.
2. Validate exact CLI capabilities used by builder-II.
3. Validate the governed recipe digest and sole extension inventory.
4. Exercise launch, MCP discovery/call/refusal, model loopback, cancellation,
   transcript export, resume, diagnostics, target-drift refusal, and close.
5. Run sabotage cases for native builtin exposure, recipe drift, session mismatch,
   malformed output, MCP death, and incomplete postflight.
6. Widen the version range only after focused tests, exact-tip evidence, local CI,
   docs/matrix consistency, and review.

## Deep Agents boundary

Goose remains the human foreground. Durable multi-agent work is requested through
the builder delegation service and executed by the separately admitted Deep Agents
runtime. Goose does not choose the final topology, models, budgets, tools,
concurrency, checkpoints, or evidence namespace.
