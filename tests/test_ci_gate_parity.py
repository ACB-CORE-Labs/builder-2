"""Pin the local gate battery as the repository's only merge-verification definition."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CI_SCRIPT = REPO_ROOT / "scripts" / "ci.sh"
SECRET_SCAN = REPO_ROOT / "scripts" / "secret_scan.py"
GATE_BATTERY_LIB = REPO_ROOT / "scripts" / "lib" / "gate_battery_receipt.sh"
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

REQUIRED_GATES: tuple[str, ...] = (
    "cargo build --manifest-path builder_ii_validation_rs/Cargo.toml",
    "compileall -q builder_ii tests",
    "builder-platform audit-docs",
    "builder-platform matrix",
    "scripts/secret_scan.py",
    "ruff check builder_ii tests",
    "uv run mypy",
    "uv run mypy builder_ii/tui/app.py --follow-imports=silent",
    "bandit -q -r builder_ii -s B101,B105,B106,B110,B112,B404,B603,B607",
    "uv run pytest",
)


def test_local_gate_surfaces_exist_and_hosted_workflows_are_absent() -> None:
    assert CI_SCRIPT.is_file()
    assert SECRET_SCAN.is_file()
    assert GATE_BATTERY_LIB.is_file()
    assert not list(WORKFLOW_DIR.glob("*.y*ml")), "verification must remain local-only"


def test_gate_battery_sources_its_receipt_library() -> None:
    script = CI_SCRIPT.read_text(encoding="utf-8")
    assert "scripts/lib/gate_battery_receipt.sh" in script


def test_gate_battery_contains_every_blocking_gate() -> None:
    script = CI_SCRIPT.read_text(encoding="utf-8")
    for gate in REQUIRED_GATES:
        assert gate in script, f"scripts/ci.sh is missing the blocking gate: {gate!r}"


def test_gate_battery_never_pipes_a_gate_into_a_pager() -> None:
    for path in (CI_SCRIPT, GATE_BATTERY_LIB):
        script = path.read_text(encoding="utf-8")
        for line in script.splitlines():
            if line.strip().startswith("#"):
                continue
            assert "| tail" not in line and "| head" not in line


def test_gate_battery_does_not_double_quiet_pytest() -> None:
    assert "uv run pytest -q" not in CI_SCRIPT.read_text(encoding="utf-8")


def test_gate_battery_sets_strict_shell_flags() -> None:
    script = CI_SCRIPT.read_text(encoding="utf-8")
    for flag in ("set -o errexit", "set -o nounset", "set -o pipefail"):
        assert flag in script
    lib = GATE_BATTERY_LIB.read_text(encoding="utf-8")
    for flag in ("-o errexit", "-o nounset", "-o pipefail"):
        assert flag in lib


def test_ci_parallelism_cap_is_only_for_constrained_environments() -> None:
    script = CI_SCRIPT.read_text(encoding="utf-8")
    assert "_IN_CI=0" in script and "_IN_CI=1" in script
    assert "CARGO_BUILD_JOBS=2" in script
    assignments = re.findall(r"^\s*_XDIST_N=(\S*)", script, re.MULTILINE)
    assert "2" in assignments
    assert [value for value in assignments if value != "2"]
    assert "uv run pytest" in script
