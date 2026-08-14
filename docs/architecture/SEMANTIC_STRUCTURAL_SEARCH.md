# Semantic / Structural Read-Only Search (V.1)

**Status:** validation_only / advisory RO scaffold.  
**Not** Serena rewrite authority. **Not** ast-grep apply. **Not** S3.

## CLI

```bash
uv run builder-semantic doctor
uv run builder-semantic map --repo . --target builder -o map.json
uv run builder-semantic preview --query "wrp" -o preview.json
uv run builder-semantic validate map.json
```

## Design

| Layer | Implementation |
| --- | --- |
| Doctor | Detect serena/ast-grep/rg/fd via `tool_registry`; prove `create_repo_map` works |
| Map | `create_repo_map` over the open-core repository inventory |
| Preview | Path/role substring over map hits only |

## Promotion ceiling

- `grants_authority=false`
- `mutates_target_repo=false`
- `invokes_serena_rewrite=false`
- `invokes_ast_grep_apply=false`

External tool subprocess query may later raise to `read_only_runtime_candidate` under a separate eight-gate package.

## Reuse

- `builder_ii/core/repo_map.py`
- `builder_ii/core/tool_registry.py`

Do **not** place under `builder-wrp` (routing plane).
