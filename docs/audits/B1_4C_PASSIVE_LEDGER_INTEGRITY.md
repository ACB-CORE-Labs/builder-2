# B1.4C Passive Verification Ledger Integrity

B1.4C adds a read-only integrity report over existing `builder_ii.verification_execution_ledger_record` artifacts under `.builder/ledger/`.

## Command Surface

- `builder-ledger validate-receipts`
- `builder ledger validate-receipts`

The command emits `builder_ii.verification_execution_ledger_integrity_report` JSON to stdout. It does not write report files in this slice.

## What It Validates

- native ledger record schema and record digest stability;
- deterministic ordering by `recorded_at`, `chain_digest`, `ledger_record_id`, and path;
- duplicate `ledger_record_id`, record digest, `chain_digest`, and receipt digest values;
- required plan, approval, and receipt subject refs;
- plan/approval/receipt subject digest consistency with `chain_digest`;
- optional `ledger_index` and `previous_ledger_record_digest` continuity when those index-chain fields are present.

## Authority Boundary

B1.4C is passive validation only. It does not replay execution, re-run verification, run subprocesses, execute shell, call models/tools, invoke MCP, start Goose/deepagents, mutate source files, mutate target repos, mutate git, mutate memory, or promote B2 authority.

## Follow-On B1 Work

B1.4D adds the read-only reconstruction/report surface and B1 closure docs. B1 remains passive foundation only after that closure; broader runtime and write authorities remain disabled until later promotion gates.
