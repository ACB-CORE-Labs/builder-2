# B1.4A Passive Execution Ledger Scope

## Purpose

B1.4A indexes validated B1.3 verification execution receipt chains into passive ledger records.

## Scope

- ingest a verification execution plan, approval, and receipt JSON chain;
- require all referenced artifacts to validate and carry `valid=true`;
- verify approval-to-plan and receipt-to-plan/approval bindings;
- emit one deterministic `builder_ii.verification_execution_ledger_record` artifact;
- write ledger records only under the target repo `.builder/ledger/` directory through `builder-ledger index-receipt`.

## Boundaries

This slice is passive indexing only. It does not replay execution, re-run verification, expand command profiles, invoke shell/model/MCP/Goose/deepagents runtimes, mutate source files, mutate git, or grant B2 patch authority.

## Next Step After B1.4A

After this passive index is proven, B1.4B can add read-only chain queries over verification execution ledger records. Active replay remains out of scope until passive ledger records, validators, command authority, and rollback boundaries are complete.
