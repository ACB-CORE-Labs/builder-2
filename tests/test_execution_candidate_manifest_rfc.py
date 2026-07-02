from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RFC_PATH = ROOT / "docs" / "plan" / "PASSIVE_EXECUTION_CANDIDATE_MANIFEST_RFC.md"
ROADMAP_PATH = ROOT / "docs" / "ROADMAP.md"


def _rfc_text() -> str:
    assert RFC_PATH.exists(), "Goal 5 execution candidate manifest RFC must exist"
    return RFC_PATH.read_text(encoding="utf-8")


def test_execution_candidate_manifest_rfc_exists_and_required_sections() -> None:
    text = _rfc_text()

    required_sections = [
        "1. Current Plan Position",
        "2. Scope",
        "3. Non-Goals & Non-Negotiables",
        "4. Existing HITL / Candidate Surfaces in the Codebase",
        "5. Proposed Goal 5 Artifact Kinds",
        "6. Deferred / Rejected Kinds",
        "7. Required Cryptographic Refs",
        "8. Allowed Candidate States",
        "9. Authority Boundary & Invariants",
        "10. Candidate Scope Model",
        "11. Rollback Requirements",
        "12. Verification Requirements",
        "13. Artifact Index Requirements",
        "14. Artifact Chain Verification Requirements",
        "15. Command Authority Requirements",
        "16. Operator Command Surface Requirements",
        "17. Validation Requirements",
        "18. Tests Required for Implementation",
        "19. Rollback Path for Goal 5 Itself",
        "20. Future Handoff to Goal 6",
    ]
    for section in required_sections:
        assert section in text, f"Missing required section: {section}"


def test_execution_candidate_manifest_rfc_locks_passive_goal5_boundary() -> None:
    text = _rfc_text()
    lower = text.lower()

    assert "goal 5 is passive/candidate-only" in lower
    assert "builder_ii.hitl_approval_boundary" in text
    assert "builder_ii.execution_candidate_manifest" in text
    assert "builder_ii.execution_candidate_manifest_validation_report" in text
    assert "goal 6/runtime activation" in lower
    assert "goal 6 remains deferred" in lower
    assert "requires_separate_activation_artifact: true" in text


def test_execution_candidate_manifest_rfc_locks_false_authority_invariants() -> None:
    text = _rfc_text()

    invariants = [
        '"executes_model": false',
        '"executes_tools": false',
        '"executes_shell": false',
        '"invokes_goose": false',
        '"constructs_deepagents": false',
        '"constructs_subagents": false',
        '"invokes_mcp": false',
        '"performs_network_calls": false',
        '"mutates_target_repo": false',
        '"mutates_memory": false',
        '"runtime_execution": false',
        '"source_writes": false',
        '"memory_mutation": false',
        '"artifact_is_authority": false',
        '"bypasses_command_authority": false',
        '"bypasses_verification": false',
        '"grants_runtime_authority": false',
        '"authorizes_execution": false',
        '"grants_authority": false',
        '"requires_separate_activation_artifact": true',
        '"core_workbench_coupling": "NONE"',
    ]
    for invariant in invariants:
        assert invariant in text, f"Missing invariant: {invariant}"


def test_execution_candidate_manifest_rfc_forbids_runtime_and_mutation_surfaces() -> None:
    text = _rfc_text()
    lower = text.lower()

    required_forbidden_phrases = [
        "forbids shell execution",
        "forbids model execution",
        "forbids tool execution",
        "forbids goose invocation",
        "forbids deepagents construction",
        "forbids mcp invocation",
        "forbids network calls",
        "forbids target repo mutation",
        "forbids memory mutation",
        "no command-running code in goal 5",
        "no executor command in goal 5",
        "no artifact is authority",
    ]
    for phrase in required_forbidden_phrases:
        assert phrase in lower, f"Missing forbidden boundary phrase: {phrase}"


def test_execution_candidate_manifest_rfc_preserves_platform_boundaries() -> None:
    text = _rfc_text()
    lower = text.lower()

    assert "generic-first" in lower
    assert "core is only a target profile" in lower
    assert "core may appear only as a target profile" in lower
    assert "core workbench/ui coupling" in lower
    assert "deephaven work is out of scope and forbidden" in lower
    assert "not core workbench/ui" in lower


def test_execution_candidate_manifest_rfc_defines_refs_states_and_evidence() -> None:
    text = _rfc_text()

    required_refs_and_states = [
        "approval_boundary_ref",
        "promotion_decision_ref",
        "promotion_review_ref",
        "promotion_request_ref",
        "target_profile_ref",
        "command_authority_ref",
        "verification_profile_ref",
        "rollback_plan_ref",
        "git state/preflight refs",
        "artifact_chain_verification_report_ref",
        "CANDIDATE_RECORDED_ONLY",
        "BOUNDARY_CHECKED_ONLY",
        "PREFLIGHT_REQUIRED_ONLY",
        "ROLLBACK_REQUIRED_ONLY",
        "VERIFICATION_REQUIRED_ONLY",
        "VALIDATION_ONLY",
    ]
    for phrase in required_refs_and_states:
        assert phrase in text, f"Missing ref/state phrase: {phrase}"


def test_execution_candidate_manifest_rfc_defines_rollback_verification_and_command_authority() -> None:
    text = _rfc_text()
    lower = text.lower()

    assert "rollback evidence requirements" in lower
    assert "verification evidence requirements" in lower
    assert "rollback evidence in goal 5 is a requirement, not proof" in lower
    assert "verification evidence in goal 5 is a requirement, not completed evidence" in lower
    assert "non-executing candidate design, not activation" in lower
    assert "tier 1 artifact-only" in lower
    assert "tier 3 hitl runtime candidate" in lower


def test_execution_candidate_manifest_rfc_relationship_to_existing_verification_candidate() -> None:
    text = _rfc_text()
    lower = text.lower()

    assert "builder_ii.hitl_verification_execution_candidate" in text
    assert "specialized sibling" in lower
    assert "should not replace that specialized sibling" in lower
    assert "not silently widened" in lower


def test_roadmap_lists_goal5_rfc_without_activation() -> None:
    text = ROADMAP_PATH.read_text(encoding="utf-8")
    lower = text.lower()

    assert "docs/plan/PASSIVE_EXECUTION_CANDIDATE_MANIFEST_RFC.md" in text
    assert "builder_ii.hitl_approval_boundary" in text
    assert "not runtime activation" in lower
    assert "execution candidate activation" in lower
