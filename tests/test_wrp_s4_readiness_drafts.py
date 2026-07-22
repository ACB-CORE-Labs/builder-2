"""W.6 S4 readiness drafts — validation_only; no promo flip."""

from __future__ import annotations

import json as json_lib
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.cli.wrp_cli import wrp_app
from builder_ii.lifecycle.candidate.promotion_decision_records import validate_promotion_decision_record
from builder_ii.lifecycle.candidate.promotion_readiness_records import validate_promotion_readiness_record
from builder_ii.wrp.s4_readiness import (
    S4_DRAFT_BACKEND_IDS,
    build_s4_decision_record,
    build_s4_gate_audit,
    build_s4_readiness_record,
    draft_all_s4_packages,
    draft_s4_package,
    validate_s4_draft_package,
    write_s4_evidence,
)

runner = CliRunner()


def test_s4_backend_ids_are_opt_in_only() -> None:
    assert "hashing_embed" not in S4_DRAFT_BACKEND_IDS
    assert "msda_python" not in S4_DRAFT_BACKEND_IDS
    assert set(S4_DRAFT_BACKEND_IDS) == {
        "modernbert_embed",
        "opa",
        "langgraph",
        "vllm_research",
    }


def test_per_backend_readiness_ready_but_not_promoted() -> None:
    for bid in S4_DRAFT_BACKEND_IDS:
        readiness = build_s4_readiness_record(bid)
        assert readiness["ready"] is True
        assert readiness["status"] == "ready"
        assert readiness["s4_promoted"] is False
        assert readiness["s3_enabled"] is False
        assert readiness["draft_only"] is True
        assert readiness["s4_backend_id"] == bid
        assert readiness["grants_runtime_authority"] is False
        assert validate_promotion_readiness_record(readiness) == []


def test_decision_always_blocked_pending_human() -> None:
    for bid in S4_DRAFT_BACKEND_IDS:
        decision = build_s4_decision_record(bid)
        assert decision["decision"] == "blocked"
        assert decision["approved"] is False
        assert decision["decided_by"] == "PENDING_HUMAN"
        assert decision["s4_promoted"] is False
        assert decision["human_decision_required"] is True
        assert validate_promotion_decision_record(decision) == []


def test_gate_audit_is_draft_not_pass() -> None:
    audit = build_s4_gate_audit()
    assert audit["status"] == "DRAFT"
    assert audit["s4_promoted"] is False
    assert audit["honesty_locks"]["decision.approved"] is False
    assert audit["human_decision_required"] is True
    assert set(audit["backends"]) == set(S4_DRAFT_BACKEND_IDS)


def test_draft_package_honesty() -> None:
    pkg = draft_s4_package("opa")
    assert pkg["ok"] is True
    assert pkg["s4_promoted"] is False
    assert pkg["engine_started"] is False
    assert pkg["cloud_invoke"] is False
    assert pkg["decision"]["approved"] is False
    assert validate_s4_draft_package(pkg) == []
    again = draft_s4_package("opa")
    assert again["digest"] == pkg["digest"]


def test_draft_all_packages() -> None:
    all_pkg = draft_all_s4_packages()
    assert all_pkg["ok"] is True
    assert all_pkg["scope"] == "all_s4_draft_backends"
    assert len(all_pkg["packages"]) == len(S4_DRAFT_BACKEND_IDS)
    assert all_pkg["s4_promoted"] is False
    assert validate_s4_draft_package(all_pkg) == []


def test_write_evidence(tmp_path: Path) -> None:
    written = write_s4_evidence(backend_id=None, evidence_dir=tmp_path)
    assert "gate_audit" in written
    for bid in S4_DRAFT_BACKEND_IDS:
        r = tmp_path / f"wrp_s4_{bid}_readiness.json"
        d = tmp_path / f"wrp_s4_{bid}_decision.json"
        assert r.is_file()
        assert d.is_file()
        readiness = json_lib.loads(r.read_text(encoding="utf-8"))
        decision = json_lib.loads(d.read_text(encoding="utf-8"))
        assert validate_promotion_readiness_record(readiness) == []
        assert validate_promotion_decision_record(decision) == []
        assert decision["approved"] is False


def test_cli_list_and_draft(tmp_path: Path) -> None:
    r = runner.invoke(wrp_app, ["s4-readiness", "list"])
    assert r.exit_code == 0, r.output
    assert "modernbert_embed" in r.output

    out = tmp_path / "draft.json"
    r = runner.invoke(
        wrp_app,
        ["s4-readiness", "draft", "--backend", "vllm_research", "-o", str(out)],
    )
    assert r.exit_code == 0, r.output
    data = json_lib.loads(out.read_text(encoding="utf-8"))
    assert data["backend_id"] == "vllm_research"
    assert data["s4_promoted"] is False
    assert data["decision"]["approved"] is False

    evidence = tmp_path / "ev"
    r = runner.invoke(
        wrp_app,
        [
            "s4-readiness",
            "draft",
            "--backend",
            "all",
            "--write-evidence",
            "--evidence-dir",
            str(evidence),
            "-o",
            str(tmp_path / "all.json"),
        ],
    )
    assert r.exit_code == 0, r.output
    assert (evidence / "wrp_s4_promotion_gate_audit.json").is_file()
    assert (evidence / "wrp_s4_opa_readiness.json").is_file()


def test_cli_rejects_unknown_backend() -> None:
    r = runner.invoke(wrp_app, ["s4-readiness", "draft", "--backend", "hashing_embed"])
    assert r.exit_code != 0
