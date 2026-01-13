"""Query Router - Dispatches queries to appropriate backends.

The router uses the dataset registry to determine which backend
to use for each dataset, then delegates query execution.

Usage:
    router = QueryRouter()
    results = router.query('adhd_prevalence_estimate',
                          'SELECT * FROM data LIMIT 10')
"""

from pathlib import Path
from typing import Any, Optional

from mcp_server.core.registry import DatasetRegistry

# Project root (parent of mcp_server)
PROJECT_ROOT = Path(__file__).parent.parent.parent


class QueryRouter:
    """Routes queries to the appropriate backend based on dataset config."""

    def __init__(self, registry: Optional[DatasetRegistry] = None):
        """Initialize router with dataset registry.

        Args:
            registry: DatasetRegistry instance (creates one if None)
        """
        self.registry = registry or DatasetRegistry()
        self.backends = {}  # Lazy-loaded backend instances

    def _get_backend(self, backend_name: str):
        """Get or create backend instance.

        Args:
            backend_name: Backend name from config

        Returns:
            Backend instance
        """
        if backend_name not in self.backends:
            backend_config = self.registry.get_backend_config(backend_name)
            backend_type = backend_config.get('type', 'duckdb')

            if backend_type == 'duckdb':
                from mcp_server.backends.duckdb_parquet import DuckDBBackend
                self.backends[backend_name] = DuckDBBackend(backend_config)
            elif backend_type == 'postgres':
                from mcp_server.backends.postgres import PostgresBackend
                self.backends[backend_name] = PostgresBackend(backend_config)
            else:
                raise ValueError(f"Unknown backend type: {backend_type}")

        return self.backends[backend_name]

    def _resolve_path(self, dataset_config: dict) -> str:
        """Resolve data source path for a dataset.

        Args:
            dataset_config: Dataset configuration

        Returns:
            Absolute path (for parquet) or table name (for postgres)
        """
        if 'path' in dataset_config:
            # Parquet file path
            path = dataset_config['path']
            if not Path(path).is_absolute():
                path = str(PROJECT_ROOT / path)
            return path
        elif 'table' in dataset_config:
            # PostgreSQL table
            return dataset_config['table']
        else:
            raise ValueError("Dataset config must have 'path' or 'table'")

    def query(self, dataset_code: str, sql: str) -> list[dict]:
        """Execute SQL query against a dataset.

        The SQL should use 'data' as the table name. The router
        resolves the actual data source and delegates to the backend.

        Args:
            dataset_code: Dataset code from registry
            sql: SQL query (use 'data' as table name)

        Returns:
            List of dicts (query results)
        """
        config = self.registry.get_dataset_config(dataset_code)
        backend_name = config.get('backend', 'duckdb_parquet')
        backend = self._get_backend(backend_name)
        source = self._resolve_path(config)

        return backend.execute(source, sql)

    def get_schema(self, dataset_code: str) -> list[dict]:
        """Get column schema for a dataset.

        Args:
            dataset_code: Dataset code

        Returns:
            List of column dicts with name and type
        """
        config = self.registry.get_dataset_config(dataset_code)
        backend_name = config.get('backend', 'duckdb_parquet')
        backend = self._get_backend(backend_name)
        source = self._resolve_path(config)

        return backend.get_schema(source)

    def get_stats(self, dataset_code: str) -> dict:
        """Get statistics for a dataset.

        Args:
            dataset_code: Dataset code

        Returns:
            Dict with row_count, column_count, etc.
        """
        config = self.registry.get_dataset_config(dataset_code)
        backend_name = config.get('backend', 'duckdb_parquet')
        backend = self._get_backend(backend_name)
        source = self._resolve_path(config)

        return backend.get_stats(source)

    def get_sample(self, dataset_code: str, n: int = 5) -> list[dict]:
        """Get sample rows from a dataset.

        Args:
            dataset_code: Dataset code
            n: Number of rows

        Returns:
            List of sample row dicts
        """
        config = self.registry.get_dataset_config(dataset_code)
        backend_name = config.get('backend', 'duckdb_parquet')
        backend = self._get_backend(backend_name)
        source = self._resolve_path(config)

        return backend.get_sample(source, n)
