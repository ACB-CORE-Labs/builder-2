# Profile Resolution

Profile resolution defines a deterministic, fail-closed mechanism for selecting and validating passive execution-environment parameters (targets, context packs, prompt profiles, agent profiles, and verification profiles) in the builder-II platform.

This layer replaces scattered, ad-hoc lookups and default mapping logic across generic, builder, and core repositories.

## Concepts

### Targets
A **target** represents the repository workspace that builder-II is operating within or against. There are three canonical targets:
- `generic`: Any standard repository with no builder-II doctrine.
- `builder`: The builder-II self-development workspace.
- `core`: The `AssetOverflow/core` mathematical engine repository.

### Profile Types
- **Agent Profiles**: Specify the agent's purpose, authority, tools allowed/forbidden, and output contract (e.g., `repo_mapper`, `context_planner`, `code_reviewer`).
- **Prompt Profiles**: Contain the initialization prompts (e.g., `generic_default`, `builder_default`, `core_default`).
- **Verification Profiles**: Detail the target-scoped verification commands and expected evidence (e.g., `generic_basic`, `builder_fast`, `core_smoke`).
- **Context Defaults**: The list of files/directories loaded by default for context gathering.

## Default Resolution Matrix

When default parameters are not specified, the target resolves to the following defaults:

| Target | Agent Profile | Prompt Profile | Verification Profile | Default Context Folders |
| --- | --- | --- | --- | --- |
| `generic` | `repo_mapper` | `generic_default` | `generic_basic` | `README.md`, `pyproject.toml`, `package.json`, `src`, `tests`, `docs` |
| `builder` | `context_planner` | `builder_default` | `builder_fast` | `README.md`, `docs/ROADMAP.md`, `docs/TOOLING.md`, `builder_ii`, `recipes`, `tests` |
| `core` | `code_reviewer` | `core_default` | `core_smoke` | `README.md`, `AGENTS.md`, `GROK.md`, `CLAUDE.md`, `docs`, `tests` |

## Design Constraints

### Fail-Closed Behavior
- **Unknown Profiles**: Resolving any unknown profile name (target, agent, prompt, verification) raises `UnknownProfileError`.
- **Incompatible Profiles**: Combining a profile with an incompatible target raises `ValidationError`. For example, trying to resolve target `generic` with verification profile `builder_fast` raises `ValidationError`.
- **Missing Directories**: If the resolved repository path does not exist, `MissingFileError` (a subclass of `FileNotFoundError` and `ProfileResolutionError`) is raised.

### Serialization and Determinism
The resolution output is wrapped in a `ResolutionResult` object. The `to_dict()` output contains only serializable types and is fully deterministic, making it suitable for JSON artifact generation (such as session plans).

### Scope Boundaries
- **No CORE Workbench Coupling**: No CORE Workbench, UI, or UX language exists in the resolution layer.
- **CORE as Target Only**: CORE is treated strictly as a target workspace (`core`), not as the global builder-II identity. The platform remains generic-first.
