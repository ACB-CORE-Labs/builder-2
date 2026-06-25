from pathlib import Path
from types import SimpleNamespace

from builder_ii.context_pack import (
    ContextPackSelection,
    build_context_pack,
    render_context_manifest,
    repomix_command,
    select_context_files,
)


def test_select_context_files_uses_defaults_for_empty_selection() -> None:
    repo = Path.cwd()
    files = select_context_files(repo, ContextPackSelection())

    assert "README.md" in files
    assert "builder_ii/context.py" in files


def test_select_context_files_accepts_specific_file_module() -> None:
    repo = Path.cwd()
    files = select_context_files(repo, ContextPackSelection(module="builder_ii/context_pack.py"))

    assert files == ("builder_ii/context_pack.py",)


def test_repomix_command_includes_output_and_selection() -> None:
    repo = Path("/tmp/core")
    cmd = repomix_command(repo, ("a.py", "b.py"), Path("out.xml"))

    assert "--output" in cmd
    assert "out.xml" in cmd
    assert "--include" in cmd
    assert "a.py,b.py" in cmd
    assert str(repo) in cmd


def test_render_context_manifest_mentions_task_and_command() -> None:
    text = render_context_manifest(
        repo=Path("/tmp/core"),
        selection=ContextPackSelection(task="review context", module="builder_ii", changed=True),
        selected_files=("builder_ii/context.py",),
        repomix_output=Path(".builder/context-pack.xml"),
        command=("repomix", "--output", ".builder/context-pack.xml"),
    )

    assert "review context" in text
    assert "builder_ii/context.py" in text
    assert "Repomix command" in text


def test_build_context_pack_manifest_only(tmp_path: Path) -> None:
    settings = SimpleNamespace(core_repo=Path.cwd(), project_root=tmp_path)
    result = build_context_pack(
        settings,
        ContextPackSelection(task="manifest only", module="builder_ii/context_pack.py"),
        run_repomix=False,
    )

    assert result.ok
    assert result.ran_repomix is False
    assert result.markdown_path.exists()
    assert "manifest only" in result.markdown_path.read_text(encoding="utf-8")
    assert result.selected_files == ("builder_ii/context_pack.py",)
