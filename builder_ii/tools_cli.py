from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from builder_ii.tool_registry import ToolTier, check_tools, missing_required_tools

tools_app = typer.Typer(help="Inspect builder-II external engineering tool integrations.")
console = Console()
_VALID_TIERS: set[str] = {"tier1", "tier2", "notes"}


def _normalize_tier(value: str | None) -> ToolTier | None:
    if value is None:
        return None
    if value not in _VALID_TIERS:
        console.print("[red]--tier must be one of: tier1, tier2, notes[/]")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


@tools_app.command("list")
def list_tools(tier: str | None = typer.Option(None, "--tier", help="tier1, tier2, or notes")) -> None:
    """List external tools and intended builder-II integrations."""
    table = Table("Tool", "Tier", "Category", "Integration", "Required", "Open", "Install")
    for check in check_tools(tier=_normalize_tier(tier)):
        tool = check.tool
        table.add_row(
            tool.name,
            tool.tier,
            tool.category,
            tool.integration,
            "yes" if tool.required else "no",
            "yes" if tool.open_source else "no",
            tool.install,
        )
    console.print(table)


@tools_app.command("check")
def check(tier: str | None = typer.Option(None, "--tier", help="tier1, tier2, or notes")) -> None:
    """Check whether external tools are installed on PATH."""
    table = Table("Tool", "Status", "Path", "Version", "Install")
    checks = check_tools(tier=_normalize_tier(tier))
    for item in checks:
        mark = "PASS" if item.status == "installed" else ("INFO" if item.status == "optional-ui" else "MISS")
        table.add_row(item.tool.name, mark, item.path or "-", item.version or "-", item.tool.install)
    console.print(table)
    missing = [item for item in checks if item.tool.required and item.status == "missing"]
    raise typer.Exit(1 if missing else 0)


@tools_app.command("missing")
def missing() -> None:
    """Print required tools that are missing."""
    checks = missing_required_tools()
    if not checks:
        console.print("[green]All required external tools are available[/]")
        return
    for item in checks:
        console.print(f"[red]{item.tool.name}[/] — install: {item.tool.install}")
    raise typer.Exit(1)
