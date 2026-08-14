from __future__ import annotations

from test_hitl_chain_binding import _artifact_fixtures

from builder_ii.governance.hitl.hitl_chain_binding import (
    bind_hitl_chain_artifacts,
    validate_hitl_chain_binding,
    verify_hitl_chain_binding_files,
)


def test_verify_hitl_chain_binding_files_allows_absent_evidence_bundle(tmp_path):
    paths = _artifact_fixtures(tmp_path)
    binding = bind_hitl_chain_artifacts(
        base_dir=tmp_path,
        proposal_path=paths["proposal.json"],
        approval_path=paths["approval.json"],
        preflight_path=paths["preflight.json"],
        request_path=paths["request.json"],
        receipt_path=paths["receipt.json"],
        postflight_path=paths["postflight.json"],
        verification_path=paths["verification.json"],
    )

    assert "evidence_bundle_ref" not in binding
    assert validate_hitl_chain_binding(binding) == []
    assert verify_hitl_chain_binding_files(binding, base_dir=tmp_path) == []
