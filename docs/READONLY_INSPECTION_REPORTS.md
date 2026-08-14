# Read-only inspection reports

`builder_ii.readonly_inspection_report` is the first bounded runtime-candidate surface after the no-runtime foundation.

It records metadata and SHA-256 digests for explicit operator-supplied file paths. It does not discover files, expand globs, traverse directories, execute commands, call models, or store file contents.

## Scope

- explicit paths only
- optional root boundary
- file existence and type metadata
- byte size
- SHA-256 digest
- output artifact written only when the operator supplies `--output`

## CLI

```bash
builder-readonly report --target builder --purpose review --path README.md --output .builder/artifacts/readonly-inspection.json
builder-readonly validate .builder/artifacts/readonly-inspection.json
```

## Verification

```bash
uv run pytest tests/test_readonly_inspection_reports.py -q
uv run pytest -q
git diff --check
```
