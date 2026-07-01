import json as json_lib
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.handoff_notes import create_artifact_ref, create_handoff_note
from builder_ii.memory_cli import memory_app
from builder_ii.research_plans import create_research_plan_artifact
from builder_ii.workflow_records import canonical_digest


runner = CliRunner()


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json_lib.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_builder_memory_cli_round_trip_from_research_plan(tmp_path: Path) -> None:
    source_path = tmp_path / "research-plan.json"
    _write_json(
        source_path,
        create_research_plan_artifact(
            target="builder",
            profile_name="research_planner",
            task="map builder memory command surface",
            topic="artifact memory",
            source_hint=("docs",),
        ),
    )

    atom_path = tmp_path / "memory-atom.json"
    atom_result = runner.invoke(
        memory_app,
        [
            "atom",
            str(source_path),
            "--output",
            str(atom_path),
            "--tag",
            "memory",
            "--tag",
            "research",
            "--created-at",
            "2026-07-01T18:10:00Z",
        ],
    )
    assert atom_result.exit_code == 0, atom_result.output
    atom = json_lib.loads(atom_path.read_text(encoding="utf-8"))
    assert atom["kind"] == "builder_ii.memory_atom"

    index_path = tmp_path / "memory-index.json"
    index_result = runner.invoke(
        memory_app,
        [
            "index",
            str(atom_path),
            "--output",
            str(index_path),
            "--index-name",
            "builder-memory-cli",
            "--task-scope",
            "artifact memory CLI",
            "--created-at",
            "2026-07-01T18:10:00Z",
        ],
    )
    assert index_result.exit_code == 0, index_result.output
    index = json_lib.loads(index_path.read_text(encoding="utf-8"))
    assert index["kind"] == "builder_ii.memory_index"

    search_path = tmp_path / "memory-search.json"
    search_result = runner.invoke(
        memory_app,
        [
            "search",
            str(index_path),
            "--query",
            "memory research",
            "--output",
            str(search_path),
            "--limit",
            "5",
            "--created-at",
            "2026-07-01T18:10:00Z",
        ],
    )
    assert search_result.exit_code == 0, search_result.output
    search = json_lib.loads(search_path.read_text(encoding="utf-8"))
    assert search["kind"] == "builder_ii.memory_search_result"
    assert search["matches"][0]["atom_id"] == atom["atom_id"]

    reconstruction_path = tmp_path / "memory-reconstruction.json"
    reconstruction_result = runner.invoke(
        memory_app,
        [
            "reconstruct",
            str(index_path),
            "--query",
            "memory research",
            "--output",
            str(reconstruction_path),
            "--max-atoms",
            "5",
            "--created-at",
            "2026-07-01T18:10:00Z",
        ],
    )
    assert reconstruction_result.exit_code == 0, reconstruction_result.output
    reconstruction = json_lib.loads(reconstruction_path.read_text(encoding="utf-8"))
    assert reconstruction["kind"] == "builder_ii.memory_reconstruction"
    assert reconstruction["selected_atom_refs"][0]["sha256"] == canonical_digest(atom)

    for command, artifact_path in (
        ("validate-atom", atom_path),
        ("validate-index", index_path),
        ("validate-search-result", search_path),
        ("validate-reconstruction", reconstruction_path),
    ):
        result = runner.invoke(memory_app, [command, str(artifact_path)])
        assert result.exit_code == 0, result.output


def test_builder_memory_atom_extracts_handoff_source_refs(tmp_path: Path) -> None:
    handoff_path = tmp_path / "handoff-note.json"
    handoff = create_handoff_note(
        target_name="builder",
        summary="Prepared a governed handoff for artifact memory follow-up.",
        next_recommended_action="Review the recorded sources.",
        session_ref=create_artifact_ref(
            kind="builder_ii.session_workflow_plan",
            path="session-workflow.json",
            sha256="a" * 64,
        ),
        goose_readonly_session_ref=create_artifact_ref(
            kind="builder_ii.goose_readonly_session_plan",
            path="goose-readonly-session.json",
            sha256="b" * 64,
        ),
        verification_report_ref=create_artifact_ref(
            kind="builder_ii.verification_profile_report",
            path="verification-profile-report.json",
            sha256="c" * 64,
        ),
    )
    _write_json(handoff_path, handoff)

    atom_path = tmp_path / "handoff-memory-atom.json"
    result = runner.invoke(
        memory_app,
        [
            "atom",
            str(handoff_path),
            "--output",
            str(atom_path),
            "--created-at",
            "2026-07-01T18:12:00Z",
        ],
    )

    assert result.exit_code == 0, result.output
    atom = json_lib.loads(atom_path.read_text(encoding="utf-8"))
    assert atom["claim_boundary"] == "reviewed_handoff"
    assert [ref["kind"] for ref in atom["source_refs"]] == [
        "builder_ii.goose_readonly_session_plan",
        "builder_ii.session_workflow_plan",
        "builder_ii.verification_profile_report",
    ]
