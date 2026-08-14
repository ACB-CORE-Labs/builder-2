# Goose command proposal artifacts

`builder-goose propose-command` creates a proposed command artifact.

It does not execute the command. It does not start Goose. It does not start a shell. It does not call a model. It does not write source files. It does not mutate memory.

The artifact records:

- command string;
- target repo binding;
- reason;
- risk level;
- `requires_human_approval = true`;
- `execution_state = PROPOSED_ONLY`;
- `executed = false`;
- empty stdout/stderr/exit code;
- rollback note;
- verification refs;
- denied runtime, shell, command, model, write, memory, deepagents, commit, push, PR, web, and MCP authority.

## Commands

    builder-goose propose-command .builder/artifacts/goose-session.json \
      --command "uv run pytest -q" \
      --reason "verify current tree" \
      --risk-level low \
      --output .builder/artifacts/goose-command-proposal.json

    builder-goose validate-command-proposal .builder/artifacts/goose-command-proposal.json

## Promotion boundary

This artifact is a proposal surface only. Any future command execution capability must pass the capability promotion rule: docs, tests, command surface, failure mode, human approval boundary, output artifact, rollback path, and verification path.
