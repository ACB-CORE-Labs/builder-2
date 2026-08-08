"""Pin: the CI workflow and the local gate battery are ONE definition, not two copies.

The gate battery is `scripts/ci.sh`. `.github/workflows/ci.yml` must provision an
environment and then call it -- never inline a gate of its own. Without this pin the
two drift silently, and "I ran the gates locally" stops meaning "I ran what CI runs".

This is the same shape the rest of the codebase uses: one definition, one paired
validator. Here the validator is a test rather than a `validate-*` command, because
the artifact is a shell script rather than a `kind`-tagged JSON document.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
CI_SCRIPT = REPO_ROOT / "scripts" / "ci.sh"
SECRET_SCAN = REPO_ROOT / "scripts" / "secret_scan.py"
STRATUM_CLOSURE_SCRIPT = REPO_ROOT / "scripts" / "verify_stratum_control_plane.sh"
# gate()/skip() -- the functions the no-pager and strict-flag pins below exist to protect --
# live here, not in CI_SCRIPT. Both files are covered by both pins for exactly that reason.
GATE_BATTERY_LIB = REPO_ROOT / "scripts" / "lib" / "gate_battery_receipt.sh"

# Every blocking gate, as it must appear in scripts/ci.sh.
REQUIRED_GATES: tuple[str, ...] = (
    "cargo build --manifest-path builder_ii_validation_rs/Cargo.toml",
    "compileall -q builder_ii tests",
    "builder-platform audit-docs",
    "builder-platform matrix",
    "scripts/secret_scan.py",
    "ruff check builder_ii tests",
    "uv run mypy",
    # Pinned separately from the bare `uv run mypy` above: this is a second invocation, and a
    # substring match on "uv run mypy" alone would keep passing if it were deleted.
    "uv run mypy builder_ii/tui/app.py --follow-imports=silent",
    "bandit -q -r builder_ii -s B101,B105,B106,B110,B112,B404,B603,B607",
    "bash scripts/verify_stratum_control_plane.sh",
    "uv run pytest",
)

# Substrings that must NOT appear in a `run:` line of the workflow: they would mean a
# gate was inlined there instead of living in scripts/ci.sh.
FORBIDDEN_IN_WORKFLOW_RUNS: tuple[str, ...] = (
    "uv run pytest",
    "uv run ruff",
    "uv run mypy",
    "uv run bandit",
    "compileall",
    "builder-platform",
    "cargo build",
)


def _workflow_run_lines() -> list[str]:
    """Lines of ci.yml that are shell, not comments/keys -- i.e. `run:` bodies."""
    lines: list[str] = []
    in_run_block = False
    for raw in CI_WORKFLOW.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if stripped.startswith("#"):
            continue
        if stripped.startswith("run:"):
            in_run_block = True
            lines.append(stripped.removeprefix("run:").strip())
            continue
        if in_run_block:
            # A new YAML key at list-item level ends the run block.
            if stripped.startswith("- ") or (stripped.endswith(":") and " " not in stripped):
                in_run_block = False
                continue
            lines.append(stripped)
    return [line for line in lines if line and line != "|"]


def test_ci_script_and_secret_scan_exist() -> None:
    assert CI_SCRIPT.is_file(), "scripts/ci.sh is the single source of truth for the gate battery"
    assert SECRET_SCAN.is_file(), "the secret scan must be a file, not an inline workflow heredoc"
    assert STRATUM_CLOSURE_SCRIPT.is_file(), (
        "the STRATUM control-plane closure lane must remain a repository script, not an inline CI fragment"
    )


def test_gate_battery_lib_exists_and_is_sourced_by_the_script() -> None:
    assert GATE_BATTERY_LIB.is_file(), "gate()/skip() live in scripts/lib/gate_battery_receipt.sh"
    script = CI_SCRIPT.read_text(encoding="utf-8")
    assert "scripts/lib/gate_battery_receipt.sh" in script, "scripts/ci.sh must source the shared gate-running lib"


def test_workflow_delegates_to_the_gate_battery() -> None:
    body = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "scripts/ci.sh" in body, "ci.yml must call scripts/ci.sh"


def test_workflow_inlines_no_gate() -> None:
    run_lines = _workflow_run_lines()
    assert run_lines, "expected at least one `run:` line in ci.yml"
    for line in run_lines:
        for forbidden in FORBIDDEN_IN_WORKFLOW_RUNS:
            assert forbidden not in line, (
                f"ci.yml inlines the gate {forbidden!r} in {line!r}; "
                "add it to scripts/ci.sh instead so local runs match CI"
            )


def test_workflow_requests_a_receipt_on_a_gitignored_path() -> None:
    """The workflow's battery step must ask for a receipt, and the path must be ignored.

    The path matters more than the flag: `_gbr_emit_receipt` computes `working_tree_clean`
    from `git status --porcelain`, which sees an untracked receipt left by a PREVIOUS run.
    A repo-root receipt makes the very next run report a dirty tree -- the field that
    exists to prove "these gates ran against exactly this commit" poisoned by the mechanism
    recording it. `.builder/` is gitignored, so `git status` never sees the receipt.
    tests/test_gate_battery_receipt_shell.py proves both directions of that property by
    running a battery twice; this pin keeps the workflow on the safe path.
    """
    run_lines = _workflow_run_lines()
    battery_lines = [line for line in run_lines if "scripts/ci.sh" in line]
    assert battery_lines, "ci.yml must call scripts/ci.sh"
    for line in battery_lines:
        assert "--receipt .builder/artifacts/gate-battery-receipt.json" in line, (
            f"the battery step must request the receipt at the gitignored .builder/ path: {line!r}"
        )
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".builder/" in gitignore, ".builder/ must stay gitignored or the receipt poisons working_tree_clean"


def test_workflow_uploads_the_receipt_even_when_the_battery_is_red() -> None:
    """A default upload step is skipped when a prior step fails, and the receipt that
    matters most is the one from a red run -- the upload must be `if: always()`."""
    body = CI_WORKFLOW.read_text(encoding="utf-8")
    upload_blocks = [block for block in body.split("- name:") if "upload-artifact" in block]
    assert upload_blocks, "ci.yml must upload the gate battery receipt"
    for block in upload_blocks:
        assert "if: always()" in block, "the receipt upload must run even when the battery failed"
        assert ".builder/artifacts/gate-battery-receipt.json" in block


def test_no_step_may_continue_on_error() -> None:
    """No advisory steps: every step in ci.yml must be able to fail the job.

    `continue-on-error` on the battery or the upload would let a red battery -- or exit 3, a
    requested-but-unwritten receipt -- read green. The one step that ever carried it was a
    `gitleaks` Action, which required an org license it never had: it failed instantly on every
    run, scanned nothing, and stamped a permanent red mark on CI that taught readers to ignore
    red. A check that can only fail is worse than no check. It is gone, and secret scanning is a
    real BLOCKING gate in `scripts/ci.sh`, so the invariant is now the stronger one: **zero**
    advisory steps.
    """
    body = CI_WORKFLOW.read_text(encoding="utf-8")
    live_lines = [line for line in body.splitlines() if not line.strip().startswith("#")]
    hits = [line for line in live_lines if "continue-on-error" in line]
    assert hits == [], f"no continue-on-error is allowed in ci.yml; found: {hits}"
    assert "gitleaks" not in body.lower(), "the licence-gated gitleaks Action must not come back"


def test_gate_battery_contains_every_blocking_gate() -> None:
    script = CI_SCRIPT.read_text(encoding="utf-8")
    for gate in REQUIRED_GATES:
        assert gate in script, f"scripts/ci.sh is missing the blocking gate: {gate!r}"


def test_stratum_closure_lane_is_strict_reproducible_and_non_selective() -> None:
    """The focused lane may improve diagnosis, never weaken closure evidence.

    It is deliberately duplicated inside the later full-suite gate. A developer can run it alone
    for a fast reproduction, but CI treats it as a normal blocking command and then still runs the
    entire suite. Fixed ordering here is for reproducibility; randomized repository-wide ordering
    remains the separate full-suite obligation.
    """
    script = STRATUM_CLOSURE_SCRIPT.read_text(encoding="utf-8")
    for flag in ("set -o errexit", "set -o nounset", "set -o pipefail"):
        assert flag in script, f"focused STRATUM closure lane must {flag}"

    assert "uv run pytest -q" not in script, "pyproject already supplies -q; do not double-quiet the focused lane"
    assert "--randomly-seed=0" in script, "focused closure order must be reproducible"
    for weakening in ("|| true", " -x ", "--lf", "--failed-first", "continue-on-error"):
        assert weakening not in script, f"focused closure lane contains a selective/advisory escape: {weakening!r}"

    required_surfaces = (
        "tests/test_goose_cli_start_governed.py",
        "tests/test_goose_run_governed.py",
        "tests/test_mcp_governed_apply.py",
        "tests/test_readonly_repo_tools.py",
        "tests/test_ratification_dispatch.py",
        "tests/test_stratum_governed_dispatch.py",
        "tests/scenarios/test_governed_mcp_readonly_session.py",
        "tests/scenarios/test_in_loop_hitl_gate_to_apply.py",
    )
    for surface in required_surfaces:
        assert surface in script, f"STRATUM focused lane lost the load-bearing surface {surface!r}"


def test_gate_battery_never_pipes_a_gate_into_a_pager() -> None:
    """Piping a gate into head/tail reports the PAGER's exit status, so a red gate reads green.

    Covers scripts/ci.sh AND scripts/lib/gate_battery_receipt.sh: gate()'s `"$@"` invocation --
    the only place a gate actually runs -- lives in the lib, not in ci.sh, so a pin scoped to
    ci.sh alone would no longer be watching the thing it exists to protect.
    """
    for path in (CI_SCRIPT, GATE_BATTERY_LIB):
        script = path.read_text(encoding="utf-8")
        for line in script.splitlines():
            if line.strip().startswith("#"):
                continue
            assert "| tail" not in line and "| head" not in line, (
                f"{path.relative_to(REPO_ROOT)} pipes a gate into a pager, masking its exit code: {line!r}"
            )


def test_gate_battery_does_not_double_quiet_pytest() -> None:
    """pyproject's addopts already carries -q; a second -q suppresses the pass/fail summary."""
    script = CI_SCRIPT.read_text(encoding="utf-8")
    assert "uv run pytest -q" not in script, "pyproject addopts already sets -q; `-qq` hides the summary line"


