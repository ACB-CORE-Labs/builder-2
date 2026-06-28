import json
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.model_client_registry import create_model_client_registry, write_model_client_registry
from builder_ii.model_policy_cli import model_policy_app

runner = CliRunner()


def test_model_policy_validate_success(tmp_path: Path):
    reg = create_model_client_registry()
    path = tmp_path / "registry.json"
    write_model_client_registry(reg, path)

    result = runner.invoke(model_policy_app, ["validate", str(path)])
    assert result.exit_code == 0
    assert "is valid" in result.output


def test_model_policy_validate_failure(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text('{"kind": "builder_ii.model_client_registry", "schema_version": "1.0.0"}', encoding="utf-8")

    result = runner.invoke(model_policy_app, ["validate", str(path)])
    assert result.exit_code != 0
    assert "Validation error" in result.output


def test_model_policy_render(tmp_path: Path):
    out_path = tmp_path / "rec.json"
    result = runner.invoke(
        model_policy_app,
        [
            "render",
            "--task-intent",
            "coding",
            "--max-risk",
            "local_offline",
            "--output",
            str(out_path),
        ],
    )
    assert result.exit_code == 0
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["kind"] == "builder_ii.model_routing_recommendation"
    assert data["recommended_candidates"][0]["model_alias"] == "qwen-coder"


def test_model_policy_dry_run(tmp_path: Path):
    out_path = tmp_path / "dry_run.json"
    result = runner.invoke(
        model_policy_app,
        ["dry-run", "--output", str(out_path)],
    )
    assert result.exit_code == 0
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["kind"] == "builder_ii.model_routing_recommendation"
