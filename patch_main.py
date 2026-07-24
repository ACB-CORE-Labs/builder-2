content = open("builder_ii/cli/main.py").read()

lines_to_remove = [
    "self.add_lazy_command(\"builder_ii.cli.tui_inspection_cli\", \"hitl_app\", \"hitl\")",
    "self.add_lazy_command(\"builder_ii.cli.tui_inspection_cli\", \"profile_app\", \"profile\")",
    "self.add_lazy_command(\"builder_ii.cli.tui_inspection_cli\", \"model_app\", \"model\")",
    "self.add_lazy_command(\"builder_ii.cli.tui_inspection_cli\", \"promote_app\", \"promote\")",
    "self.add_lazy_command(\"builder_ii.cli.tui_inspection_cli\", \"postflight_app\", \"postflight\")",
    "self.add_lazy_command(\"builder_ii.cli.tui_inspection_cli\", \"goose_app\", \"goose\")",
    "self.add_lazy_command(\"builder_ii.cli.tui_inspection_cli\", \"code_vault_app\", \"code-vault\")"
]

for l in lines_to_remove:
    content = content.replace(f"        {l}\n", "")

if "inspect_app" not in content:
    content = content.replace(
        "self.add_lazy_command(\"builder_ii.cli.mcp_cli\", \"mcp_app\", \"mcp\")",
        "self.add_lazy_command(\"builder_ii.cli.mcp_cli\", \"mcp_app\", \"mcp\")\n        self.add_lazy_command(\"builder_ii.cli.tui_inspection_cli\", \"inspect_app\", \"inspect\")"
    )
open("builder_ii/cli/main.py", "w").write(content)
