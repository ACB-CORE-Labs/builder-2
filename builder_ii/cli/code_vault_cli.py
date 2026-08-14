import click
import typer

try:
    from builder_ii_code_vault.cli.code_vault_cli import code_vault_app
except ImportError:
    from builder_ii.core.codevault_upsell import CODEVAULT_CLI_UPGRADE_MESSAGE

    CODE_VAULT_UPGRADE_MESSAGE = CODEVAULT_CLI_UPGRADE_MESSAGE

    code_vault_app = typer.Typer()

    # A catch-all keeps the commercial-boundary refusal reachable for any invocation.
    @code_vault_app.command(
        context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
        help=CODE_VAULT_UPGRADE_MESSAGE,
    )
    def unavailable(argv: list[str] = typer.Argument(None)) -> None:
        click.echo(CODE_VAULT_UPGRADE_MESSAGE)
        raise typer.Exit(1)
