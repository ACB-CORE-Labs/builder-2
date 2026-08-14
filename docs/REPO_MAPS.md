# Bounded Repository Maps

The repository map capability provides a bounded, read-only intelligence layer over a target project repository. It allows human operators and governed tools to understand repository structure and file roles without performing any execution or writing to the target repository.

builder-II is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench, not CORE UI/UX, and not a second CORE runtime. CORE is only a target profile.

## Artifact Specification

- **Kind**: `builder_ii.repo_map`
- **Schema Version**: `1`

The repository map artifact captures:
- **`repo_path`**: Absolute path to the resolved target repository root.
- **`target_name`**: Target profile (`generic`, `builder`, or `core`).
- **`scan_state`**: Strictly `READ_ONLY`.
- **`file_count`**: Number of files selected in the map.
- **`truncated`**: Boolean indicating whether candidate files exceeded size or count boundaries.
- **`ignored_directories`**: Sorted list of noisy directories ignored during scanning.
- **`files`**: Sorted list of selected file entries containing `path`, `suffix`, `size_bytes`, `sha256`, and `role`.
- **`summary_counts`**: Aggregate counts by role (`source_files`, `test_files`, `docs_files`, `config_files`, `artifact_files`, `unknown_files`).

## Role Classification & Filtering

During scanning, standard heavy or noisy directories are explicitly filtered out:
`.git`, `.builder`, `.venv`, `venv`, `node_modules`, `__pycache__`, `.pytest_cache`, `dist`, `build`, `.mypy_cache`, and `.ruff_cache`.

Each discovered file is classified into a stable role:
- **`docs`**: Documentation files (`README.md`, `docs/`, `.md`, etc.).
- **`config`**: Configuration files (`pyproject.toml`, `package.json`, `.toml`, `.yaml`, etc.).
- **`test`**: Test suites (`tests/`, `test_*.py`, `*.spec.ts`, etc.).
- **`source`**: Application or library source code (`.py`, `.ts`, `.go`, `.rs`, etc.).
- **`artifact`**: Generated JSON reports and prepare packages under governed directories.
- **`unknown`**: Any unclassified binary or raw assets.

## CLI Command

You can generate a repository map independently via the CLI:

```bash
builder-session repo-map generic \
  --repo-path . \
  --output .builder/artifacts/repo-map.json
```

## Governance & Runtime Boundary

The repository map strictly preserves the platform boundary:
- **No shell execution**: Scanning uses pure Python filesystem traversal (`os.walk` and `Path`).
- **No subprocess authority**: No external tools or Git binaries are invoked.
- **No target-repo writes**: The repository working tree is inspected in a read-only manner.
- **No model execution**: Role classification is deterministic.
- **No Goose / deepagents activation**: No agents are triggered or delegated to.
- **Passive artifact**: The generated JSON artifact is informative context only and never grants runtime execution authority.
