# Stacked PR note: read-only inspection boundary

This branch is intentionally stacked on `feat/goose-readonly-runtime-candidate`.

Base PR: Goose read-only runtime candidate audits.

This stacked branch adds the next thin layer: bounded read-only repository file inspection.

It should be retargeted to `main` only after the base branch merges, or merged after the base PR lands.

## Added boundary

`builder-goose inspect-readonly` may read only explicit operator-requested relative paths inside the target repository.

It records metadata only:

- relative path;
- byte count;
- SHA-256 digest;
- line count;
- `content_recorded: false`.

It does not record file contents.

## Still denied

- Goose process/runtime start;
- arbitrary repository file reads;
- path traversal;
- `.git` reads;
- directory reads;
- oversized file reads;
- git status inspection;
- linked target artifact reads;
- command execution;
- shell execution;
- model calls;
- deepagents construction;
- source writes;
- memory mutation;
- commits/pushes;
- pull request creation;
- source collection;
- web search;
- MCP execution.
