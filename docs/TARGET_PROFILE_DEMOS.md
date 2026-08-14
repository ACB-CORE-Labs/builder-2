# Target profile demos

Target profile demos are copyable operator recipes for the three initial builder-II target profiles:

- `generic`
- `builder`
- `core`

Use:

```text
builder-targets demo generic
builder-targets demo builder
builder-targets demo core
```

The command renders a markdown recipe. It does not execute the listed commands.

## Generic

For ordinary software repositories. The operator supplies the repo path explicitly.

Expected artifact kinds:

- `builder_ii.target_profile`
- `builder_ii.context_pack_record`
- `builder_ii.agent_profile_record`
- `builder_ii.verification_profile`

## Builder

For builder-II self-development. The demo preserves generic-first platform boundaries.

Expected artifact kinds:

- `builder_ii.target_profile`
- `builder_ii.context_pack_record`
- `builder_ii.agent_profile_record`
- `builder_ii.verification_profile`
- `builder_ii.git_state_record`

## CORE

For the CORE target profile. CORE remains a target profile only.

Expected artifact kinds:

- `builder_ii.target_profile`
- `builder_ii.context_pack_record`
- `builder_ii.agent_profile_record`
- `builder_ii.verification_profile`
- `builder_ii.git_state_record`

## Verification

```bash
uv run pytest tests/test_target_profile_demos.py tests/test_targets_cli.py -q
uv run pytest -q
```
