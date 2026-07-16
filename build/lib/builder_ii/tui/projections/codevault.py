"""CodeVault frame / demo status projection (read-only, no vault I/O mutation)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_VAULT_KIND_FRAGMENTS = (
    "code_vault",
    "hierarchical_frame",
    "geometric",
    "vault_frame",
    "recall_report",
)


@dataclass(frozen=True)
class VaultArtifactView:
    kind: str
    path: str
    label: str


@dataclass(frozen=True)
class CodeVaultView:
    is_installed: bool
    artifacts: tuple[VaultArtifactView, ...]
    frame_count: int
    compose_demo: str
    compose_status: str
    compose_frame: str
    note: str
    error: str | None = None


def project_code_vault(*, artifacts_dir: Path | None, project_root: Path | None = None) -> CodeVaultView:
    arts: list[VaultArtifactView] = []
    error: str | None = None

    try:
        import builder_ii.code_vault  # noqa: F401
        is_installed = True
        note = (
            "CodeVault is exact geometric recall — not ANN/HNSW. "
            "CLI: builder-code-vault; prepare-package may include a frame."
        )
    except ImportError:
        is_installed = False
        note = "CodeVault not installed. Upgrade your builder-ii package to enable CodeVault features."
        error = "CodeVault package not found"

    if is_installed:
        try:
            search_roots: list[Path] = []
            if artifacts_dir is not None:
                search_roots.append(artifacts_dir)
                search_roots.append(artifacts_dir.parent / "code_vault")
                search_roots.append(artifacts_dir.parent / "vault")
            if project_root is not None:
                search_roots.append(project_root / ".builder" / "code_vault")

            seen: set[Path] = set()
            for root in search_roots:
                if not root.exists():
                    continue
                for path in sorted(root.rglob("*.json")):
                    try:
                        resolved = path.resolve()
                    except OSError:
                        continue
                    if resolved in seen:
                        continue
                    seen.add(resolved)
                    try:
                        data = json.loads(path.read_text(encoding="utf-8"))
                    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                        continue
                    if not isinstance(data, dict):
                        continue
                    kind = str(data.get("kind", ""))
                    kl = kind.lower()
                    name = path.name.lower()
                    if any(f in kl for f in _VAULT_KIND_FRAGMENTS) or "vault" in name or "frame" in name:
                        label = str(data.get("name") or data.get("frame_id") or path.stem)
                        arts.append(VaultArtifactView(kind=kind or path.name, path=str(path), label=label))
        except Exception as exc:
            error = str(exc)

    return CodeVaultView(
        is_installed=is_installed,
        artifacts=tuple(arts[:30]),
        frame_count=len(arts),
        compose_demo="uv run builder-code-vault demo" if is_installed else "",
        compose_status="uv run builder-code-vault status" if is_installed else "",
        compose_frame="uv run builder-code-vault frame --help" if is_installed else "",
        note=note,
        error=error,
    )
