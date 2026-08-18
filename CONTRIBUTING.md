# Contributing to builder-II

> **Status:** builder-II is now open source and accepting external contributions. See the sections
> below for setup, quality gates, and the pull request process.

Thank you for your interest in builder-II — a generic governed control plane for local
agent-assisted software development. See [`README.md`](README.md) and
[`docs/MANIFESTO.md`](docs/MANIFESTO.md) for what the project is and why it's built the way it is
before proposing a change; a lot of the design exists to preserve specific invariants (see "The
governing distinctions" in the README), and changes that touch those invariants get more scrutiny
than ordinary bug fixes.

## Before you start

- Read [`docs/README.md`](docs/README.md) for the full documentation index, and
  [`docs/PLATFORM_COMPLETION_AUDIT.md`](docs/PLATFORM_COMPLETION_AUDIT.md) /
  [`docs/CAPABILITY_PROMOTION.md`](docs/CAPABILITY_PROMOTION.md)
  for what's currently promoted vs. speculative. A capability that isn't promoted yet is usually that
  way on purpose — check before assuming it's just unfinished.
- For anything non-trivial, open an issue or discussion first (see "Reporting issues" below) to
  confirm the approach before investing in an implementation.
- Small, focused changes are much easier to review than large ones. Prefer several small pull
  requests over one large one when the work naturally splits.

## Development setup

```bash
uv sync --all-groups --extra deepagents  # full development/native orchestration lane
uv sync --extra mlx                 # add the local Apple Silicon model backend (optional, Mac-first)
cp .env.example .env
```

Requires Python 3.12 (pinned via `.python-version` / `uv.lock`) and [`uv`](https://docs.astral.sh/uv/).
See the "Install" section of [`README.md`](README.md) for the full setup, including Goose and model
downloads if you need to exercise runtime-adjacent code paths.

The default model backend is **Ollama** — the recommended path for Linux, CI, and open-source
contributors. Apple Silicon users can opt into the local MLX lane via `uv sync --extra mlx` and
setting `BUILDER_MODEL_BACKEND=mlx-lm` in `.env`. See `.env.example` for the full backend menu
and recommended defaults.

## Quality gates

Before opening a pull request, run the same checks CI runs:

```bash
uv run python -m compileall -q builder_ii tests
uv run builder-platform audit-docs   # fails if docs claim capabilities the code doesn't back
uv run ruff check builder_ii tests
uv run mypy                          # targeted: authority-sensitive modules only, see pyproject.toml
uv run bandit -q -r builder_ii -s B101,B105,B106,B110,B112,B404,B603,B607
uv run pytest -q
cargo build --manifest-path builder_ii_validation_rs/Cargo.toml   # if you touched the Rust validator
```

All of these must pass. `docs/**` and `README.md` are scanned for false-completion language by
`audit-docs` — if you change what a command does (especially promoting a capability from
speculative/planned to operational), the corresponding doc must be updated in the same change, and
any promotion claim must be backed by real evidence (tests, a closure audit) rather than asserted.

## Code conventions

- **Artifact-first.** Most features in `builder_ii/` follow the same shape: build a governed artifact
  (a Pydantic/dataclass model with a `kind` field) → write it as JSON → a paired `validate-*` command
  re-checks it → downstream commands consume it as input. New features should follow this shape rather
  than inventing a new one. See [`docs/ARTIFACT_INDEX.md`](docs/ARTIFACT_INDEX.md).
- **Explicit authority.** A command that can change state (write files, execute code, call a model)
  must go through the command-authority tier registry and, where authority changes, an explicit
  human-in-the-loop approval boundary. See [`docs/COMMAND_AUTHORITY.md`](docs/COMMAND_AUTHORITY.md).
- **Tests live at `tests/test_<module>.py`**, mirroring `builder_ii/` roughly 1:1, plus
  `tests/scenarios/` for flows spanning multiple artifact stages. Add a scenario test when a change
  spans more than one artifact stage.
- Line length 120 (see `[tool.ruff]` in `pyproject.toml`); `ruff` handles import ordering.

## Commit messages

```
<type>: <description>

<optional body>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`. Keep the summary line
imperative and under ~70 characters; use the body to explain *why*, not just *what*.

## Opening a pull request

1. Branch from `main`.
2. Make your change, keeping it focused, and ensure the quality gates above pass.
3. Push your branch and open a pull request against `main` on [GitHub](https://github.com/AssetOverflow/builder-2), describing what changed and why, plus a test plan.
4. Address review feedback. CRITICAL/HIGH-severity findings must be resolved before merge.

## Reporting issues

Open an issue on the [GitHub issue tracker](https://github.com/ACB-CORE-Labs/builder-2/issues).

For security vulnerabilities specifically, see [`SECURITY.md`](SECURITY.md) — do not open a public
issue for those.

## License

builder-II is licensed under the [MIT License](LICENSE). The current copyright holder
(`Joshua Shay`) is provisional — the intent is to reassign copyright to a formal entity (CORE (AI))
once one exists; this does not change the license terms. Contributions made once the project
accepts them will be under this same license (standard inbound = outbound).

CodeVault (`builder-ii-code-vault`) is a separate, commercially licensed plugin repository and is
not covered by this license — see [`README.md`](README.md#codevault-paid-commercial-plugin-upgrade)
for the boundary. Third-party software builder-II integrates with (notably Codename Goose, Apache
2.0, invoked as a separately installed binary rather than bundled) is documented in
[`NOTICE.md`](NOTICE.md).

## Code of Conduct

This project follows [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