def test_gate_battery_sets_strict_shell_flags() -> None:
    script = CI_SCRIPT.read_text(encoding="utf-8")
    for flag in ("set -o errexit", "set -o nounset", "set -o pipefail"):
        assert flag in script, f"scripts/ci.sh must {flag} so a failing gate aborts the battery"

    # The lib doesn't set these itself (it's sourced, not run) -- it must instead REFUSE to
    # load when the caller hasn't, rather than merely documenting the requirement in a comment.
    # A prior review round mutation-tested the pre-fix lib (no enforcement, comment only): a
    # gate piped into `tail` still passed all seven parity pins, because none of them read the
    # file the mutation was in. Not a live defect -- ci.sh's own `pipefail` already stops that
    # specific mutation from turning a red gate green -- but a guarantee that had silently
    # stopped covering the only place a gate now runs.
    lib = GATE_BATTERY_LIB.read_text(encoding="utf-8")
    for flag in ("-o errexit", "-o nounset", "-o pipefail"):
        assert flag in lib, (
            f"scripts/lib/gate_battery_receipt.sh must assert {flag} at source time and refuse "
            "otherwise, not merely document the requirement in a comment"
        )


# --- The battery is unconditional: caching may make CI cheap, never selective -----------------
#
# The measured shape of a CI run here is that the GATES ARE FREE and the PROVISIONING IS NOT:
# the complete blocking battery is cheap relative to the shared-runner provisioning cost, and a
# cold build of the Rust validator is similarly small compared with assembling the environment.
# So the honest optimisation is caching/provisioning efficiency -- and the dishonest one, which
# looks equally attractive and is the natural next idea, is to stop running some gates on some
# commits ("full suite only after a wave").
#
# That would buy back seconds and cost the property the battery exists for. These pins make the
# selective version impossible to introduce QUIETLY: the battery step must be unconditional, and
# the workflow must fire on every pull request and every push to main with no path filter.


