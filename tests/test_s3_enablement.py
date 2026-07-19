"""W3.2 S3 enablement ceremony path."""

from __future__ import annotations

import pytest

from builder_ii.wrp.s3_enablement import (
    apply_s3_session_binding,
    create_s3_enablement_decision,
    validate_s3_enablement_decision,
    validate_s3_session_binding,
)


def test_s3_decision_requires_held_proof() -> None:
    with pytest.raises(ValueError, match="held"):
        create_s3_enablement_decision(
            class_u_report={"digest": "a" * 64, "summary": {"utility_ok": True}},
            class_u_proof={"held": False, "digest": "b" * 64},
            approved_by="gov",
        )


def test_s3_session_binding_scoped() -> None:
    decision = create_s3_enablement_decision(
        class_u_report={"digest": "a" * 64, "summary": {"utility_ok": True, "proof_u_held": True}},
        class_u_proof={"held": True, "digest": "b" * 64},
        approved_by="governor",
    )
    assert validate_s3_enablement_decision(decision) == []
    assert decision["global_default_s3_enabled"] is False
    binding = apply_s3_session_binding(decision=decision, session_id="sess-1")
    assert binding["s3_enabled"] is True
    assert binding["global_default_s3_enabled"] is False
    assert validate_s3_session_binding(binding) == []
