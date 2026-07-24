content = open("builder_ii/cli/main.py").read()
if "chain_app" not in content:
    content = content.replace(
        "self.add_lazy_command(\"builder_ii.cli.mcp_cli\", \"mcp_app\", \"mcp\")",
        "self.add_lazy_command(\"builder_ii.cli.mcp_cli\", \"mcp_app\", \"mcp\")\n        self.add_lazy_command(\"builder_ii.cli.chain_cli\", \"chain_app\", \"chain\")"
    )
open("builder_ii/cli/main.py", "w").write(content)
