# B1.4B Read-Only Verification Ledger Queries

## Scope

B1.4B adds read-only query and audit helpers over existing `builder_ii.verification_execution_ledger_record` artifacts under `.builder/ledger/`.

The supported query surface is:

- `builder-ledger query-receipts`
- `builder ledger query-receipts`

The command validates each discovered ledger record before including it in results, reports malformed or invalid records as rejected JSON diagnostics, filters by receipt digest, chain digest, receipt status, and runner mode, and emits deterministic summary counts.

## Authority Boundary

B1.4B is passive/read-only only.

It does not:

- replay execution;
- run verification;
- invoke subprocess, shell, model, MCP, Goose, or deepagents runtime;
- mutate source files, target repo files, git state, memory, patches, or B2 authority;
- add command profiles;
- touch Deephaven-related work.

Missing `.builder/ledger/` directories produce empty valid reports. Invalid ledger root paths fail closed with JSON diagnostics.
