from pathlib import Path


def test_hitl_promotion_bridge_rfc_exists_and_covers_sections() -> None:
    rfc_path = Path(__file__).resolve().parent.parent / "docs" / "plan" / "PASSIVE_HITL_PROMOTION_BRIDGE_RFC.md"
    assert rfc_path.exists(), "docs/plan/PASSIVE_HITL_PROMOTION_BRIDGE_RFC.md must exist"

    content = rfc_path.read_text(encoding="utf-8")

    required_sections = [
        "1. Current Plan Position",
        "2. Scope",
        "3. Non-Goals & Non-Negotiables",
        "4. Proposed Artifact Kinds",
        "5. Per-Artifact Required Refs",
        "6. Allowed Statuses & Dispositions",
        "7. Authority Boundary & Invariants",
        "8. Active-State Forbidden Terms",
        "9. Validation Requirements",
        "10. Artifact Index Integration Requirements",
        "11. Artifact Chain Verification Requirements",
        "12. Command Authority Requirements",
        "13. Operator Command Surface Requirements",
        "14. Tests Required for the Later Implementation PR",
        "15. Rollback Path",
        "16. Future Handoff to Goal 5 / Goal 6",
    ]
    for section in required_sections:
        assert section in content, f"Missing required section in RFC: {section}"


def test_hitl_promotion_bridge_rfc_enforces_passive_invariants() -> None:
    rfc_path = Path(__file__).resolve().parent.parent / "docs" / "plan" / "PASSIVE_HITL_PROMOTION_BRIDGE_RFC.md"
    content = rfc_path.read_text(encoding="utf-8")

    invariants = [
        'executes_model": false',
        'executes_tools": false',
        'executes_shell": false',
        'invokes_goose": false',
        'constructs_deepagents": false',
        'constructs_subagents": false',
        'invokes_mcp": false',
        'performs_network_calls": false',
        'mutates_target_repo": false',
        'mutates_memory": false',
        'artifact_is_authority": false',
        'bypasses_command_authority": false',
        'bypasses_verification": false',
        'core_workbench_coupling": "NONE"',
        'grants_runtime_authority": false',
        'authorizes_execution": false',
        'requires_separate_execution_candidate": true',
    ]
    for inv in invariants:
        assert inv in content, f"Missing invariant enforcement in RFC: {inv}"


def test_hitl_promotion_bridge_rfc_covers_artifact_kinds_and_deferred() -> None:
    rfc_path = Path(__file__).resolve().parent.parent / "docs" / "plan" / "PASSIVE_HITL_PROMOTION_BRIDGE_RFC.md"
    content = rfc_path.read_text(encoding="utf-8")

    kinds = [
        "builder_ii.hitl_promotion_request",
        "builder_ii.hitl_promotion_review",
        "builder_ii.hitl_promotion_decision",
        "builder_ii.hitl_approval_boundary",
        "builder_ii.hitl_rejection_record",
        "builder_ii.hitl_promotion_validation_report",
    ]
    for kind in kinds:
        assert kind in content, f"Missing artifact kind in RFC: {kind}"

    assert "builder_ii.execution_candidate_manifest" in content
    assert "Rejected/Deferred to Goal 5" in content
