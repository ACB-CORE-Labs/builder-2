# B1.4D Passive Ledger Reconstruction

B1.4D adds a read-only reconstruction report over existing `builder_ii.verification_execution_ledger_record` artifacts under `.builder/ledger/`.

## Command Surface

- `builder-ledger reconstruct-receipts`
- `builder ledger reconstruct-receipts`

The command emits `builder_ii.verification_execution_ledger_reconstruction_report` JSON to stdout. It does not write report files in this slice.

## What It Reconstructs

- deterministic receipt-chain projections ordered by `recorded_at`, `chain_digest`, `ledger_record_id`, and path;
- summary counts by receipt status, runner mode, and process result status;
- invalid and rejected record diagnostics from the integrity layer;
- chain continuity status from the optional index-chain rule;
- evidence refs back to the passive ledger records being reconstructed.

## Authority Boundary

B1.4D is passive reconstruction only. It does not replay execution, re-run verification, load receipt/plan/approval files, run subprocesses, execute shell, call models/tools, invoke MCP, start Goose/deepagents, mutate source files, mutate target repos, mutate git, mutate memory, or promote B2 authority.

## Relationship To B1.4C

B1.4C validates ledger integrity. B1.4D consumes that integrity result and renders a deterministic reconstruction/report surface for review. The reconstruction report is invalid whenever the integrity report is invalid.
