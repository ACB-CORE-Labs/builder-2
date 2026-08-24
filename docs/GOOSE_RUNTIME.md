# Goose Runtime Specification

This document defines how builder-II treats Codename Goose as the preferred local runtime and operator substrate while preserving builder-II governance and authority boundaries.

---

## 1. Identity & Authority Boundary

```text
builder-II  = Sovereign governed control plane & authority registry
Goose       = Governed local operator runtime adapter
deepagents  = Governed inner planning & delegation harness
Target Repo = generic / builder / core
```

Goose is the muscle for local interactive pairing; **builder-II provides the authority**. Goose may operate only inside governed execution envelopes with explicit manifests, receipts, and verification postflights.

---

## 2. Runtime Modes & Operational Status

```text
disabled              [PROMOTED - Default]
read_only             [OPERATIONALLY_VERIFIED - READ_ONLY_RUNTIME_VERIFIED]
command_proposal      [PASSIVE_FOUNDATION - Artifact Only]
verification_execution [OPERATIONALLY_VERIFIED - BOUNDED_EXECUTION_VERIFIED]
patch_proposal        [OPERATIONALLY_VERIFIED - PASSIVE_ARTIFACT_VERIFIED]
hitl_write            [OPERATIONALLY_VERIFIED - MUTATION_WITH_ROLLBACK_VERIFIED]
```

### I. `read_only` Mode (OPERATIONALLY_VERIFIED)
The governed read-only runtime is promoted and machine-checked:
- **Command Surfaces:** `builder-goose start-readonly`, `builder-goose close-readonly`.
- **Enforcement:** Enforces zero repository mutation, captures pre/postflight git fingerprints, and records launch/close receipts.
- **Evidence:** Validated via `tests/test_goose_readonly.py`, `tests/test_goose_inspection.py`, and `tests/test_goose_runtime_harness.py`.

### II. In-Loop Governed Runtime (ADR-0009)
Goose operates with builder-II interposition via a dedicated stdio MCP server:
- **Sole Extension:** Goose runs with builder-II's governed MCP server as its primary tool interposition layer.
- **Deny-by-Default:** Mutating tool calls are denied at the gateway and recorded in the event ledger.
- **Receipts:** All tool invocations emit structured execution receipts.

### III. Unpromoted Autonomous Modes
- **Autonomous Tool Execution:** Fully autonomous, unprompted Goose tool execution remains unpromoted.
- **Unattended File Writes:** All code edits must flow through the digest-bound HITL patch lane (`builder-hitl apply-patch`).
- **Autonomous Commits/Pushes:** Commit and push operations are never automated.

---

## 3. Goose Session Manifests

Goose session manifests declare runtime parameters passively before launch:

```bash
# Mint a read-only session manifest
uv run builder-goose manifest --target generic --mode read_only \
  --task "Inspect repo structure and analyze call graph" \
  --output .builder/goose/session.json

# Validate manifest integrity
uv run builder-goose validate .builder/goose/session.json

# Launch governed read-only runtime
uv run builder-goose start-readonly --manifest .builder/goose/session.json
```

A session manifest binds target profiles, context packs, allowed read paths, and expected receipt locations. The manifest itself is passive configuration; execution begins only upon explicit operator command.

---

## 4. Summary & Verification

Goose is the approved operator pairing substrate. Operational status is verified continuously:
- Read-only sessions emit `builder_ii.goose_readonly_receipt`.
- Postflight verification verifies `preflight_git_state == postflight_git_state`.
- All mutation operations require the separate, digest-bound HITL patch application lane.

