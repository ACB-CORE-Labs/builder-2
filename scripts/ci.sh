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
#   * There is no advisory (non-blocking) step anywhere: every gate in CI is in this
#     script, and every gate in this script blocks. A `gitleaks` Action step used to sit
#     in ci.yml as `continue-on-error: true`; it required an org license it never had, so
#     it failed instantly on every run without scanning anything -- a permanent red mark
#     that taught readers to ignore red. Secret scanning is a real BLOCKING gate below.
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
#
# --receipt <path> -- opt-in, additive. When given, emits a `builder_ii.gate_battery_receipt`
# artifact to <path> naming exactly which gates ran, their argv/exit codes/durations, the git
# HEAD before and after, and whether the tree was clean. It is a RECORDED_ONLY receipt, not an
# independent proof -- see builder_ii/gate_battery_receipt.py's module docstring for the honest
# limit. With no --receipt, this script's behavior is unchanged from before this flag existed.

set -o errexit
set -o nounset
set -o pipefail

cd "$(dirname "$0")/.."

# gate()/skip()/the --receipt machinery live in lib/ so they're testable without running the
# real (slow) nine-gate battery -- see scripts/lib/gate_battery_receipt.sh's header comment.
source scripts/lib/gate_battery_receipt.sh
_gbr_parse_args "$@"
_gbr_init
trap _gbr_emit_receipt EXIT

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
#    -n auto: parallelize across CPU-detected worker processes (pytest-xdist).
#    -p randomly: force-load pytest-randomly (it auto-activates once installed via a
#    pytest11 entry point, so this is defensive/explicit rather than strictly required).
#    pytest-randomly shuffles test order every run and prints "Using --randomly-seed=N"
#    at the top of the run; reproduce a specific failing order with --randomly-seed=<N>.
gate "full test suite" uv run pytest -n auto -p randomly

printf '\n================================\n'
if [ ${#SKIPPED[@]} -eq 0 ]; then
  printf 'ALL BLOCKING GATES PASSED (no skips).\n'
else
  printf 'ALL BLOCKING GATES PASSED, but %d gate(s) were SKIPPED on this host:\n' "${#SKIPPED[@]}"
  for name in "${SKIPPED[@]}"; do printf '  - %s\n' "$name"; done
  printf 'CI provisions every toolchain and will not skip these.\n'
fi
printf '================================\n'
