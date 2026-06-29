from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from builder_ii.event_ledger import load_event_records, replay_events
from builder_ii.readonly_founder_demo import generate_readonly_founder_demo
from builder_ii.targets_cli import targets_app

runner = CliRunner()


def test_readonly_founder_demo_idempotence(tmp_path: Path) -> None:
    out = tmp_path / "core-readonly-idempotence"
    session_id = "wf-core-idempotence-test"

    res1 = generate_readonly_founder_demo(
        target="core", output_dir=out, session_id=session_id, force=False
    )
    assert res1["event_ledger"].exists()
    assert res1["workflow_status"].exists()

    events1 = load_event_records(out / "events")
    assert len(events1) == 4
    replay1 = replay_events(events1, session_id=session_id)
    assert replay1["valid"] is True
    assert replay1["current_stage"] == "candidate"

    with pytest.raises(ValueError) as excinfo:
        generate_readonly_founder_demo(
            target="core", output_dir=out, session_id=session_id, force=False
        )
    assert "already exists and is not empty" in str(excinfo.value)
    assert "Use --force to overwrite" in str(excinfo.value)

    from builder_ii.cli import app as main_app

    result_vc = runner.invoke(
        main_app,
        [
            "workflow",
            "verify-chain",
            session_id,
            "--workflows-dir",
            str(tmp_path),
        ],
    )
    assert result_vc.exit_code == 0

    events_dir = out / "events"
    event5_path = events_dir / "0005-workflow_chain_verified.json"
    assert event5_path.exists()

    events_vc = load_event_records(events_dir)
    assert len(events_vc) == 5
    replay_vc = replay_events(events_vc, session_id=session_id)
    assert replay_vc["valid"] is True
    assert replay_vc["current_stage"] == "chain_verified"

    res2 = generate_readonly_founder_demo(
        target="core", output_dir=out, session_id=session_id, force=True
    )
    assert res2["event_ledger"].exists()

    assert not event5_path.exists()
    events2 = load_event_records(events_dir)
    assert len(events2) == 4
    replay2 = replay_events(events2, session_id=session_id)
    assert replay2["valid"] is True
    assert replay2["current_stage"] == "candidate"

    result_vc2 = runner.invoke(
        main_app,
        [
            "workflow",
            "verify-chain",
            session_id,
            "--workflows-dir",
            str(tmp_path),
        ],
    )
    assert result_vc2.exit_code == 0
    assert event5_path.exists()

    events_vc2 = load_event_records(events_dir)
    assert len(events_vc2) == 5
    replay_vc2 = replay_events(events_vc2, session_id=session_id)
    assert replay_vc2["valid"] is True
    assert replay_vc2["current_stage"] == "chain_verified"


def test_readonly_founder_demo_cli_idempotence(tmp_path: Path) -> None:
    out = tmp_path / "core-readonly-cli-idempotence"

    res1 = runner.invoke(
        targets_app,
        ["readonly-founder-demo", "core", "--output", str(out)],
    )
    assert res1.exit_code == 0
    assert "Generated passive read-only founder demo" in " ".join(res1.stdout.split())

    res2 = runner.invoke(
        targets_app,
        ["readonly-founder-demo", "core", "--output", str(out)],
    )
    assert res2.exit_code == 1
    assert "Error:" in " ".join(res2.stdout.split())
    assert "already exists and is not empty" in " ".join(res2.stdout.split())

    res3 = runner.invoke(
        targets_app,
        ["readonly-founder-demo", "core", "--output", str(out), "--force"],
    )
    assert res3.exit_code == 0
    assert "Generated passive read-only founder demo" in " ".join(res3.stdout.split())


def test_readonly_founder_demo_force_safety_violations(tmp_path: Path) -> None:
    from builder_ii.config import load_settings
    from builder_ii.readonly_founder_demo import validate_safe_demo_directory_for_deletion

    settings = load_settings()
    proj_root = Path(settings.project_root).resolve().absolute()

    unsafe_paths = [
        proj_root,
        Path.cwd(),
        Path.home(),
        Path("/"),
        proj_root / ".builder",
        proj_root / ".builder" / "cache",
        proj_root / "builder_ii",
        proj_root / "tests",
        proj_root / "custom-demo-folder",
        tmp_path / "plain-output",
    ]

    for path in unsafe_paths:
        with pytest.raises(ValueError) as excinfo:
            validate_safe_demo_directory_for_deletion(path, settings)
        assert "Safety violation:" in str(excinfo.value)

    safe_paths = [
        proj_root / ".builder" / "demos" / "core-readonly-test",
        tmp_path / "isolated-demo-test",
        tmp_path / "core-readonly-idempotence",
    ]
    for path in safe_paths:
        validate_safe_demo_directory_for_deletion(path, settings)

    blocked_dir = proj_root / ".builder" / "cache"
    blocked_dir.mkdir(parents=True, exist_ok=True)
    (blocked_dir / "sentinel.txt").write_text("keep\n", encoding="utf-8")

    result = runner.invoke(
        targets_app,
        ["readonly-founder-demo", "core", "--output", str(blocked_dir), "--force"],
    )
    assert result.exit_code == 1
    normalized_out = " ".join(result.stdout.split())
    assert "Error:" in normalized_out
    assert "Safety violation:" in normalized_out
    assert (blocked_dir / "sentinel.txt").exists()

    file_output = tmp_path / "core-readonly-file"
    file_output.write_text("keep\\n", encoding="utf-8")
    file_result = runner.invoke(
        targets_app,
        ["readonly-founder-demo", "core", "--output", str(file_output), "--force"],
    )
    assert file_result.exit_code == 1
    file_out = " ".join(file_result.stdout.split())
    assert "Error:" in file_out
    assert "not a directory" in file_out
    assert file_output.read_text(encoding="utf-8") == "keep\\n"
