# Offline lane checks

Offline lane checks verify that the builder-II role, lane-guide, and capability-gate stack is internally consistent.

They do not call local models, start Goose, inspect the filesystem, edit files, or validate model quality. They are deterministic manifest checks.

## What is checked

For each persona and its lane guide, the check verifies:

- the role declares the guide;
- the role model alias matches the guide model alias;
- the prompt template renders supplied context;
- the role output contract is visible in the rendered prompt;
- direct ask is allowed;
- local Goose tool execution remains unsupported;
- heavy model routing remains forbidden;
- file editing is either operator-only or forbidden as expected;
- runtime switching is either operator-only or forbidden as expected.

## Boundary

Passing offline lane checks does not mean a local model is correct, that Goose tools are safe, or that edits can be accepted. It only means the operator manifests agree with each other.

Live behavior still requires the relevant commands, such as:

```bash
uv run pytest -q
uv run builder-runtime reset
builder ask --model qwen-coder --prompt "..."
```
