"""Read-only repository identity preflight for governed delivery lanes."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

REPOSITORY_IDENTITY_KIND = "builder_ii.repository_identity_preflight"
DEFAULT_CANONICAL_REPOSITORY = "https://github.com/ACB-CORE-Labs/builder-2"


@dataclass(frozen=True)
class RepositoryIdentityReport:
    remote_name: str
    configured_url: str | None
    canonical_repository: str
    matches: bool
    error: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": REPOSITORY_IDENTITY_KIND,
            "schema_version": 1,
            "remote_name": self.remote_name,
            "configured_url": self.configured_url,
            "canonical_repository": self.canonical_repository,
            "matches": self.matches,
            "governance": {
                "artifact_is_authority": False,
                "grants_action_authority": False,
                "grants_runtime_authority": False,
                "source_writes": "DISABLED",
                "network_mutation": "DISABLED",
            },
            **({"error": self.error} if self.error else {}),
        }


def _normalize_url(url: str) -> str:
    return url.strip().removesuffix("/").removesuffix(".git").lower()


def check_repository_identity(
    *,
    canonical_repository: str = DEFAULT_CANONICAL_REPOSITORY,
    remote_name: str = "origin",
) -> RepositoryIdentityReport:
    """Compare a configured Git remote with the declared canonical repository."""
    try:
        result = subprocess.run(
            ["git", "config", "--get", f"remote.{remote_name}.url"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return RepositoryIdentityReport(remote_name, None, canonical_repository, False, str(exc))

    configured_url = result.stdout.strip() or None
    if result.returncode != 0 or configured_url is None:
        return RepositoryIdentityReport(
            remote_name,
            configured_url,
            canonical_repository,
            False,
            f"remote {remote_name!r} is not configured",
        )

    matches = _normalize_url(configured_url) == _normalize_url(canonical_repository)
    return RepositoryIdentityReport(
        remote_name,
        configured_url,
        canonical_repository,
        matches,
        None if matches else "configured remote does not match the canonical repository",
    )
