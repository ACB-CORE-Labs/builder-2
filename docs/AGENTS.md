# Agent profiles

builder-II agent profiles are generic prompt and authority contracts. They do not call models or edit files by themselves.

Initial profiles:

- `repo_mapper`
- `context_planner`
- `code_reviewer`
- `patch_planner`
- `verification_planner`
- `handoff_scribe`

Commands:

```bash
builder-agent profiles
builder-agent profiles --target builder
builder-agent show patch_planner
builder-agent render patch_planner --target generic
builder-agent render patch_planner --target builder
builder-agent render verification_planner --target core
builder-agent validate
```

Each profile declares purpose, authority, compatible targets, required context, allowed tools, forbidden tools, HITL requirements, and output contract.

This layer only renders and inspects profiles. It does not run Goose, invoke deepagents, edit files, execute shell commands, or write notes.

The base profiles are generic and compatible with `generic`, `builder`, and `core`. CORE-specific profiles can be added later only as explicit extensions.
