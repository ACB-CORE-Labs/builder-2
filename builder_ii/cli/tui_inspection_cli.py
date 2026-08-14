"""Read-only inspection command groups for the root ``builder`` CLI."""

from __future__ import annotations

from importlib import import_module
from typing import Callable

import typer

from builder_ii.core.tui_contract import GLYPHS, builder_dir, invalid_json_files
from builder_ii.governance.authority import CommandAuthorityError, enforce_command_authority

MainFn = Callable[[list[str] | None], int]


def _args(command: str, *positional: str | None, verbose: bool = False) -> list[str]:
    argv = [command]
    argv.extend(str(value) for value in positional if value)
    if verbose:
        argv.append("--verbose")
    return argv


def _dispatch(command_name: str, module_name: str, argv: list[str]) -> None:
    """Authority-check and dispatch to a legacy argv-based TUI module."""
    try:
        enforce_command_authority(command_name, requested_effects=())
    except CommandAuthorityError as exc:
        typer.echo(f"{GLYPHS['fail']} command authority denied: {exc}")
        raise typer.Exit(1) from exc

    invalid = invalid_json_files(builder_dir())
    if invalid:
        typer.echo(f"{GLYPHS['fail']} invalid JSON artifact(s) under {builder_dir()}:")
        for path, error in invalid:
            typer.echo(f"  {GLYPHS['fail']} {path}: {error}")
        raise typer.Exit(1)

    module = import_module(module_name)
    main: MainFn = getattr(module, "main")
    raise typer.Exit(main(argv))


inspect_app = typer.Typer(name="inspect", help="Read-only inspection surface.", no_args_is_help=True)

hitl_app = typer.Typer(help="Read-only HITL inspection surface.", no_args_is_help=True)
profile_app = typer.Typer(help="Read-only profile-pack inspection surface.", no_args_is_help=True)
model_app = typer.Typer(help="Read-only model routing inspection surface.", no_args_is_help=True)
promote_app = typer.Typer(help="Read-only promotion pipeline inspection surface.", no_args_is_help=True)
postflight_app = typer.Typer(help="Read-only postflight inspection surface.", no_args_is_help=True)
goose_app = typer.Typer(help="Read-only Goose session inspection surface.", no_args_is_help=True)

model_routing_app = typer.Typer(help="Read-only model routing artifact inspection.", no_args_is_help=True)
model_registry_app = typer.Typer(help="Read-only model registry artifact inspection.", no_args_is_help=True)


