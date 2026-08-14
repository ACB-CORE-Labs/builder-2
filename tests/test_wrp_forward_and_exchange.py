from __future__ import annotations

from pathlib import Path

from builder_ii.wrp.exchange import (
    create_governor_certification,
    create_maker_candidate_manifest,
    validate_governor_certification,
    validate_maker_candidate_manifest,
    write_exchange_package,
)
from builder_ii.wrp.forward_operator import forward_route, validate_forward_route
from builder_ii.wrp.patterns import sequential_chain
from builder_ii.wrp.subtask_graph import create_subtask_graph, replay_graph_digests, validate_subtask_graph


def test_forward_route_composes_passive_components() -> None:
    art = forward_route(text="implement allocate fleet optimizer tests")
    assert validate_forward_route(art) == []
    assert art["operator"] == "R"
    assert art["executes_model"] is False
    assert "components" in art


def test_replay_perfect_match() -> None:
    plan = create_subtask_graph(
        sequential_chain(["a", "b", "c"]),
        task="replay demo",
    )
    assert validate_subtask_graph(plan) == []
    observed = [
        {"node_id": "a", "digest": "a" * 64},
        {"node_id": "b", "digest": "b" * 64},
        {"node_id": "c", "digest": "c" * 64},
    ]
    report = replay_graph_digests(planned=plan, observed_chain=observed)
    assert report["perfect_match"] is True


def test_exchange_package_and_certs(tmp_path: Path) -> None:
    manifest = create_maker_candidate_manifest(
        wave="G0",
        branch="feat/wrp-control-plane",
        summary="G0 constitutionalization",
        artifact_digests={"adr": "d" * 64},
        test_commands=["uv run pytest tests/test_wrp_spaces.py -q"],
        test_exit_code=0,
    )
    assert validate_maker_candidate_manifest(manifest) == []
    wave_dir = write_exchange_package(tmp_path, wave="G0", maker_manifest=manifest)
    assert (wave_dir / "maker_candidate_manifest.json").is_file()
    cert = create_governor_certification(
        wave="G0",
        decision="PASS",
        findings=["ADR honest"],
        maker_manifest_digest=manifest["digest"],
    )
    assert validate_governor_certification(cert) == []
    assert cert["permits_push"] is True
