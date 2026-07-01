import json
from typer.testing import CliRunner
from builder_ii.mcp_cli import mcp_app

runner = CliRunner()

def test_mcp_inventory():
    result = runner.invoke(mcp_app, ["inventory"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "servers" in data

def test_mcp_policy():
    result = runner.invoke(mcp_app, ["policy"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "allowed_servers" in data
