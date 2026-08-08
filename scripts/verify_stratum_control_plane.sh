#!/usr/bin/env bash
# Focused blocking verification lane for the STRATUM governed-control-plane closure.
#
# This is intentionally ADDITIVE to the full repository suite. It exists so a failure in the
# operator-control-plane work has a compact, named reproduction surface instead of being buried
# inside the complete pytest run. `scripts/ci.sh` invokes this lane as a blocking gate and later
# invokes the full suite as the repository-wide authority.
#
# Do not add `-q`: pyproject already supplies pytest quietness and a second -q suppresses useful
# pass/fail output. Do not add selective early-exit or last-failure shortcuts: a closure run must
# report the whole focused surface. The fixed random seed makes this lane replayable while the
# full battery continues to exercise randomized order separately.

set -o errexit
set -o nounset
set -o pipefail

cd "$(dirname "$0")/.."

TESTS=(
  tests/test_ci_gate_parity.py
  tests/test_governed_invocation.py
  tests/test_goose_cli.py
  tests/test_goose_cli_start_governed.py
  tests/test_goose_run_governed.py
  tests/test_mcp_governed_apply.py
  tests/test_readonly_repo_tools.py
  tests/test_ratification_dispatch.py
  tests/test_ratification_points.py
  tests/test_command_authority.py
  tests/test_stratum_governed_dispatch.py
  tests/test_stratum_tui.py
  tests/scenarios/test_governed_mcp_readonly_session.py
  tests/scenarios/test_hitl_orchestration.py
  tests/scenarios/test_in_loop_hitl_gate_to_apply.py
)

printf 'STRATUM governed control-plane focused lane\n'
printf 'Repository: %s\n' "$(pwd)"
printf 'Tests: %d files\n' "${#TESTS[@]}"
printf '%s\n' '---'

uv run pytest -p randomly --randomly-seed=0 "${TESTS[@]}"

printf '%s\n' '---'
printf 'STRATUM governed control-plane focused lane passed.\n'