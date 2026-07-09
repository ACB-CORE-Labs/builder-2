#!/usr/bin/env bash
# The blocking CI gate battery -- one definition, run identically by humans and CI.
#
# Why this file exists: `.github/workflows/ci.yml` used to inline every gate, so the
# only way to check a change locally was to transcribe nine commands out of the
# workflow (or out of CLAUDE.md) by hand. Two hand-transcriptions of a nine-step
# sequence is a lot of trust placed in copying. This script is now the single source
# of truth: the workflow provisions an environment and then calls this, and a
# developer runs the same thing.
#
# Scope -- what this is and is not:
#   * These are the BLOCKING gates. If this script exits 0, every blocking CI gate
#     passed on this host.
#   * `gitleaks` is deliberately NOT here. It is a GitHub Action, needs a token, and
#     is configured `continue-on-error: true` -- i.e. advisory, never blocking. It
#     therefore cannot change whether the battery is green.
#   * Environment provisioning (`uv sync`, toolchain installs) is NOT a gate and is
#     NOT done here. Run `uv sync --all-groups` first.
#
# Exit-code discipline: `set -o pipefail` plus never piping a gate into `head`/`tail`.
# Piping a command into a pager silently reports the *pager's* exit status, which is
# how a red gate can look green. Do not add `| tail` to any line below.
#
# Skips are announced, never silent: a gate that cannot run on this host prints
# [SKIP] and is listed again in the final summary. CI provisions every toolchain, so
# CI never skips -- a local green with skips is weaker than a CI green, and says so.

set -o errexit
set -o nounset
set -o pipefail

cd "$(dirname "$0")/.."

SKIPPED=()

gate() {
  printf '\n=== [GATE] %s ===\n' "$1"
  shift
  "$@"
}

skip() {
  printf '\n=== [SKIP] %s ===\n  reason: %s\n' "$1" "$2"
  SKIPPED+=("$1")
}

# 1. Rust validation accelerator must build (optional toolchain; CI always has it).
#    PyO3 otherwise resolves whatever `python3` is first on PATH. On a dev box that is
#    often a newer Python than PyO3 supports, so the gate fails for a reason that has
#    nothing to do with the change under test. Pin it to the project interpreter, which
#    is 3.12 both locally (uv venv) and in CI (setup-python + uv sync).
if command -v cargo >/dev/null 2>&1; then
  PYO3_PYTHON="$(uv run python -c 'import sys; print(sys.executable)')"
  export PYO3_PYTHON
  gate "rust validator build" cargo build --manifest-path builder_ii_validation_rs/Cargo.toml
else
  skip "rust validator build" "cargo not found on PATH"
fi

# 2. Everything must at least compile.
gate "python bytecode compile" uv run python -m compileall -q builder_ii tests

# 3. Docs may not claim capabilities the code does not back.
gate "docs truth audit" uv run builder-platform audit-docs
gate "completion truth matrix" uv run builder-platform matrix

# 4. No high-confidence vendor keys committed.
gate "high-confidence secret scan" uv run python scripts/secret_scan.py

# 5. Lint, types, security.
gate "ruff lint" uv run ruff check builder_ii tests
gate "targeted mypy" uv run mypy
gate "targeted bandit" uv run bandit -q -r builder_ii -s B101,B105,B106,B110,B112,B404,B603,B607

# 6. Full suite. `addopts` in pyproject already carries `-q`; adding another `-q`
#    turns it into `-qq` and suppresses the pass/fail summary line. Do not add one.
gate "full test suite" uv run pytest

printf '\n================================\n'
if [ ${#SKIPPED[@]} -eq 0 ]; then
  printf 'ALL BLOCKING GATES PASSED (no skips).\n'
else
  printf 'ALL BLOCKING GATES PASSED, but %d gate(s) were SKIPPED on this host:\n' "${#SKIPPED[@]}"
  for name in "${SKIPPED[@]}"; do printf '  - %s\n' "$name"; done
  printf 'CI provisions every toolchain and will not skip these.\n'
fi
printf '================================\n'