def _workflow_lines() -> list[str]:
    return [line for line in CI_WORKFLOW.read_text(encoding="utf-8").splitlines() if not line.strip().startswith("#")]


def test_the_gate_battery_step_is_unconditional() -> None:
    """No `if:` may guard the battery. A conditionally-skipped gate is not a gate."""
    lines = _workflow_lines()
    battery_index = next(i for i, line in enumerate(lines) if "scripts/ci.sh" in line and "run:" in line)
    # Walk back to the step's `- name:` and scan the step body for a condition.
    start = battery_index
    while start > 0 and not lines[start].strip().startswith("- "):
        start -= 1
    step = lines[start : battery_index + 1]
    assert not any(line.strip().startswith("if:") for line in step), (
        "the gate battery step must not be conditional -- every gate runs on every commit"
    )


def test_the_workflow_has_no_path_filter_that_could_skip_a_commit() -> None:
    """`paths:`/`paths-ignore:` would let a commit land with no battery at all -- the
    'docs-only change, skip CI' shortcut that eventually ships a red tree."""
    body = "\n".join(_workflow_lines())
    for skipper in ("paths:", "paths-ignore:", "branches-ignore:"):
        assert skipper not in body, (
            f"ci.yml must not use `{skipper}` -- it would let commits bypass the battery entirely"
        )


