from pathlib import Path

from builder_ii.session_cli import session_app
from typer.testing import CliRunner

runner = CliRunner()


def test_session_cli_commands(tmp_path: Path):
    invalid_json = tmp_path / "invalid.json"
    invalid_json.write_text("{invalid json", encoding="utf-8")

    empty_json = tmp_path / "empty.json"
    empty_json.write_text("{}", encoding="utf-8")

    not_found = str(tmp_path / "not_found.json")
    repo = str(tmp_path)

    # 1. plan
    res = runner.invoke(session_app, ["plan", "generic", "--repo-path", repo, "--output", str(tmp_path / "plan.json")])
    assert res.exit_code == 0

    res = runner.invoke(session_app, ["validate", str(tmp_path / "plan.json")])
    assert res.exit_code == 0

    res = runner.invoke(session_app, ["validate", not_found])
    assert res.exit_code != 0

    # 2. config
    res = runner.invoke(
        session_app, ["config", "generic", "--repo-path", repo, "--output", str(tmp_path / "config.json")]
    )
    assert res.exit_code == 0

    res = runner.invoke(session_app, ["validate-config", str(tmp_path / "config.json")])
    assert res.exit_code == 0

    # 3. goose-projection (requires config path)
    res = runner.invoke(
        session_app, ["goose-projection", str(tmp_path / "config.json"), "--output", str(tmp_path / "goose_proj.json")]
    )
    assert res.exit_code == 0

    res = runner.invoke(session_app, ["validate-goose-projection", str(tmp_path / "goose_proj.json")])
    assert res.exit_code == 0

    # 4. goose-wrapper-plan (requires projection path)
    res = runner.invoke(
        session_app,
        ["goose-wrapper-plan", str(tmp_path / "goose_proj.json"), "--output", str(tmp_path / "wrapper.json")],
    )
    assert res.exit_code == 0

    res = runner.invoke(session_app, ["validate-goose-wrapper-plan", str(tmp_path / "wrapper.json")])
    assert res.exit_code == 0

    # 5. goose-readonly-plan
    res = runner.invoke(
        session_app,
        ["goose-readonly-plan", "generic", "--repo-path", repo, "--output", str(tmp_path / "readonly.json")],
    )
    assert res.exit_code == 0

    res = runner.invoke(session_app, ["validate-goose-readonly-plan", str(tmp_path / "readonly.json")])
    assert res.exit_code == 0

    # 6. prepare-package
    res = runner.invoke(
        session_app, ["prepare-package", "generic", "--repo-path", repo, "--output-dir", str(tmp_path / "pkg")]
    )
    assert res.exit_code == 0

    res = runner.invoke(session_app, ["validate-prepare-package", str(tmp_path / "pkg")])
    assert res.exit_code == 0

    res = runner.invoke(session_app, ["summarize-prepare-package", str(tmp_path / "pkg")])
    assert res.exit_code == 0

    # 7. command-surface
    res = runner.invoke(session_app, ["command-surface"])
    assert res.exit_code == 0

    # 8. operator-surface
    res = runner.invoke(session_app, ["operator-surface"])
    assert res.exit_code == 0

    # 9. repo-map
    res = runner.invoke(
        session_app, ["repo-map", "generic", "--repo-path", repo, "--output", str(tmp_path / "repo-map.json")]
    )
    assert res.exit_code == 0

    # 10. context-pack
    res = runner.invoke(
        session_app,
        [
            "context-pack",
            "generic",
            "--repo-map",
            str(tmp_path / "repo-map.json"),
            "--output",
            str(tmp_path / "context-pack.json"),
        ],
    )
    assert res.exit_code == 0

    # Also test error branches for all commands with empty/invalid inputs
    cmds_to_fail = [
        ["plan", "invalid_target"],
        ["config", "invalid_target"],
        ["goose-projection", not_found],
        ["goose-projection", str(invalid_json)],
        ["goose-projection", str(empty_json)],
        ["goose-wrapper-plan", not_found],
        ["goose-readonly-plan", "invalid_target"],
        ["prepare-package", "invalid_target"],
        ["validate-prepare-package", not_found],
        ["repo-map", "invalid_target"],
        ["context-pack", "invalid_target", "--repo-map", str(tmp_path / "repo-map.json"), "--output", "x.json"],
    ]
    for cmd in cmds_to_fail:
        res = runner.invoke(session_app, cmd)
        assert res.exit_code != 0

    # Hit stdout branches (no --output)
    res = runner.invoke(session_app, ["plan", "generic", "--repo-path", repo])
    assert res.exit_code == 0

    res = runner.invoke(session_app, ["config", "generic", "--repo-path", repo])
    assert res.exit_code == 0

    res = runner.invoke(session_app, ["goose-projection", str(tmp_path / "config.json")])
    assert res.exit_code == 0

    res = runner.invoke(session_app, ["goose-wrapper-plan", str(tmp_path / "goose_proj.json")])
    assert res.exit_code == 0

    res = runner.invoke(session_app, ["goose-readonly-plan", "generic", "--repo-path", repo])
    assert res.exit_code == 0

    # Hit Profile Resolution ValueError by specifying non-existent profile overrides
    cmds_with_profiles = [
        ["plan", "generic", "--repo-path", repo, "--agent", "nonexistent_agent_99"],
        ["config", "generic", "--repo-path", repo, "--agent", "nonexistent_agent_99"],
        ["goose-readonly-plan", "generic", "--repo-path", repo, "--agent", "nonexistent_agent_99"],
        [
            "prepare-package",
            "generic",
            "--repo-path",
            repo,
            "--agent",
            "nonexistent_agent_99",
            "--output-dir",
            str(tmp_path / "pkg2"),
        ],
    ]
    for cmd in cmds_with_profiles:
        res = runner.invoke(session_app, cmd)
        assert res.exit_code != 0

    # Validation errors on invalid loaded JSON (schema validation)
    # The empty `{}` json created earlier will fail schema validation.
    cmds_validation = [
        ["validate", str(empty_json)],
        ["validate-config", str(empty_json)],
        ["validate-goose-projection", str(empty_json)],
        ["validate-goose-wrapper-plan", str(empty_json)],
        ["validate-goose-readonly-plan", str(empty_json)],
        ["validate-prepare-package", str(empty_json)],
    ]
    for cmd in cmds_validation:
        res = runner.invoke(session_app, cmd)
        assert res.exit_code != 0

    # 1. Test write failures
    bad_output = "/dev/null/output.json"
    runner.invoke(session_app, ["plan", "generic", "--repo-path", repo, "--output", bad_output])
    runner.invoke(session_app, ["config", "generic", "--repo-path", repo, "--output", bad_output])
    runner.invoke(session_app, ["goose-projection", str(tmp_path / "config.json"), "--output", bad_output])
    runner.invoke(session_app, ["goose-wrapper-plan", str(tmp_path / "goose_proj.json"), "--output", bad_output])
    runner.invoke(session_app, ["goose-readonly-plan", "generic", "--repo-path", repo, "--output", bad_output])
    runner.invoke(session_app, ["repo-map", "generic", "--repo-path", repo, "--output", bad_output])
    runner.invoke(
        session_app, ["context-pack", "generic", "--repo-map", str(tmp_path / "repo-map.json"), "--output", bad_output]
    )
    runner.invoke(session_app, ["prepare-package", "generic", "--repo-path", repo, "--output-dir", bad_output])

    # 2. Test JSON array instead of object
    arr_json = tmp_path / "array.json"
    arr_json.write_text("[]", encoding="utf-8")
    runner.invoke(session_app, ["validate", str(arr_json)])

    # 3. Test value errors in creation functions
    runner.invoke(session_app, ["goose-wrapper-plan", str(empty_json)])
