# builder-II

Local AI coding platform for the CORE deterministic engine.

**Stack:** [Codename Goose](https://goose-docs.ai) (agent) + Gemma 4 via [Rapid-MLX](https://github.com/raullenchai/Rapid-MLX) (inference) on M1 16GB.

```bash
brew install block-goose-cli   # real Goose — NOT pip goose-ai
uv sync
builder setup && builder pull && builder start
```

Goose orchestrator with subagents, skills, slash commands, plan mode, and verify loop.

See [docs/manual.md](docs/manual.md).