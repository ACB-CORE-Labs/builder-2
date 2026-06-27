# Platform Completion Audit

## Identity & Philosophy
* **builder-II** is a generic-first governed local agent/developer platform.
* **CORE** is a target profile, not the runtime itself.
* **builder-II** is not CORE Workbench/UI or a second CORE runtime. It remains decoupled from any CORE Workbench/UI coupling.

## Completed Foundation
The following structural and metadata tracking foundations are fully completed and verified:
* **target profiles**
* **verification profiles**
* **context pack records**
* **agent profile records**
* **explicit git state records**
* **command proposal records**
* **approval records**
* **preflight records**
* **receipt records**
* **handoff bundles**
* **intake records**
* **artifact index**
* **chain verification**
* **promotion readiness**
* **promotion decisions**
* **state ledger**
* **snapshots**
* **research adapters**
* **performance measurements**
* **readonly inspection promotion spec**
* **readonly inspection reports**
* **readonly inspection promotion wiring**

## Current Runtime-Candidate Capability
The only current runtime-candidate capability is:
* **bounded read-only inspection report**

This capability is strictly constrained by the following rules:
* **explicit file paths only**
* **metadata/SHA-256 only**
* **optional root boundary**
* **no content capture**
* **no traversal**

## Not Yet Promoted
The following capabilities and runtimes are not yet promoted:
* **shell execution** (disabled)
* **model execution** (disabled)
* **patch application**
* **commit/push automation**
* **Goose runtime activation** (disabled)
* **deepagents runtime** (disabled)
* **MCP execution**
* **arbitrary repository traversal**
* **content capture**
* **voice/TTS/STT**
* **CORE Workbench/UI coupling**

## Governance Assertions
* **No autonomous writes**: The platform does not perform or claim autonomous write operations.
* **Shell execution is disabled**: There is no active shell execution capability.
* **Model execution is disabled**: The platform does not invoke or execute AI models directly at runtime.
* **Deepagents runtime is disabled**: The deepagents bridge/runtime is not enabled.
* **Goose runtime is disabled**: The Goose runtime environment is not enabled.

## Release Verification Checklist
Use this checklist when validating the current governed platform state. Paths shown are examples; operators must supply real artifact paths for their run.

```bash
uv run pytest -q
builder-index validate <artifact-index>
builder-chain verify <artifact-path>...
builder-promotion record --capability-name <name> --target <target> ...
builder-promotion-decision record <promotion-readiness>
builder-state-index validate <state-index>
builder-snapshot validate <snapshot>
builder-inspect report --target <target> --purpose review --path <explicit-file> --output <readonly-inspection-report>
builder-inspect validate <readonly-inspection-report>
```

## Next Arcs
* **HITL command execution spec**
* **execution receipts**
* **HITL patch proposal/application artifacts**
* **rollback artifacts**
* **optional Goose runtime after promotion**
* **optional deepagents bridge after promotion**
