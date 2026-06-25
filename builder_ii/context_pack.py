from __future__ import annotations

import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from builder_ii.config import Settings

DEFAULT_MARKDOWN_OUTPUT = Path(".builder/context-pack.md")
DEFAULT_REPOMIX_OUTPUT = Path(".builder/context-pack.xml")


@dataclass(frozen=True)
class ContextPackSelection:
    task: str | None = None
    module: str | None = None
    changed: bool = False


@dataclass(frozen=True)
class ContextPackResult:
    repo: Path
    markdown_path: Path
    repomix_path: Path | None
    selected_files: tuple[str, ...]
    command: tuple[str, ...] | None
    ran_repomix: bool
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode in (None, 0)


def _run_git(repo: Path, args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return (proc.stdout or proc.stderr).strip()


def git_status(repo: Path) -> str:
    try:
        return _run_git(repo, ["status", "--short", "--branch"]) or "(empty)"
    except (OSError, subprocess.SubprocessError):
        return "[git unavailable]"


def changed_files(repo: Path) -> tuple[str, ...]:
    try:
        tracked = _run_git(repo, ["diff", "--name-only", "HEAD"])
        untracked = _run_git(repo, ["ls-files", "--others", "--exclude-standard"])
    except (OSError, subprocess.SubprocessError):
        return ()
    files = [line.strip() for line in (tracked + "\n" + untracked).splitlines() if line.strip()]
    return tuple(dict.fromkeys(files))


def _tracked_files(repo: Path) -> tuple[str, ...]:
    try:
        out = _run_git(repo, ["ls-files"])
    except (OSError, subprocess.SubprocessError):
        return ()
    return tuple(line.strip() for line in out.splitlines() if line.strip())


def _module_files(repo: Path, module: str) -> tuple[str, ...]:
    rel = module.strip().strip("/")
    target = repo / rel
    if target.is_file():
        return (rel,)
    if target.is_dir():
        prefix = rel + "/"
        return tuple(path for path in _tracked_files(repo) if path.startswith(prefix))
    return (rel,)


def select_context_files(repo: Path, selection: ContextPackSelection) -> tuple[str, ...]:
    files: list[str] = []
    if selection.changed:
        files.extend(changed_files(repo))
    if selection.module:
        files.extend(_module_files(repo, selection.module))
    if not files:
        defaults = (
            "README.md",
            "docs/ROADMAP.md",
            "docs/TOOLING.md",
            "builder_ii/context.py",
            "builder_ii/goose_setup.py",
            "builder_ii/goose_launcher.py",
            "recipes/core-platform.yaml",
            "recipes/core-coding.yaml",
        )
        files.extend(path for path in defaults if (repo / path).exists())
    return tuple(dict.fromkeys(files))


def repomix_command(repo: Path, files: tuple[str, ...], output: Path) -> tuple[str, ...]:
    cmd = shutil.which("repomix") or "repomix"
    args = [cmd, "--output", str(output)]
    if files:
        args.extend(["--include", ",".join(files)])
    args.append(str(repo))
    return tuple(args)


def render_context_manifest(
    *,
    repo: Path,
    selection: ContextPackSelection,
    selected_files: tuple[str, ...],
    repomix_output: Path,
    command: tuple[str, ...],
) -> str:
    lines = [
        "# builder-II context pack",
        "",
        "This file is a small manifest for the generated AI context pack.",
        "The full repository content pack is produced by Repomix when enabled.",
        "",
        "## Task",
        "",
        selection.task or "(none supplied)",
        "",
        "## Repository",
        "",
        f"`{repo}`",
        "",
        "## Git status",
        "",
        "```text",
        git_status(repo),
        "```",
        "",
        "## Selection",
        "",
        f"changed: `{selection.changed}`",
        f"module: `{selection.module or ''}`",
        "",
        "## Selected files",
        "",
    ]
    if selected_files:
        lines.extend(f"- `{path}`" for path in selected_files)
    else:
        lines.append("(none)")
    lines.extend(
        [
            "",
            "## Repomix output",
            "",
            f"`{repomix_output}`",
            "",
            "## Repomix command",
            "",
            "```bash",
            " ".join(shlex.quote(part) for part in command),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def build_context_pack(
    settings: Settings,
    selection: ContextPackSelection,
    *,
    markdown_output: Path = DEFAULT_MARKDOWN_OUTPUT,
    repomix_output: Path = DEFAULT_REPOMIX_OUTPUT,
    run_repomix: bool = True,
) -> ContextPackResult:
    repo = settings.core_repo
    selected = select_context_files(repo, selection)
    markdown_path = settings.project_root / markdown_output
    repomix_path = settings.project_root / repomix_output
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    repomix_path.parent.mkdir(parents=True, exist_ok=True)
    command = repomix_command(repo, selected, repomix_path)
    markdown_path.write_text(
        render_context_manifest(
            repo=repo,
            selection=selection,
            selected_files=selected,
            repomix_output=repomix_path,
            command=command,
        ),
        encoding="utf-8",
    )
    if not run_repomix:
        return ContextPackResult(repo, markdown_path, repomix_path, selected, command, False)
    proc = subprocess.run(command, cwd=repo, capture_output=True, text=True, timeout=300)
    return ContextPackResult(
        repo=repo,
        markdown_path=markdown_path,
        repomix_path=repomix_path,
        selected_files=selected,
        command=command,
        ran_repomix=True,
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )
