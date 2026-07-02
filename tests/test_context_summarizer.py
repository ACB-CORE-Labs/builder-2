from __future__ import annotations

import json as json_lib
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from builder_ii.context_cli import context_app
from builder_ii.context_pack import ContextPackSelection, build_context_pack, create_context_pack_record
from builder_ii.context_summarizer import (
    CONTEXT_SUMMARY_KIND,
    summarize_context_pack,
    validate_context_summary,
)


def test_validate_context_summary() -> None:
    valid_summary = {
        "kind": CONTEXT_SUMMARY_KIND,
        "schema_version": 1,
        "source_paths": ["file.py"],
        "source_hashes": {"file.py": "hash"},
        "target_profile": "generic",
        "model_alias": "gpt-4o-stub",
        "model_backend": "stub",
        "prompt_used": "prompt",
        "summary": "This is a summary.",
        "known_omissions": [],
        "claim_boundary": "boundary",
        "review_required": True,
        "artifact_is_authority": False,
    }
    assert validate_context_summary(valid_summary) == []

    # Invalid tests
    bad_summary = dict(valid_summary)
    bad_summary.pop("summary")
    assert "'summary' is required" in validate_context_summary(bad_summary)


def test_summarize_context_pack_logic(tmp_path: Path) -> None:
    from dataclasses import replace

    from builder_ii.config import load_settings
    settings = replace(
        load_settings(),
        project_root=tmp_path,
        core_repo=tmp_path / "core",
        allow_cloud_models=False,
    )

    # Create mock context pack record
    pack_res = build_context_pack(
        settings,
        ContextPackSelection(task="test summary"),
        target="generic",
        markdown_output=Path("context-pack.md"),
        repomix_output=Path("context-pack.xml"),
        run_repomix=False,
    )

    record = create_context_pack_record(pack_res, task="test summary")
    record_path = tmp_path / "context-pack-record.json"
    record_path.write_text(json_lib.dumps(record, indent=2), encoding="utf-8")

    # Run summarizer with gpt-4o-stub
    summary = summarize_context_pack(record_path, model_id="gpt-4o-stub", settings=settings)

    assert summary["kind"] == CONTEXT_SUMMARY_KIND
    assert summary["target_profile"] == "generic"
    assert summary["model_alias"] == "gpt-4o-stub"
    assert validate_context_summary(summary) == []


def test_cli_summarize(tmp_path: Path) -> None:
    runner = CliRunner()

    from dataclasses import replace

    from builder_ii.config import load_settings
    settings = replace(
        load_settings(),
        project_root=tmp_path,
        core_repo=tmp_path / "core",
        allow_cloud_models=False,
    )

    # Create record via CLI
    record_path = tmp_path / "context-pack-record.json"

    with patch("builder_ii.context_cli.load_settings", return_value=settings):
        # We need mock repositories to exist
        tmp_path.joinpath("README.md").write_text("Test", encoding="utf-8")

        result_art = runner.invoke(
            context_app,
            [
                "artifact",
                "--target",
                "generic",
                "--output",
                str(record_path),
            ]
        )
        assert result_art.exit_code == 0, result_art.output

        # Call summarize
        result_sum = runner.invoke(
            context_app,
            [
                "summarize",
                "--context-pack",
                str(record_path),
                "--model",
                "gpt-4o-stub",
            ]
        )
        assert result_sum.exit_code == 0, result_sum.output
        data = json_lib.loads(result_sum.stdout)
        assert data["kind"] == CONTEXT_SUMMARY_KIND
