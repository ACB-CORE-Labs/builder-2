"""Doctrine: honesty pins reject false claims; they do not forbid implementation."""

from __future__ import annotations

from pathlib import Path

from builder_ii.wrp.agent_factory import spawn_agent, validate_agent_lifecycle_record
from builder_ii.wrp.gateway_nodes import GATEWAY_MODES
from builder_ii.wrp.s3_enablement import create_s3_enablement_decision


def test_doctrine_doc_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    doc = root / "docs" / "HONESTY_PINS_VS_IMPLEMENTATION.md"
    assert doc.is_file()
    text = doc.read_text(encoding="utf-8")
    assert "Honesty pins are not a reason to defer building muscle" in text
    assert "Earned true requires evidence" in text


def test_gateway_modes_implement_not_just_pin_default() -> None:
    # Default mode is record; implemented live modes must still exist.
    assert "record" in GATEWAY_MODES
    assert "invoke_local" in GATEWAY_MODES
    assert "invoke_cloud" in GATEWAY_MODES


def test_agent_factory_default_unearned_and_earned_path() -> None:
    unearned = spawn_agent(role="code_reviewer", task="default honesty")
    assert unearned["spawn_executed"] is False
    assert unearned["runtime_binding"] == "UNBOUND"
    assert validate_agent_lifecycle_record(unearned) == []

    earned = spawn_agent(
        role="code_reviewer",
        task="earned seam bind",
        seam_execution={
            "subagent_loop_digest": "a" * 64,
            "plan_digest": "b" * 64,
            "approved_by": "operator",
            "gateway_mode": "invoke_local",
            "steps_executed": 2,
            "kill_switch_armed": True,
        },
    )
    assert earned["spawn_executed"] is True
    assert earned["spawn_permitted"] is True
    assert earned["runtime_binding"] == "SEAM_BOUND"
    assert earned["process_spawn"] is False
    assert earned["grants_authority"] is False
    assert validate_agent_lifecycle_record(earned) == []


def test_false_spawn_executed_without_evidence_rejected() -> None:
    bad = spawn_agent(role="code_reviewer", task="tamper")
    bad = dict(bad)
    bad["spawn_executed"] = True
    bad["spawn_permitted"] = True
    bad["runtime_binding"] = "SEAM_BOUND"
    bad.pop("digest", None)
    errs = validate_agent_lifecycle_record(bad)
    assert any("seam_execution" in e for e in errs)


def test_s3_session_path_exists_while_global_default_false() -> None:
    # Implementation of enablement path is present; global default stays false.
    decision = create_s3_enablement_decision(
        class_u_report={"digest": "c" * 64, "summary": {"utility_ok": True}},
        class_u_proof={"held": True, "digest": "d" * 64},
        approved_by="governor",
    )
    assert decision["global_default_s3_enabled"] is False
    assert decision["session_scoped_enable_permitted"] is True
