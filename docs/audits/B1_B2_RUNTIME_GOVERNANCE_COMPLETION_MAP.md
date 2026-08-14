# B1/B2 Runtime Governance Completion Map

builder-II is a generic governed local agent/developer platform. CORE is a target profile and lineage context only; this runway must not make builder-II a CORE runtime, CORE Workbench/UI, or second CORE runtime.

## B1 Already Proves

- `builder_ii.verification_execution_plan` records passive verification intent with structured command-profile refs, disabled execution, and digest stability.
- `builder_ii.verification_execution_approval` binds human approval to an exact passive plan digest without granting execution authority.
- `builder_ii.verification_execution_receipt` records the B1.3 receipt contract and the bounded approved `platform_status` runner receipt shape.
- `builder-verify run-approved` is bounded to one in-code profile, fixed argv, `shell=False`, env allowlist, timeout, bounded capture, target/artifact-root validation, and receipt output only.
- `builder_ii.verification_execution_ledger_record` passively indexes validated plan/approval/receipt chains under `.builder/ledger/`.
- `builder-ledger query-receipts` and `builder ledger query-receipts` read existing ledger records, validate each record before inclusion, and emit deterministic JSON query reports without execution or writes.

## B1 Still Lacks

- Passive integrity validation over a set of verification execution ledger records.
- Deterministic duplicate, digest-drift, required-ref, chain-digest, and continuity diagnostics.
- B1.4D is responsible for read-only reconstruction/reporting that summarizes invalid/rejected records, chain continuity, and evidence refs without re-running verification.
- B1 closure docs must prove what remains disabled after B1 before B2 begins.
- Artifact-chain validators for any new B1 report kinds.

## B2 Meaning In This Repo

B2 begins as governed live read, not patching. The first acceptable B2 capability is an explicit, target-bound file metadata/hash inspection template that reads only the operator-supplied path under an allowed boundary and emits a bounded artifact. B2 does not mean source mutation, git mutation, patch application, arbitrary command execution, model/provider calls, MCP/tool calls, Goose runtime start, or deepagents runtime construction.

## Intentionally Disabled

- autonomous writes
- arbitrary shell or argv
- model/provider execution
- MCP/tool execution
- Goose runtime start
- deepagents runtime construction
- source writes
- git mutation
- patch application or B2 write authority
- memory mutation
- Deephaven-related changes
- hidden agent authority

## PR Slices

| Slice | Purpose | Must Not Promote |
|---|---|---|
| B1.4C | Passive verification ledger integrity report over existing `builder_ii.verification_execution_ledger_record` artifacts. | No execution replay, subprocess, shell, model, MCP, Goose, deepagents, source writes, git mutation, patch authority, or B2 authority. |
| B1.4D | Read-only ledger reconstruction/report surface and B1 closure docs. | No command execution, no mutable status authority, no receipt re-run, no broader runtime event classes. |
| B2.0 | Machine-checkable capability promotion gate/checklist. **SHIPPED** as `builder_ii.verification_promotion_evidence` via `builder-verify evaluate-promotion` / `validate-promotion-evidence` — consumes plan/approval/receipt (+ optional ledger), emits pass/fail evidence, never flips matrix or grants authority. | No live filesystem read yet and no write authority. |
| B2.1 | Tiny governed live-read file metadata/hash command for an explicit target path. | No content exfiltration by default, no directory crawling, no source/git mutation, no shell. |
| B2.2 | Passive indexing/query/integrity support for B2 read artifacts. | No patching, no model/tool calls, no runtime expansion beyond explicit read artifact validation. |
| B2 closure | Reconcile truth docs and define preconditions for later B3/write authority. | No B2 write/patch authority. |

## Current Slice

B1.4D should add the reconstruction operator over B1.4C integrity: deterministic read-only receipt-chain projections with invalid/rejected records, chain continuity status, and evidence refs. It emits JSON only in this slice and does not promote execution replay.
