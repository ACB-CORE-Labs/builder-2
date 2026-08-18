#!/usr/bin/env bash
# The blocking local gate battery -- the one merge-verification definition, run by humans.
#
# This script is intentionally independent of hosted CI. It is the single source of
# truth for the checks developers must run before push, PR creation, and merge.
#
# Scope -- what this is and is not:
# * These are the BLOCKING gates. If this script exits 0, every blocking CI gate
#   passed on this host.
# * There is no advisory (non-blocking) step: every gate in this script blocks. Secret
#   scanning is a real blocking gate below.
# * Environment provisioning (`uv sync`, toolchain installs) is NOT a gate and is
#   NOT done here. For the full native-orchestration lane, run
#   `uv sync --all-groups --extra deepagents` first. A lightweight
#   governance-only install may use plain `uv sync`.
#
# Exit-code discipline: `set -o pipefail` plus never piping a gate into `head`/`tail`.
# Piping a command into a pager silently reports the *pager's* exit status, which is
# how a red gate can look green. Do not add `| tail` to any line below.
#
# Skips are announced, never silent: a gate that cannot run on this host prints
# [SKIP] and is listed again in the final summary. A local green with skips is weaker
# than a fully green local run, and says so.
#
# --receipt -- opt-in, additive. When given, emits a `builder_ii.gate_battery_receipt`
# artifact to naming exactly which gates ran, their argv/exit codes/durations, the git
# HEAD before and after, and whether the tree was clean. It is a RECORDED_ONLY receipt, not an
# independent proof -- see builder_ii/governance/ledger/gate_battery_receipt.py's module docstring for the honest
# limit. With no --receipt, this script's behavior is unchanged from before this flag existed.
#
# Resource discipline: CI environment variables, when present, still cap parallelism
# for constrained environments. This does not create a hosted verification dependency;
# the authoritative result is always the local receipt from this script.

set -o errexit
set -o nounset
set -o pipefail

cd "$(dirname "$0")/.."

# Detect the constrained shared runner / any CI. Local stays full-power.
_IN_CI=0
if [ -n "${CI:-}" ] || [ -n "${GITHUB_ACTIONS:-}" ] || [ -n "${FORGEJO_ACTIONS:-}" ] || [ -n "${GITHUB_WORKFLOW:-}" ]; then
  _IN_CI=1
fi

# gate()/skip()/the --receipt machinery live in lib/ so they're testable without running the
# real (slow) nine-gate battery -- see scripts/lib/gate_battery_receipt.sh's header comment.
source scripts/lib/gate_battery_receipt.sh
_gbr_parse_args "$@"
_gbr_init
trap _gbr_emit_receipt EXIT

# 1. Rust validation accelerator must build (optional toolchain; CI always has it).
# PyO3 otherwise resolves whatever `python3` is first on PATH. On a dev box that is
# often a newer Python than PyO3 supports, so the gate fails for a reason that has
# nothing to do with the change under test. Pin it to the project interpreter, which
# is 3.12 both locally (uv venv) and in CI (setup-python + uv sync).
if command -v cargo >/dev/null 2>&1; then
  PYO3_PYTHON="$(uv run python -c 'import sys; print(sys.executable)')"
  export PYO3_PYTHON
  if [ "$_IN_CI" -eq 1 ]; then
    # Cap so the 1.2 GB runner does not OOM mid-link. Cache still hits.
    export CARGO_BUILD_JOBS=2
  fi
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

# 5b. The TUI app surface, checked for its OWN errors only.
#
# A separate invocation rather than another entry in `[tool.mypy] files`, and the reason is a
# measurement: `builder_ii/tui/app.py` type-clean in itself drags 122 errors out of 20 *other*
# modules through its import graph (verification_execution_ledger alone contributes 46). Listing it
# in `files` would therefore either fail the gate on debt that is not app.py's, or force
# `follow_imports = "silent"` globally -- which would quietly stop the gate above from reporting
# errors in anything the 14 authority modules import. Weakening an authority gate to strengthen a
# UI one is a bad trade made silently.
#
# `--follow-imports=silent` resolves imports for type information and reports only the named file,
# so this pins exactly the claim intended: app.py's own annotations do not regress. Verified by
# re-narrowing a fixed callback to `bool` -- the gate catches it. It does not pretend to check
# app.py's dependencies; that debt is real, unowned, and out of this gate's scope.
gate "tui app mypy" uv run mypy builder_ii/tui/app.py --follow-imports=silent

gate "targeted bandit" uv run bandit -q -r builder_ii -s B101,B105,B106,B110,B112,B404,B603,B607

# 6. Native orchestration prerequisite. The full suite includes the native
# Deep Agents lane, so fail early with exact remediation instead of spending
# the full test duration before collection fails. This is check-only: CI never
# installs dependencies. Plain `uv sync` remains the lightweight governance-only
# path; the declared extra is required for this full lane.
gate "deepagents readiness" uv run python -c '
import importlib.util
import sys

if importlib.util.find_spec("deepagents") is None:
    print("deepagents is unavailable in the active environment.", file=sys.stderr)
    print("Remediation: run `uv sync --all-groups --extra deepagents`, then rerun `bash scripts/ci.sh`.", file=sys.stderr)
    raise SystemExit(1)
print("deepagents import surface available")
'

# 7. Full suite. `addopts` in pyproject already carries `-q`; adding another `-q`
# turns it into `-qq` and suppresses the pass/fail summary line. Do not add one.
# -n auto: parallelize across CPU-detected worker processes (pytest-xdist).
# -p randomly: force-load pytest-randomly (it auto-activates once installed via a
#   pytest11 entry point, so this is defensive/explicit rather than strictly required).
# pytest-randomly shuffles test order every run and prints "Using --randomly-seed=N"
# at the top of the run; reproduce a specific failing order with --randomly-seed=.
if [ "$_IN_CI" -eq 1 ]; then
  _XDIST_N=2
else
  # Local hosts (like M1s) might be heavily contended by other agent workloads (e.g. Grok, VMs).
  # Pick _XDIST_N from available capacity (cores - load average) to prevent Pilot timeouts.
  _XDIST_N=$(uv run python -c '
import os, math
try:
    cores = os.cpu_count() or 4
    load1, _, _ = os.getloadavg()
    # At minimum 2 workers, up to total cores, degraded by 1-minute load average
    available = max(2, math.floor(cores - load1))
    print(min(cores, available))
except Exception:
    print("auto")
')
fi
gate "full test suite" uv run pytest -n "$_XDIST_N" -p randomly

printf '\n===\n'
if [ ${#SKIPPED[@]} -eq 0 ]; then
  printf 'ALL BLOCKING GATES PASSED (no skips).\n'
else
  printf 'ALL BLOCKING GATES PASSED, but %d gate(s) were SKIPPED on this host:\n' "${#SKIPPED[@]}"
  for name in "${SKIPPED[@]}"; do printf ' - %s\n' "$name"; done
  printf 'CI provisions every toolchain and will not skip these.\n'
fi
printf '===\n'
