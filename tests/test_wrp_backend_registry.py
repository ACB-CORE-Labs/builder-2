"""P6.1 backend registry + doctor — inventory honesty, M1 defaults healthy."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from builder_ii.cli.wrp_cli import wrp_app
from builder_ii.wrp.backend_registry import backend_ids, doctor_backends, list_backends

runner = CliRunner()


def test_list_backends_includes_required_ids() -> None:
    ids = set(backend_ids())
    required = {
        "hashing_embed",
        "modernbert_embed",
        "msda_python",
        "opa",
        "pure_graph_projection",
        "langgraph",
        "vllm_research",
        "msda_preflight",
        "classifier_hash_embed",
    }
    assert required <= ids
    for row in list_backends():
        assert row["grants_authority"] is False
        assert "health" in row and "state" in row["health"]
        assert row["is_default_runtime"] in (True, False)


def test_doctor_defaults_healthy_without_heavy_deps() -> None:
    report = doctor_backends()
    assert report["ok"] is True
    assert report["default_runtime_ok"] is True
    assert report["grants_authority"] is False
    assert report["s3_enabled"] is False
    assert report["s4_promoted"] is False
    assert report["m1_safe_defaults"] is True
    # Defaults must be ready
    by_id = {b["id"]: b for b in report["backends"]}
    assert by_id["hashing_embed"]["health"]["ready"] is True
    assert by_id["msda_python"]["health"]["ready"] is True
    # Research stub never claims ready engine
    assert by_id["vllm_research"]["health"]["state"] == "research_stub"
    assert by_id["vllm_research"]["is_default_runtime"] is False


def test_doctor_does_not_require_opa_or_langgraph() -> None:
    report = doctor_backends()
    assert report["ok"] is True
    # unavailable list may include opa/langgraph/modernbert — still ok
    by_id = {b["id"]: b for b in report["backends"]}
    if not by_id["opa"]["health"]["available"]:
        assert "opa" in report["unavailable"] or by_id["opa"]["health"]["state"] == "unavailable"


def test_modernbert_not_default(monkeypatch) -> None:
    monkeypatch.delenv("BUILDER_II_WRP_EMBEDDER", raising=False)
    by_id = {b["id"]: b for b in list_backends()}
    assert by_id["modernbert_embed"]["is_default_runtime"] is False
    assert by_id["modernbert_embed"]["opt_in_enabled"] is False
    assert by_id["hashing_embed"]["is_default_runtime"] is True


def test_cli_backends_and_doctor(tmp_path: Path) -> None:
    inv = tmp_path / "inv.json"
    r = runner.invoke(wrp_app, ["backends", "-o", str(inv)])
    assert r.exit_code == 0, r.output
    assert inv.is_file()

    doc = tmp_path / "doc.json"
    r = runner.invoke(wrp_app, ["doctor-backends", "-o", str(doc)])
    assert r.exit_code == 0, r.output
    assert doc.is_file()
    import json

    data = json.loads(doc.read_text(encoding="utf-8"))
    assert data["ok"] is True
    assert data["s4_promoted"] is False
