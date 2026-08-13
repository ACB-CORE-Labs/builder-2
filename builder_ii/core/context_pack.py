import hashlib
import json as json_lib
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from builder_ii.core.config import Settings

DEFAULT_MARKDOWN_OUTPUT = Path(".builder/context-pack.md")
DEFAULT_REPOMIX_OUTPUT = Path(".builder/context-pack.xml")
RepoTarget = Literal["core", "builder", "generic"]

CONTEXT_PACK_RECORD_KIND = "builder_ii.context_pack_record"
CONTEXT_PACK_RECORD_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ContextPackSelection:
    task: str | None = None
    module: str | None = None
    changed: bool = False


@dataclass(frozen=True)
class ContextPackResult:
    repo: Path
    target: RepoTarget
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


def repo_for_target(settings: Settings, target: RepoTarget) -> Path:
    if target == "core":
        return settings.target_repo
    if target == "builder":
        return settings.project_root
    if target == "generic":
        return Path.cwd()
    raise ValueError(f"unknown context target: {target}")


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
        files = tuple(path for path in _tracked_files(repo) if path.startswith(prefix))
        if files:
            return files
        raise FileNotFoundError(f"module directory has no tracked files in {repo}: {rel}")
    raise FileNotFoundError(f"module not found in {repo}: {rel}")


def select_context_files(repo: Path, selection: ContextPackSelection) -> tuple[str, ...]:
    files: list[str] = []
    if selection.changed:
        files.extend(changed_files(repo))
    if selection.module:
        files.extend(_module_files(repo, selection.module))
    if not files:
        defaults = (
            "README.md",
            "docs/PLATFORM_COMPLETION_AUDIT.md",
            "docs/TOOLING.md",
            "builder_ii/core/context.py",
            "builder_ii/adapters/goose/goose_setup.py",
            "builder_ii/adapters/goose/goose_launcher.py",
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
    target: RepoTarget,
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
        f"target: `{target}`",
        f"path: `{repo}`",
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
    target: RepoTarget = "core",
    markdown_output: Path = DEFAULT_MARKDOWN_OUTPUT,
    repomix_output: Path = DEFAULT_REPOMIX_OUTPUT,
    run_repomix: bool = True,
) -> ContextPackResult:
    repo = repo_for_target(settings, target)
    selected = select_context_files(repo, selection)
    markdown_path = settings.project_root / markdown_output
    repomix_path = settings.project_root / repomix_output
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    repomix_path.parent.mkdir(parents=True, exist_ok=True)
    command = repomix_command(repo, selected, repomix_path)
    markdown_path.write_text(
        render_context_manifest(
            repo=repo,
            target=target,
            selection=selection,
            selected_files=selected,
            repomix_output=repomix_path,
            command=command,
        ),
        encoding="utf-8",
    )
    if not run_repomix:
        return ContextPackResult(repo, target, markdown_path, repomix_path, selected, command, False)
    proc = subprocess.run(command, cwd=repo, capture_output=True, text=True, timeout=300)
    return ContextPackResult(
        repo=repo,
        target=target,
        markdown_path=markdown_path,
        repomix_path=repomix_path,
        selected_files=selected,
        command=command,
        ran_repomix=True,
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def _file_sha256(path: Path | None) -> str:
    if not path or not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_context_pack_record(
    result: ContextPackResult,
    *,
    task: str | None = None,
) -> dict[str, Any]:
    md_digest = _file_sha256(result.markdown_path)
    repomix_digest = _file_sha256(result.repomix_path)
    return {
        "kind": CONTEXT_PACK_RECORD_KIND,
        "schema_version": CONTEXT_PACK_RECORD_SCHEMA_VERSION,
        "target": result.target,
        "task": task or "",
        "selected_files": list(result.selected_files),
        "markdown_path": str(result.markdown_path),
        "repomix_path": str(result.repomix_path) if result.repomix_path else "",
        "markdown_sha256": md_digest,
        "repomix_sha256": repomix_digest,
        "governance": {
            "capability_state": "context_pack_record",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_context_pack_record(record: dict[str, Any]) -> str:
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"


def write_context_pack_record(record: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_context_pack_record(record), encoding="utf-8")


def _string_list_errors(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    if any(not isinstance(item, str) or not item for item in value):
        return [f"{field} must be a list of non-empty strings"]
    return []


def validate_context_pack_record(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["context pack record must be a JSON object"]
    if data.get("kind") != CONTEXT_PACK_RECORD_KIND:
        errors.append(f"kind must be {CONTEXT_PACK_RECORD_KIND}")
    if data.get("schema_version") != CONTEXT_PACK_RECORD_SCHEMA_VERSION:
        errors.append(f"schema_version must be {CONTEXT_PACK_RECORD_SCHEMA_VERSION}")
    if data.get("target") not in ("core", "builder", "generic"):
        errors.append("target must be one of: core, builder, generic")
    errors.extend(_string_list_errors(data.get("selected_files"), field="selected_files"))

    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("capability_state") != "context_pack_record":
            errors.append("governance.capability_state must be context_pack_record")
        for key in ("runtime_execution", "model_execution", "shell_execution", "source_writes", "memory_mutation"):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")
    return errors


def validate_context_pack_record_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_context_pack_record(data)
