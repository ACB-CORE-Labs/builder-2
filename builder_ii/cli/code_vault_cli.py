import click
import typer

try:
    from builder_ii_code_vault.cli.code_vault_cli import code_vault_app
except ImportError:
    from builder_ii.core.codevault_upsell import CODEVAULT_CLI_UPGRADE_MESSAGE

    CODE_VAULT_UPGRADE_MESSAGE = CODEVAULT_CLI_UPGRADE_MESSAGE

    code_vault_app = typer.Typer()

    # A catch-all command rather than a group with no subcommands: a group rejects `frame` at
    # resolve time with "No such command", which reads as a typo rather than as a capability
    # severed from open core. Swallowing the argv lets every invocation reach the refusal and
    # be told why, instead of only the bare one -- which `no_args_is_help` used to intercept,
    # leaving this message unreachable on every path.
    @code_vault_app.command(
        context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
        help=CODE_VAULT_UPGRADE_MESSAGE,
    )
    def unavailable(argv: list[str] = typer.Argument(None)) -> None:
        click.echo(CODE_VAULT_UPGRADE_MESSAGE)
        raise typer.Exit(1)