@hitl_app.command("status")
def hitl_status(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    _dispatch("builder inspect hitl status", "builder_ii.hitl_tui", _args("status", verbose=verbose))


@hitl_app.command("chain")
def hitl_chain(
    chain_id: str | None = typer.Argument(None), verbose: bool = typer.Option(False, "--verbose", "-v")
) -> None:
    _dispatch("builder inspect hitl chain", "builder_ii.hitl_tui", _args("chain", chain_id, verbose=verbose))


@hitl_app.command("pending")
def hitl_pending(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    _dispatch("builder inspect hitl pending", "builder_ii.hitl_tui", _args("pending", verbose=verbose))


@hitl_app.command("approval")
def hitl_approval(
    approval_id: str | None = typer.Argument(None), verbose: bool = typer.Option(False, "--verbose", "-v")
) -> None:
    _dispatch("builder inspect hitl approval", "builder_ii.hitl_tui", _args("approval", approval_id, verbose=verbose))


@hitl_app.command("evidence")
def hitl_evidence(
    evidence_id: str | None = typer.Argument(None), verbose: bool = typer.Option(False, "--verbose", "-v")
) -> None:
    _dispatch("builder inspect hitl evidence", "builder_ii.hitl_tui", _args("evidence", evidence_id, verbose=verbose))


@hitl_app.command("execution")
def hitl_execution(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    _dispatch("builder inspect hitl execution", "builder_ii.hitl_tui", _args("execution", verbose=verbose))


@hitl_app.command("promote")
def hitl_promote(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    _dispatch("builder inspect hitl promote", "builder_ii.hitl_tui", _args("promote", verbose=verbose))


@hitl_app.command("replay")
def hitl_replay(
    n: int = typer.Option(30, "--n", "-n"),
    agent: str | None = typer.Option(None, "--agent", "-a"),
    kind: str | None = typer.Option(None, "--kind", "-k"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    argv = ["replay", "--n", str(n)]
    if agent:
        argv.extend(["--agent", agent])
    if kind:
        argv.extend(["--kind", kind])
    if verbose:
        argv.append("--verbose")
    _dispatch("builder inspect hitl replay", "builder_ii.hitl_tui", argv)


@profile_app.command("status")
def profile_status(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    _dispatch("builder inspect profile status", "builder_ii.profile_tui", _args("status", verbose=verbose))


@profile_app.command("lifecycle")
def profile_lifecycle(
    pack_id: str | None = typer.Argument(None), verbose: bool = typer.Option(False, "--verbose", "-v")
) -> None:
    _dispatch("builder inspect profile lifecycle", "builder_ii.profile_tui", _args("lifecycle", pack_id, verbose=verbose))


@profile_app.command("validate")
def profile_validate(
    pack_id: str | None = typer.Argument(None), verbose: bool = typer.Option(False, "--verbose", "-v")
) -> None:
    _dispatch("builder inspect profile validate", "builder_ii.profile_tui", _args("validate", pack_id, verbose=verbose))


@profile_app.command("render-plan")
def profile_render_plan(
    pack_id: str | None = typer.Argument(None), verbose: bool = typer.Option(False, "--verbose", "-v")
) -> None:
    _dispatch("builder inspect profile render-plan", "builder_ii.profile_tui", _args("render-plan", pack_id, verbose=verbose))


@profile_app.command("dry-run")
def profile_dry_run(
    pack_id: str | None = typer.Argument(None), verbose: bool = typer.Option(False, "--verbose", "-v")
) -> None:
    _dispatch("builder inspect profile dry-run", "builder_ii.profile_tui", _args("dry-run", pack_id, verbose=verbose))


@profile_app.command("resolve")
def profile_resolve(
    profile: str | None = typer.Argument(None), verbose: bool = typer.Option(False, "--verbose", "-v")
) -> None:
    _dispatch("builder inspect profile resolve", "builder_ii.profile_tui", _args("resolve", profile, verbose=verbose))


@profile_app.command("history")
def profile_history(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    _dispatch("builder inspect profile history", "builder_ii.profile_tui", _args("history", verbose=verbose))


@model_routing_app.command("show")
def model_routing_show(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    _dispatch("builder inspect model routing show", "builder_ii.routing.model_tui", _args("routing", "show", verbose=verbose))


@model_routing_app.command("simulate")
def model_routing_simulate(
    intent: str | None = typer.Argument(None),
    risk: str | None = typer.Argument(None),
    tools: bool = typer.Option(False, "--tools", "-t"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    argv = ["routing", "simulate"]
    if intent:
        argv.append(intent)
    if risk:
        argv.append(risk)
    if tools:
        argv.append("--tools")
    if verbose:
        argv.append("--verbose")
    _dispatch("builder inspect model routing simulate", "builder_ii.routing.model_tui", argv)


@model_routing_app.command("candidates")
def model_routing_candidates(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    _dispatch(
        "builder inspect model routing candidates", "builder_ii.model_tui", _args("routing", "candidates", verbose=verbose)
    )


@model_routing_app.command("policy")
def model_routing_policy(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    _dispatch("builder inspect model routing policy", "builder_ii.routing.model_tui", _args("routing", "policy", verbose=verbose))


@model_routing_app.command("execution-policy")
def model_routing_execution_policy(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    _dispatch(
        "builder inspect model routing execution-policy",
        "builder_ii.model_tui",
        _args("routing", "execution-policy", verbose=verbose),
    )


@model_routing_app.command("validate")
def model_routing_validate(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    _dispatch("builder inspect model routing validate", "builder_ii.routing.model_tui", _args("routing", "validate", verbose=verbose))


@model_registry_app.command("show")
def model_registry_show(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    _dispatch("builder inspect model registry show", "builder_ii.routing.model_tui", _args("registry", "show", verbose=verbose))


@model_registry_app.command("diff")
def model_registry_diff(target_registry: str | None = typer.Argument(None)) -> None:
    _dispatch("builder inspect model registry diff", "builder_ii.routing.model_tui", _args("registry", "diff", target_registry))


model_app.add_typer(model_routing_app, name="routing")
model_app.add_typer(model_registry_app, name="registry")


@promote_app.command("status")
def promote_status(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    _dispatch("builder inspect promote status", "builder_ii.promote_tui", _args("status", verbose=verbose))


@promote_app.command("readiness")
def promote_readiness(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    _dispatch("builder inspect promote readiness", "builder_ii.promote_tui", _args("readiness", verbose=verbose))


@promote_app.command("artifact")
def promote_artifact(
    artifact_id: str | None = typer.Argument(None), verbose: bool = typer.Option(False, "--verbose", "-v")
) -> None:
    _dispatch("builder inspect promote artifact", "builder_ii.promote_tui", _args("artifact", artifact_id, verbose=verbose))


@promote_app.command("decision")
def promote_decision(
    decision_id: str | None = typer.Argument(None), verbose: bool = typer.Option(False, "--verbose", "-v")
) -> None:
    _dispatch("builder inspect promote decision", "builder_ii.promote_tui", _args("decision", decision_id, verbose=verbose))


@promote_app.command("compatibility")
def promote_compatibility(
    compatibility_id: str | None = typer.Argument(None), verbose: bool = typer.Option(False, "--verbose", "-v")
) -> None:
    _dispatch(
        "builder inspect promote compatibility",
        "builder_ii.promote_tui",
        _args("compatibility", compatibility_id, verbose=verbose),
    )


@promote_app.command("history")
def promote_history(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    _dispatch("builder inspect promote history", "builder_ii.promote_tui", _args("history", verbose=verbose))


@promote_app.command("gates")
def promote_gates() -> None:
    _dispatch("builder inspect promote gates", "builder_ii.promote_tui", ["gates"])


@postflight_app.command("status")
def postflight_status(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    _dispatch("builder inspect postflight status", "builder_ii.postflight_tui", _args("status", verbose=verbose))


@postflight_app.command("record")
def postflight_record(
    record_id: str | None = typer.Argument(None), verbose: bool = typer.Option(False, "--verbose", "-v")
) -> None:
    _dispatch("builder inspect postflight record", "builder_ii.postflight_tui", _args("record", record_id, verbose=verbose))


@postflight_app.command("verify")
def postflight_verify(
    record_id: str | None = typer.Argument(None), verbose: bool = typer.Option(False, "--verbose", "-v")
) -> None:
    _dispatch("builder inspect postflight verify", "builder_ii.postflight_tui", _args("verify", record_id, verbose=verbose))


@postflight_app.command("governance")
def postflight_governance(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    _dispatch("builder inspect postflight governance", "builder_ii.postflight_tui", _args("governance", verbose=verbose))


@postflight_app.command("actions")
def postflight_actions(
    record_id: str | None = typer.Argument(None), verbose: bool = typer.Option(False, "--verbose", "-v")
) -> None:
    _dispatch("builder inspect postflight actions", "builder_ii.postflight_tui", _args("actions", record_id, verbose=verbose))


@postflight_app.command("refs")
def postflight_refs(record_id: str | None = typer.Argument(None)) -> None:
    _dispatch("builder inspect postflight refs", "builder_ii.postflight_tui", _args("refs", record_id))


@postflight_app.command("validate")
def postflight_validate() -> None:
    _dispatch("builder inspect postflight validate", "builder_ii.postflight_tui", ["validate"])


@goose_app.command("status")
def goose_status(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    _dispatch("builder inspect goose status", "builder_ii.goose_tui", _args("status", verbose=verbose))


@goose_app.command("manifest")
def goose_manifest(
    manifest_id: str | None = typer.Argument(None), verbose: bool = typer.Option(False, "--verbose", "-v")
) -> None:
    _dispatch("builder inspect goose manifest", "builder_ii.goose_tui", _args("manifest", manifest_id, verbose=verbose))


@goose_app.command("links")
def goose_links(manifest_id: str | None = typer.Argument(None)) -> None:
    _dispatch("builder inspect goose links", "builder_ii.goose_tui", _args("links", manifest_id))


@goose_app.command("actions")
def goose_actions(
    manifest_id: str | None = typer.Argument(None), verbose: bool = typer.Option(False, "--verbose", "-v")
) -> None:
    _dispatch("builder inspect goose actions", "builder_ii.goose_tui", _args("actions", manifest_id, verbose=verbose))


@goose_app.command("governance")
def goose_governance(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    _dispatch("builder inspect goose governance", "builder_ii.goose_tui", _args("governance", verbose=verbose))


@goose_app.command("validate")
def goose_validate() -> None:
    _dispatch("builder inspect goose validate", "builder_ii.goose_tui", ["validate"])


@goose_app.command("approval")
def goose_approval(manifest_id: str | None = typer.Argument(None)) -> None:
    _dispatch("builder inspect goose approval", "builder_ii.goose_tui", _args("approval", manifest_id))


tui_inspection_app = typer.Typer(
    name="builder-tui-inspection",
    help="Launch the TUI status/inspection surface.",
    add_completion=False,
    invoke_without_command=True,
)

@tui_inspection_app.callback()
def main_inspection(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Launch the main TUI platform status panel."""
    from builder_ii.cli.tui_cli import render_platform_status
    from builder_ii.core.config import load_settings
    render_platform_status(load_settings(), verbose=verbose)


inspect_app.add_typer(hitl_app, name="hitl")
inspect_app.add_typer(profile_app, name="profile")
inspect_app.add_typer(model_app, name="model")
inspect_app.add_typer(promote_app, name="promote")
inspect_app.add_typer(postflight_app, name="postflight")
inspect_app.add_typer(goose_app, name="goose")
