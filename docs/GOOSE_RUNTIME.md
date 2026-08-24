# Goose runtime

Goose is builder-II's local operator runtime adapter. Builder-II represents,
constrains, binds, and enforces authority; consequential human decisions originate
with the operator. Goose does not own builder-II verification, patch approval,
model routing, or Git delivery authority.

## Runtime modes

The Goose manifest accepts exactly two modes:

```text
disabled
read_only
```

`disabled` starts no Goose process. `read_only` is the current promoted runtime
lane: both `governed read-only runtime` and `Goose readonly runtime` are
`OPERATIONALLY_VERIFIED` in the platform matrix, with
`READ_ONLY_RUNTIME_VERIFIED` assurance for the Goose lane.

Verification execution, MCP patch proposal, HITL patch application, Deep Agents,
model execution, and Git delivery are separate builder-II capabilities. They are
not additional Goose runtime modes.

## Governed read-only session

A session begins with a passive manifest and explicit operator launch:

```bash
uv run builder-goose manifest --target generic --mode read_only \
  --task "Inspect repository structure" \
  --output .builder/goose/session.json
uv run builder-goose validate .builder/goose/session.json
uv run builder-goose start-readonly .builder/goose/session.json
```

`start-readonly` validates the manifest, authority decision, runtime policy,
target-bound paths, and preflight Git state before launch. It emits a launch
receipt and session-state evidence. `builder-goose close-readonly` records the
close receipt and postflight, including the no-mutation comparison required by
the read-only contract.

The runtime may inspect admitted repository paths and Git state within its policy.
It does not gain source-write, arbitrary-shell, model-provider, patch-apply,
commit, push, PR, or hidden-memory authority. A manifest is evidence and
configuration, never approval by itself.

## In-loop interposition

ADR-0009 defines Goose's governed stdio MCP interposition seam. Inventory-admitted
services delegate to canonical builder-II implementations and emit policy,
receipt, and event evidence. The seam does not make Goose the owner of authority
and does not turn separately governed services into Goose modes.

Current capability state is derived from `builder-platform matrix`; exact command
effects and approval modes are derived from `docs/COMMAND_AUTHORITY.md`.
