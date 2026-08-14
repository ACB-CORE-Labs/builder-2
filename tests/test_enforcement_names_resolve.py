"""Every name passed to `enforce_command_authority` must resolve to a declared record.

THE DEFECT THIS PIN EXISTS TO CATCH:

``builder chain`` called ``enforce_command_authority("builder chain")`` as its first statement
while no record named ``builder chain`` existed in ``COMMAND_AUTHORITY_REGISTRY`` or in
``get_all_records()``. Every invocation therefore prompted the operator for a task description and
then died with an unhandled ``CommandAuthorityError`` traceback. The command shipped, appeared in
``builder --help``, and could never run.

``test_all_cli_commands_fully_covered`` was green throughout, because it resolves a command name
through inheritance -- a parent group record standing in for a subcommand by prefix -- while
``enforce_command_authority`` uses the strict lookup. A command can therefore be "covered" and
still be dead, and the existing pins could not tell the difference.

This pin closes exactly that gap and nothing wider. It deliberately does **not** demand a record
for every alias path: ``builder mcp inventory`` and ``builder tools list`` have no records of their
own, but they enforce under their canonical ``builder-mcp inventory`` / ``builder-tools list``
names, which do. Those are alias paths, not dead commands, and requiring records for them would
duplicate the registry to no benefit. What must never happen again is a call site that enforces a
name nothing declares.
"""

from __future__ import annotations

import ast
from pathlib import Path

from builder_ii.governance.authority import get_command_record

_ENFORCE = "enforce_command_authority"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _literal_enforcement_sites() -> list[tuple[str, int, str]]:
    """Every ``enforce_command_authority("literal")`` call site in the package.

    Only string-literal first arguments are collected: a computed name cannot be checked
    statically, and pretending otherwise would make this pin claim coverage it does not have.
    """
    sites: list[tuple[str, int, str]] = []
    package = _repo_root() / "builder_ii"
    for path in sorted(package.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - no such file today
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if name != _ENFORCE or not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                sites.append((str(path.relative_to(_repo_root())), node.lineno, first.value))
    return sites


def test_the_scan_finds_the_enforcement_sites_at_all() -> None:
    """Teeth check: a pin that silently found nothing would pass forever."""
    sites = _literal_enforcement_sites()
    assert len(sites) >= 40, f"expected the enforcement sites to be found, got {len(sites)}"


def test_every_enforced_name_resolves_to_a_declared_record() -> None:
    """A name enforced but not declared is a command that cannot run. There must be none."""
    unresolvable = [
        f"{path}:{line} enforces {name!r}, which no declared record names"
        for path, line, name in _literal_enforcement_sites()
        if get_command_record(name) is None
    ]
    assert unresolvable == [], "\n".join(unresolvable)


def test_the_strict_lookup_is_actually_discriminating() -> None:
    """Guards the pin above: if `get_command_record` returned a record for anything, it proves nothing."""
    assert get_command_record("builder-totally-fictitious-xyz-command") is None


def test_builder_chain_is_declared() -> None:
    """The specific regression. `builder chain` enforces its own name, so it must declare it."""
    record = get_command_record("builder chain")
    assert record is not None, "builder chain enforces `builder chain`; without a record it is dead on arrival"
