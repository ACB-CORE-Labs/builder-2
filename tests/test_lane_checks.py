from builder_ii.lane_checks import check_role_lane_pair, run_lane_checks
from builder_ii.roles import builder_roles


def test_lane_checks_pass_for_current_manifest() -> None:
    report = run_lane_checks()

    assert report.ok is True
    assert report.failures == ()
    assert report.results


def test_every_role_guide_pair_is_checked() -> None:
    report = run_lane_checks()
    checked_pairs = {(result.role, result.guide) for result in report.results}
    expected_pairs = {(role.name, guide) for role in builder_roles() for guide in role.lane_guides}

    assert checked_pairs == expected_pairs


def test_patch_planner_checks_include_key_boundaries() -> None:
    results = check_role_lane_pair("patch_planner", "draft_patch_plan")
    by_check = {result.check: result for result in results}

    assert by_check["model alignment"].ok
    assert by_check["prompt renders context"].ok
    assert by_check["direct ask gate"].ok
    assert by_check["tool execution gate"].ok
    assert by_check["file edit gate"].detail == "OPERATOR_ONLY"
    assert by_check["runtime switch gate"].detail == "OPERATOR_ONLY"


def test_invariant_auditor_checks_forbid_mutating_boundaries() -> None:
    results = check_role_lane_pair("invariant_auditor", "audit_invariants")
    by_check = {result.check: result for result in results}

    assert by_check["file edit gate"].detail == "FORBIDDEN"
    assert by_check["runtime switch gate"].detail == "FORBIDDEN"
    assert by_check["heavy routing gate"].ok
