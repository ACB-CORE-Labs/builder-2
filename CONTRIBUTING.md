# Contributing to builder-II

Thank you for your interest in contributing to **builder-II** — a generic governed control plane for local agent-assisted software development.

Before proposing a change, please read [`README.md`](README.md) and [`docs/MANIFESTO.md`](docs/MANIFESTO.md) to understand the governing architecture and invariants (see "The governing distinctions" in the README). Changes that touch authority boundaries, schema validation, or the completion matrix require rigorous evidence.

---

## 1. Before You Start

- **Check Capability Promotion State:** Read [`docs/CAPABILITY_PROMOTION.md`](docs/CAPABILITY_PROMOTION.md) and [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md) before implementing changes to unpromoted capabilities. An unpromoted capability is usually gated intentionally by evidence requirements.
- **Discuss Non-Trivial Changes:** For architectural shifts, new artifact kinds, or authority modifications, open an issue or proposal first to align on the technical approach.
- **Keep PRs Focused:** Small, single-purpose changes with clear tests and explicit documentation updates are reviewed and integrated much faster than broad refactors.

---

## 2. Development Setup

builder-II requires `Python >=3.12.13, <3.13` and [`uv`](https://docs.astral.sh/uv/).

```bash
# Clone the repository
git clone <repo-url>
cd builder-2

# Install dependencies and dev tools
uv sync --all-groups

# (Optional - macOS Apple Silicon) Install local MLX model backend
uv sync --extra mlx

# Initialize environment configuration
cp .env.example .env
```

---

## 3. Canonical Local Quality Gates

builder-II enforces a strict local CI gate battery. Run the local CI script before submitting commits or opening pull requests:

```bash
# Run the canonical local CI gate battery
bash scripts/ci.sh
```

You can also run individual verification steps:

```bash
# 1. Bytecode compilation
uv run python -m compileall -q builder_ii tests

# 2. Documentation truth audit (detects unbacked capability claims)
uv run builder-platform audit-docs

# 3. Static analysis & linting
uv run ruff check builder_ii tests
uv run mypy

# 4. Security checks
uv run bandit -q -r builder_ii -s B101,B105,B106,B110,B112,B404,B603,B607

# 5. Test suite execution
uv run pytest -q

# 6. Rust acceleration engine (if builder_ii_validation_rs was modified)
cargo test --manifest-path builder_ii_validation_rs/Cargo.toml
```

All gates must pass. `docs/**` and `README.md` are scanned for false-completion language by `builder-platform audit-docs`. If you modify runtime behavior or capability state, the documentation and tests must be updated in the same change.

---

## 4. Engineering Conventions

- **Artifact-First:** Features in `builder_ii/` follow the governed lifecycle: construct a typed artifact (Pydantic/dataclass with `kind`) $\rightarrow$ serialize to JSON $\rightarrow$ validate via a paired validator $\rightarrow$ consume downstream. See [`docs/ARTIFACT_INDEX.md`](docs/ARTIFACT_INDEX.md).
- **Explicit Authority Tiers:** Any command capable of changing state, calling external APIs, or executing code must register in `COMMAND_AUTHORITY_REGISTRY` (`builder_ii/governance/authority/authority_registry.py`) and enforce the required human-in-the-loop (HITL) gate. See [`docs/COMMAND_AUTHORITY.md`](docs/COMMAND_AUTHORITY.md).
- **Test Structure:** Unit tests live in `tests/test_<module>.py` mirroring `builder_ii/` 1:1. Cross-subsystem workflows and governance loops live in `tests/scenarios/`.
- **Code Style:** Formatted with `ruff` (line-length 120, standard import sorting).

---

## 5. Commit Messages & Workflow

Use conventional commits with clear, descriptive rationale:

```text
<type>: <short summary>

<detailed rationale explaining the invariant or capability preserved/tested>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`.

### Pull Request Workflow:
1. Create a feature branch from `main`.
2. Implement changes with matching unit/scenario tests and doc updates.
3. Run `bash scripts/ci.sh` locally to ensure all quality gates pass.
4. Push your branch and open a Pull Request describing the change, the invariants preserved, and the verification commands executed.

---

## 6. Reporting Issues & Security Vulnerabilities

- **Bugs & Feature Requests:** Open an issue on our tracker with detailed reproduction steps and system information.
- **Security Vulnerabilities:** Do **not** post public issues for exploitable vulnerabilities. Refer to [`SECURITY.md`](SECURITY.md) for private disclosure instructions.

---

## 7. License & Attribution

builder-II is licensed under the [MIT License](LICENSE). Contributions submitted to this repository are accepted under the terms of the MIT License (inbound = outbound).

Third-party software integrated by builder-II (including Codename Goose, Apache 2.0) is documented in [`NOTICE.md`](NOTICE.md). CodeVault (`core-labs/builder-ii-code-vault`) is a separate commercial plugin not governed by this repository's license.

All contributors must adhere to [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
