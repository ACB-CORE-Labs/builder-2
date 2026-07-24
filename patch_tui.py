content = open("builder_ii/cli/tui_inspection_cli.py").read()
if "inspect_app = typer.Typer" not in content:
    content = content.replace("hitl_app = typer.Typer", "inspect_app = typer.Typer(help=\"Read-only inspection surface.\", no_args_is_help=True)\n\nhitl_app = typer.Typer")
    content += "\ninspect_app.add_typer(hitl_app, name=\"hitl\")\n"
    content += "inspect_app.add_typer(profile_app, name=\"profile\")\n"
    content += "inspect_app.add_typer(model_app, name=\"model\")\n"
    content += "inspect_app.add_typer(promote_app, name=\"promote\")\n"
    content += "inspect_app.add_typer(postflight_app, name=\"postflight\")\n"
    content += "inspect_app.add_typer(goose_app, name=\"goose\")\n"
    content += "inspect_app.add_typer(code_vault_app, name=\"code-vault\")\n"
    open("builder_ii/cli/tui_inspection_cli.py", "w").write(content)
