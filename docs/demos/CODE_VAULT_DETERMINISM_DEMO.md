# CodeVault Determinism Demo — Recording Walkthrough

This walkthrough produces a **recordable, read-only** evidence bundle that proves CodeVault layout identity is deterministic, replay-stable, and non-authoritative. It mirrors the CORE founder demo pattern but never mutates the scanned repository.

## What you are proving on camera

1. **Replay stability** — the same repo map yields byte-identical canonical frame JSON and an identical frame digest.
2. **Sibling invariance** — adding siblings does not move an existing anchor symbol's `center_xyz`.
3. **Content vs layout separation** — editing content changes `content_digest` but not coordinates.
4. **Artifact-only posture** — all outputs are JSON artifacts with `artifact_is_authority: false` and governance caps `DISABLED`.
5. **Inspectable via TUI** — `builder code-vault` read-only commands render the bundle without granting runtime authority.

## Prerequisites

- builder-II checkout with CodeVault integrated (PR #210+)
- `uv` environment ready (`uv sync`)
- Terminal suitable for recording (TTY colors optional; output remains parseable when piped)

## One-command demo generation

From the repository you want to scan (builder-II itself is a strong demo target):

```bash
cd /path/to/builder-II

uv run builder-code-vault demo \
  --repo-path . \
  --output-dir .builder/demos/code-vault-determinism \
  --target builder \
  --force
```

Expected artifacts under `.builder/demos/code-vault-determinism/`:

| File | Role |
| --- | --- |
| `repo-map.json` | Bounded read-only scan input |
| `hierarchical-frame.json` | Content-addressed layout frame |
| `geometric-linter-report.json` | Hypothesis-only findings |
| `recall-report.json` | Advisory top-k recall report |
| `context-projection.json` | Bounded metadata projection |
| `chain-verification-report.json` | Cryptographic linkage audit |
| `artifact-index.json` | Inventory of emitted artifacts |
| `code-vault-determinism-report.json` | Structured determinism proof report |
| `CODE_VAULT_DEMO_EVIDENCE.md` | Human-readable recording companion |

Validate the report:

```bash
uv run builder-code-vault validate-demo \
  .builder/demos/code-vault-determinism/code-vault-determinism-report.json
```

## TUI inspection (read-only monitor surface)

Point the TUI at the demo output directory via `BUILDER_DIR`:

```bash
export BUILDER_DIR=.builder/demos/code-vault-determinism

uv run builder code-vault status
uv run builder code-vault determinism
uv run builder code-vault frame
uv run builder code-vault recall
uv run builder code-vault lint
uv run builder code-vault context
uv run builder code-vault governance
uv run builder code-vault validate
```

### Suggested recording beats

1. **Generate** — run `builder-code-vault demo` and show `CODE_VAULT_DEMO_EVIDENCE.md`.
2. **Digest pin** — quote `frame_digest` from `code-vault-determinism-report.json`.
3. **Replay proof** — show `replay_identical_frame` proof row (`passed: true`).
4. **Sibling proof** — show `sibling_addition_preserves_anchor` with unchanged `anchor_center_xyz`.
5. **Content proof** — show `content_edit_changes_digest_not_center`.
6. **TUI pass** — run `builder code-vault status` and `builder code-vault determinism`.
7. **Authority boundary** — run `builder code-vault governance` and confirm all caps `DISABLED`, `artifact_is_authority: false`.
8. **Chain** — open `chain-verification-report.json` and confirm `"valid": true`.

## Determinism checks you can re-run manually

```bash
# Frame digest from CLI
uv run builder-code-vault digest .builder/demos/code-vault-determinism/hierarchical-frame.json

# Re-validate every artifact kind
uv run builder-code-vault validate-frame .builder/demos/code-vault-determinism/hierarchical-frame.json
uv run builder-code-vault validate-lint .builder/demos/code-vault-determinism/geometric-linter-report.json
uv run builder-code-vault validate-recall .builder/demos/code-vault-determinism/recall-report.json
uv run builder-code-vault validate-context .builder/demos/code-vault-determinism/context-projection.json
```

## Eval / regression hook

```bash
uv run pytest tests/test_code_vault_demo_loop.py tests/test_code_vault_tui.py -q
```

## Governance statement (on-camera script)

> CodeVault is a builder-II platform capability, not CORE runtime authority. This demo emits artifacts only. No shell execution, model execution, Goose, deepagents, MCP, patch application, or target-repo writes occur. Rollback is `rm -rf .builder/demos/code-vault-determinism`.

## Related docs

- [`docs/CODE_VAULT.md`](../CODE_VAULT.md) — operator overview
- [`docs/CODE_VAULT_STAGED_ACCEPTANCE.md`](../CODE_VAULT_STAGED_ACCEPTANCE.md) — staged acceptance ledger
- [`docs/demos/CORE_READONLY_FOUNDER_DEMO.md`](CORE_READONLY_FOUNDER_DEMO.md) — parallel passive demo pattern