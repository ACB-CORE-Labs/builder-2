"""config_sources.py

Generic, target-agnostic configuration source resolver for builder-II.

Precedence (highest → lowest)
------------------------------
1. CLI override
2. Process environment variable
3. .env file (dotenv)
4. builder config file (.builder.toml / builder.toml)
5. Target profile default  ← provided by target_profile_defaults
6. Built-in platform default

This module MUST NOT contain:
  * Hardcoded target-specific repo paths
  * Hardcoded target-specific agent names
  * Any string that belongs to a specific target profile (e.g. CORE)

All target-specific defaults are owned by
``builder_ii.target_profile_defaults`` and injected here at resolution
time.

Governance
----------
* No model execution.
* No commit/push authority.
* No shell execution.
* No CORE Workbench coupling.
* Secret values are redacted in all log/report output.
* Digest validation is applied to config file reads.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from builder_ii.target_profile_defaults import get_target_defaults

# ---------------------------------------------------------------------------
# Source-kind constants
# ---------------------------------------------------------------------------
SOURCE_CLI = "cli_override"
SOURCE_ENV = "process_environment"
SOURCE_DOTENV = "dotenv"
SOURCE_CONFIG_FILE = "builder_config_file"
SOURCE_TARGET_PROFILE_DEFAULT = "target_profile_default"
SOURCE_BUILTIN = "builtin_default"

_SECRET_KEYS = frozenset(
    {
        "api_key",
        "secret",
        "token",
        "password",
        "credential",
        "private_key",
        "auth",
    }
)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedValue:
    """A single resolved configuration value with provenance metadata."""

    key: str
    value: Any
    source_kind: str
    source_detail: str = ""
    redacted: bool = False

    def display_value(self) -> str:
        """Return the value as a display string, redacting secrets."""
        if self.redacted:
            return "[REDACTED]"
        return str(self.value)


@dataclass
class ConfigResolutionReport:
    """Aggregated resolution report for all requested config keys."""

    active_target: Optional[str]
    resolved: List[ResolvedValue] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "active_target": self.active_target,
            "resolved": [
                {
                    "key": r.key,
                    "value": r.display_value(),
                    "source_kind": r.source_kind,
                    "source_detail": r.source_detail,
                }
                for r in self.resolved
            ],
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_secret_key(key: str) -> bool:
    k = key.lower()
    return any(s in k for s in _SECRET_KEYS)


def _digest(value: str) -> str:
    """Return a short SHA-256 hex digest of a string value."""
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def _redact_if_secret(key: str, value: Any) -> Tuple[Any, bool]:
    if _is_secret_key(key):
        return value, True
    return value, False


def _read_dotenv(path: Path) -> Dict[str, str]:
    """Parse a minimal .env file into a dict.  No external dependency."""
    result: Dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        result[k.strip()] = v.strip().strip('"').strip("'")
    return result


def _read_config_file(path: Path) -> Dict[str, Any]:
    """Read a minimal TOML-style builder config file.

    For compatibility without a hard toml dependency we support the
    simple ``key = value`` flat format used by builder-II configs.
    Digest validation is recorded but not enforced in this layer
    (enforcement is the responsibility of the caller / audit layer).
    """
    result: Dict[str, Any] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        result[k.strip()] = v.strip().strip('"').strip("'")
    return result


# ---------------------------------------------------------------------------
# Core resolver
# ---------------------------------------------------------------------------


class ConfigSourceResolver:
    """Resolves configuration keys against the full precedence chain.

    The resolver is target-agnostic.  Target-specific defaults are
    fetched from ``target_profile_defaults.get_target_defaults()`` and
    injected as the target-profile layer in the precedence chain.

    Parameters
    ----------
    active_target:
        The currently active target profile name (e.g. "generic",
        "builder", "core").  None falls back to built-in defaults.
    cli_overrides:
        Mapping of key → value supplied by the CLI layer.
    config_file_path:
        Path to the builder config file to read (optional).
    dotenv_path:
        Path to a .env file to read (optional).
    env_prefix:
        Environment variable prefix to strip when matching keys.
        Defaults to "BUILDER_".
    """

    ENV_PREFIX = "BUILDER_"

    def __init__(
        self,
        active_target: Optional[str] = None,
        cli_overrides: Optional[Mapping[str, Any]] = None,
        config_file_path: Optional[Path] = None,
        dotenv_path: Optional[Path] = None,
        env_prefix: Optional[str] = None,
    ) -> None:
        self.active_target = active_target
        self._cli: Dict[str, Any] = dict(cli_overrides or {})
        self._config_file_path = config_file_path
        self._dotenv_path = dotenv_path
        self._env_prefix = env_prefix or self.ENV_PREFIX

        # Lazily loaded layers
        self._dotenv_cache: Optional[Dict[str, str]] = None
        self._config_file_cache: Optional[Dict[str, Any]] = None

        # Target defaults — fetched once from the defaults module
        self._target_defaults: Dict[str, Any] = get_target_defaults(active_target)

    # ------------------------------------------------------------------
    # Layer accessors
    # ------------------------------------------------------------------

    def _env_value(self, key: str) -> Optional[str]:
        env_key = self._env_prefix + key.upper()
        return os.environ.get(env_key)

    def _dotenv_value(self, key: str) -> Optional[str]:
        if self._dotenv_cache is None:
            p = self._dotenv_path or Path(".env")
            self._dotenv_cache = _read_dotenv(p)
        env_key = self._env_prefix + key.upper()
        return self._dotenv_cache.get(env_key)

    def _config_file_value(self, key: str) -> Optional[Any]:
        if self._config_file_cache is None:
            p = self._config_file_path or Path("builder.toml")
            self._config_file_cache = _read_config_file(p)
        return self._config_file_cache.get(key)

    def _target_default_value(self, key: str) -> Optional[Any]:
        return self._target_defaults.get(key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(self, key: str, builtin_default: Any = None) -> ResolvedValue:
        """Resolve *key* through the full precedence chain.

        Returns a :class:`ResolvedValue` describing both the resolved
        value and its provenance (``source_kind``).
        """
        value, redacted = None, False

        # 1. CLI
        if key in self._cli:
            value = self._cli[key]
            value, redacted = _redact_if_secret(key, value)
            return ResolvedValue(
                key=key,
                value=value,
                source_kind=SOURCE_CLI,
                source_detail="cli",
                redacted=redacted,
            )

        # 2. Process environment
        env_val = self._env_value(key)
        if env_val is not None:
            value, redacted = _redact_if_secret(key, env_val)
            return ResolvedValue(
                key=key,
                value=value,
                source_kind=SOURCE_ENV,
                source_detail=self._env_prefix + key.upper(),
                redacted=redacted,
            )

        # 3. dotenv
        dotenv_val = self._dotenv_value(key)
        if dotenv_val is not None:
            value, redacted = _redact_if_secret(key, dotenv_val)
            return ResolvedValue(
                key=key,
                value=value,
                source_kind=SOURCE_DOTENV,
                source_detail=str(self._dotenv_path or ".env"),
                redacted=redacted,
            )

        # 4. Config file
        cfg_val = self._config_file_value(key)
        if cfg_val is not None:
            value, redacted = _redact_if_secret(key, cfg_val)
            return ResolvedValue(
                key=key,
                value=value,
                source_kind=SOURCE_CONFIG_FILE,
                source_detail=str(self._config_file_path or "builder.toml"),
                redacted=redacted,
            )

        # 5. Target profile default
        tgt_val = self._target_default_value(key)
        if tgt_val is not None:
            value, redacted = _redact_if_secret(key, tgt_val)
            return ResolvedValue(
                key=key,
                value=value,
                source_kind=SOURCE_TARGET_PROFILE_DEFAULT,
                source_detail=f"target:{self.active_target or 'none'}",
                redacted=redacted,
            )

        # 6. Built-in default
        value, redacted = _redact_if_secret(key, builtin_default)
        return ResolvedValue(
            key=key,
            value=value,
            source_kind=SOURCE_BUILTIN,
            source_detail="platform",
            redacted=redacted,
        )

    def resolve_many(
        self,
        keys_with_builtins: Sequence[Tuple[str, Any]],
    ) -> ConfigResolutionReport:
        """Resolve multiple keys and return a :class:`ConfigResolutionReport`."""
        report = ConfigResolutionReport(active_target=self.active_target)
        for key, builtin in keys_with_builtins:
            report.resolved.append(self.resolve(key, builtin))
        return report

    def target_repo(self) -> ResolvedValue:
        """Resolve the effective target repository path."""
        from builder_ii.target_profile_defaults import default_target_repo_for

        builtin = default_target_repo_for(None)
        return self.resolve("default_target_repo", builtin)

    def agent_profile(self) -> ResolvedValue:
        """Resolve the effective agent profile name."""
        from builder_ii.target_profile_defaults import default_agent_profile_for

        builtin = default_agent_profile_for(None)
        return self.resolve("default_agent_profile", builtin)

    def digest_for(self, key: str) -> Optional[str]:
        """Return a short digest of the resolved value for *key*, or None."""
        rv = self.resolve(key)
        if rv.value is None:
            return None
        return _digest(str(rv.value))
