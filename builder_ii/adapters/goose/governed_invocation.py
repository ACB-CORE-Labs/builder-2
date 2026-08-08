"""Fail-closed capability negotiation for the governed Goose runtime.

A command named ``run-governed`` is a semantic promise, not a best-effort hint.  The
headless lane is only governed when the installed Goose build can satisfy *all* of the
mechanical obligations at once:

* carry the operator's task into the child;
* load the builder-II governed recipe; and
* strip Goose's own builtins so that recipe/MCP interposition is the only tool surface.

Historically the runtime checked only ``--text`` and then conditionally omitted
``--recipe`` / ``--with-builtin`` when a Goose version did not advertise them.  That
turned CLI drift into a silent authority drift: a command still named ``run-governed``
could start a materially different runtime.  This module makes that state
unrepresentable.  Unsupported shapes produce a typed refusal before a child exists.

This module grants no authority and spawns no process.  It only converts observed help
text plus immutable run inputs into a fixed argv/capability snapshot that an executing
boundary may subsequently authorize and launch.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

_REQUIRED_HEADLESS_FLAGS: tuple[str, ...] = ("--text", "--recipe", "--with-builtin")


class GovernedInvocationError(RuntimeError):
    """The installed Goose CLI cannot satisfy the governed invocation contract."""


@dataclass(frozen=True)
class GooseCliCapabilities:
    """Observed capability snapshot derived solely from ``goose run --help`` text."""

    supports_task: bool
    supports_recipe: bool
    supports_builtin_disable: bool
    supports_name: bool
    help_sha256: str

    @property
    def supports_governed_headless(self) -> bool:
        return self.supports_task and self.supports_recipe and self.supports_builtin_disable

    @classmethod
    def from_run_help(cls, help_text: str) -> "GooseCliCapabilities":
        encoded = help_text.encode("utf-8", errors="replace")
        return cls(
            supports_task="--text" in help_text,
            supports_recipe="--recipe" in help_text,
            supports_builtin_disable="--with-builtin" in help_text,
            supports_name="--name" in help_text,
            help_sha256=hashlib.sha256(encoded).hexdigest(),
        )

    def missing_governed_headless_flags(self) -> tuple[str, ...]:
        missing: list[str] = []
        if not self.supports_task:
            missing.append("--text")
        if not self.supports_recipe:
            missing.append("--recipe")
        if not self.supports_builtin_disable:
            missing.append("--with-builtin")
        return tuple(missing)


@dataclass(frozen=True)
class GovernedInvocationPlan:
    """A complete fixed-argv headless invocation produced from observed CLI support."""

    argv: tuple[str, ...]
    capabilities: GooseCliCapabilities
    recipe_path: Path
    recipe_sha256: str
    task_sha256: str
    session_id: str


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
    except OSError as exc:
        raise GovernedInvocationError(f"governed recipe is unreadable: {path}: {exc}") from exc
    return hasher.hexdigest()


def plan_governed_headless_invocation(
    *,
    goose_binary: str,
    recipe_path: Path,
    task: str,
    session_id: str,
    help_text: str,
) -> GovernedInvocationPlan:
    """Return the one admissible argv or refuse before any child can be spawned.

    ``--name`` is observational metadata and therefore optional.  The three authority-
    bearing controls are not optional: task delivery, recipe loading, and builtin
    suppression must all be present.  A missing recipe is also a refusal; silently
    dropping it would convert governed execution into an unknown runtime shape.
    """

    cleaned_task = task.strip()
    if not cleaned_task:
        raise GovernedInvocationError("a governed headless run requires a non-empty task")
    if not help_text.strip():
        raise GovernedInvocationError(
            "could not inspect `goose run --help`; refusing to guess the runtime CLI shape"
        )

    capabilities = GooseCliCapabilities.from_run_help(help_text)
    missing = capabilities.missing_governed_headless_flags()
    if missing:
        joined = ", ".join(missing)
        raise GovernedInvocationError(
            "this Goose build cannot satisfy the governed headless contract; "
            f"missing required advertised flag(s): {joined}. "
            "Use `builder-goose start-governed` only after its governed recipe path is valid."
        )

    recipe = Path(recipe_path)
    if not recipe.is_file():
        raise GovernedInvocationError(
            f"governed recipe not found: {recipe}; refusing to start without MCP interposition"
        )

    argv: list[str] = [goose_binary, "run", "--recipe", str(recipe)]
    if capabilities.supports_name:
        argv.extend(["--name", session_id])
    # Empty builtin selection is the explicit no-native-tools contract.
    argv.extend(["--with-builtin", "", "--text", cleaned_task])

    return GovernedInvocationPlan(
        argv=tuple(argv),
        capabilities=capabilities,
        recipe_path=recipe,
        recipe_sha256=_sha256_file(recipe),
        task_sha256=hashlib.sha256(cleaned_task.encode("utf-8")).hexdigest(),
        session_id=session_id,
    )


__all__ = [
    "GooseCliCapabilities",
    "GovernedInvocationError",
    "GovernedInvocationPlan",
    "plan_governed_headless_invocation",
]
