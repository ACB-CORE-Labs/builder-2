"""Governed MCP interposition adapter (G1).

A hand-rolled, standard-library-only stdio JSON-RPC MCP server that Goose can load as an
extension. It exposes only the executor's already allowlisted read-only stub tools and runs
every call through the existing governed ceremony (policy + envelope -> receipt -> chained
event record). It introduces no new tool capability and grants no authority.
"""