def test_the_workflow_still_fires_on_every_pr_and_every_push_to_main() -> None:
    body = "\n".join(_workflow_lines())
    assert "pull_request:" in body
    assert "push:" in body
    assert "- main" in body


def test_caching_never_decides_what_is_checked() -> None:
    """Caching is allowed (and now present) -- but a cache step must only ever `uses:` an action.
    A cache that ran a gate, or a `run:` step that skipped one, would put the decision about
    WHAT is verified inside the layer whose only job is to make it FAST.
    """
    body = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "actions/cache@v3" in body, (
        "the cargo cache is what makes the battery cheap enough to run on every commit; "
        "if it is removed, say so deliberately rather than by deleting a line"
    )
    # The existing `test_workflow_inlines_no_gate` already forbids a gate in any `run:` line.
    # This is its complement: no step may CONDITIONALLY run the battery based on a cache result.
    assert "cache-hit" not in body, "no step may branch on a cache hit -- the battery runs identically warm or cold"


def test_ci_parallelism_cap_is_ci_only() -> None:
    """The xdist -n and CARGO_BUILD_JOBS caps must be guarded by _IN_CI, not unconditional.

    The shared Forgejo runner is budgeted ~1.5 cpu / 1.2 GB. Capping parallelism at 2
    keeps it from OOM-killing the battery. But the cap must never apply locally: an M1
    (or any real developer machine) must keep an uncapped local path. This pin verifies
    the structural invariant: _XDIST_N and CARGO_BUILD_JOBS only appear inside an
    _IN_CI guard, so local and CI runs differ only in degree of parallelism -- never in
    which gates run or whether they pass.

    This asserted `_XDIST_N=auto` literally until `e1c107b` made the local path derive its
    worker count from available capacity (cores - load average) instead, to stop a contended
    M1 timing out Textual Pilot lanes. The invariant was intact; only the spelling changed --
    so the pin failed, and `main` sat red. A pin that freezes one implementation of a property
    rather than the property fails on the fix as loudly as on the regression, which trains
    people to edit the pin. It now asserts the shape: a CI cap of 2, and a local branch that
    is something else.
    """
    script = CI_SCRIPT.read_text(encoding="utf-8")
    # The CI detection block must be present.
    assert "_IN_CI=0" in script, "scripts/ci.sh must initialise _IN_CI=0 before the detection block"
    assert "_IN_CI=1" in script, "scripts/ci.sh must set _IN_CI=1 inside the CI-detection block"
    assert "FORGEJO_ACTIONS" in script, "CI detection must cover FORGEJO_ACTIONS (not just GITHUB_ACTIONS)"
    # The caps must be conditional, not bare assignments at the top level.
    assert "CARGO_BUILD_JOBS=2" in script, "the cargo build jobs cap must be present"

    assignments = re.findall(r"^\s*_XDIST_N=(\S*)", script, re.MULTILINE)
    assert "2" in assignments, f"the xdist worker cap must be present (found {assignments})"
    assert [value for value in assignments if value != "2"], (
        f"the uncapped local path must be present -- every _XDIST_N assignment is the CI cap ({assignments})"
    )
    # The parity property: uv run pytest must still appear (gate not removed/conditionalized).
    assert "uv run pytest" in script, "the pytest gate must still be unconditional"
    assert "cargo build --manifest-path builder_ii_validation_rs/Cargo.toml" in script, (
        "the cargo build gate must still be unconditional"
    )
