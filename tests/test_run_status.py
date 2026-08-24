"""Frontend-neutral run registry and root status command tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from builder_ii.cli import app
from builder_ii.core.run_registry import RunRegistryView, project_run_registry
from builder_ii.core.run_status import RunSelectionError, project_run_status
from builder_ii.governance.ledger.event_ledger import create_event_record


def _write_event(root: Path, run_id: str, *, event_type: str = "workflow_initialized") -> Path:
    events = root / "sessions" / run_id / "events"
    events.mkdir(parents=True, exist_ok=True)
    event = create_event_record(
        event_id=f"evt-{run_id}",
        session_id=run_id,
        sequence=1,
        event_type=event_type,
        stage="initialized",
        subject_refs=[],
        command_surface="test",
        policy_snapshot_ref={
            "kind": "builder_ii.command_authority_registry",
            "path": "docs/COMMAND_AUTHORITY.md",
            "required": True,
            "role": "policy",
            "sha256": "0" * 64,
        },
    )
    path = events / "0001-event.json"
    path.write_text(json.dumps(event), encoding="utf-8")
    return path


def test_registry_selects_exact_or_deterministic_latest_run(tmp_path: Path) -> None:
    _write_event(tmp_path, "run-a")
    _write_event(tmp_path, "run-b")

    registry = project_run_registry(tmp_path)

    assert isinstance(registry, RunRegistryView)
    assert registry.select().run_id == "run-b"
    assert registry.select("run-a").run_id == "run-a"
    assert registry.select("missing") is None
    assert registry.rows == registry.entries
    assert registry.to_jsonable()["artifact_is_authority"] is False


def test_status_explicit_miss_never_falls_back(tmp_path: Path) -> None:
    _write_event(tmp_path, "present")

    try:
        project_run_status(tmp_path, "missing")
    except RunSelectionError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("explicit run selection unexpectedly fell back")


def test_status_cli_prints_calm_view_and_machine_payload(tmp_path: Path) -> None:
    _write_event(tmp_path, "run-status")
    runner = CliRunner()

    human = runner.invoke(app, ["status", "run-status", "--artifact-root", str(tmp_path)])
    machine = runner.invoke(app, ["status", "run-status", "--artifact-root", str(tmp_path), "--json"])

    assert human.exit_code == 0, human.output
    assert "RUN run-status | PREPARE" in human.output
    assert "goal:" in human.output
    assert "needs-you:" in human.output
    assert "proof: ledger valid" in human.output
    assert machine.exit_code == 0, machine.output
    payload = json.loads(machine.output)
    assert payload["kind"] == "builder_ii.run_status_view"
    assert payload["selected_run_id"] == "run-status"
    assert payload["run"]["kind"] == "builder_ii.run_view"
    assert payload["run"]["artifact_is_authority"] is False


def test_status_cli_reports_no_run_without_manufacturing_one(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["status", "--artifact-root", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "NO RUN" in result.output
    assert "no ledgered run exists" in result.output
    assert not (tmp_path / "sessions").exists()


def test_corrupt_selected_session_fails_closed(tmp_path: Path) -> None:
    event = _write_event(tmp_path, "run-corrupt")
    (event.parent / "foreign.json").write_text("{", encoding="utf-8")

    result = CliRunner().invoke(app, ["status", "run-corrupt", "--artifact-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "evidence CORRUPT" in result.output
    assert "repair corrupt or foreign canonical evidence" in result.output


def test_registry_exposes_session_with_only_corrupt_event_bytes(tmp_path: Path) -> None:
    events = tmp_path / "sessions" / "only-corrupt" / "events"
    events.mkdir(parents=True)
    (events / "0001-event.json").write_text("{", encoding="utf-8")

    registry = project_run_registry(tmp_path)
    selected = registry.select("only-corrupt")

    assert selected is not None
    assert selected.event_count == 0
    assert selected.chain_valid is False
    assert selected.errors


def test_registry_does_not_mask_corrupt_wal_with_valid_json_mirror(tmp_path: Path) -> None:
    event_path = _write_event(tmp_path, "corrupt-wal")
    (event_path.parent / "events.wal").write_bytes(b"{not-json\x00")

    status = project_run_status(tmp_path, "corrupt-wal")

    assert status.selected is not None
    assert status.selected.event_count == 1
    assert status.selected.chain_valid is False
    assert any("invalid event WAL" in error for error in status.selected.errors)
    assert status.is_corrupt


def test_status_watch_suppresses_unchanged_snapshot_and_interrupts_cleanly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_event(tmp_path, "run-watch")
    poll_count = 0

    def poll_without_sleep(_interval: float) -> None:
        nonlocal poll_count
        poll_count += 1
        if poll_count == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr("builder_ii.cli.main.time.sleep", poll_without_sleep)

    result = CliRunner().invoke(
        app,
        ["status", "run-watch", "--artifact-root", str(tmp_path), "--watch", "--json"],
    )

    assert result.exit_code == 0, result.output
    assert poll_count == 2
    snapshots = [line for line in result.output.splitlines() if line]
    assert len(snapshots) == 1
    assert json.loads(snapshots[0])["selected_run_id"] == "run-watch"
