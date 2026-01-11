"""MCP Server Core - Registry and routing logic."""

from mcp_server.core.router import QueryRouter
from mcp_server.core.registry import DatasetRegistry

__all__ = ['QueryRouter', 'DatasetRegistry']
