"""MCP Server Backends - Query engines for different data sources."""

from mcp_server.backends.duckdb_parquet import DuckDBBackend

__all__ = ['DuckDBBackend']
