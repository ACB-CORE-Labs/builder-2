from __future__ import annotations

from builder_ii.core.release_proof import _ci_receipt_errors


def _receipt(commit: str) -> dict:
    return {
        "valid": True,
        "overall_state": "PASSED",
        "head_sha_before": commit,
        "head_sha_after": commit,
        "head_sha_stable": True,
        "working_tree_clean": True,
        "skipped": [],
        "gates": [{"status": "PASSED", "skip_reason": None}],
    }


def test_ci_receipt_requires_exact_candidate_tip_and_zero_skips() -> None:
    commit = "1" * 40
    assert _ci_receipt_errors(_receipt(commit), commit) == []

    stale = _receipt("2" * 40)
    assert any("exact-tip" in error for error in _ci_receipt_errors(stale, commit))

    skipped = _receipt(commit)
    skipped["gates"][0] = {"status": "SKIPPED", "skip_reason": "missing tool"}
    assert any("zero blocking skips" in error for error in _ci_receipt_errors(skipped, commit))
