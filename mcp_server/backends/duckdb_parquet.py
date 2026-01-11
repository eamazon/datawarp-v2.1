"""DuckDB backend for querying Parquet files.

This backend uses DuckDB to query Parquet files directly without loading
them fully into memory. DuckDB handles type inference, column pruning,
and predicate pushdown automatically.

Usage:
    backend = DuckDBBackend({'base_path': 'output/'})
    results = backend.execute('output/adhd_prevalence.parquet',
                              'SELECT * FROM data WHERE age_band = "0-17" LIMIT 10')
"""

import duckdb
from pathlib import Path
from typing import Any
import json


class DuckDBBackend:
    """Query Parquet files using DuckDB."""

    def __init__(self, config: dict):
        """Initialize DuckDB backend.

        Args:
            config: Backend configuration with optional 'base_path'
        """
        self.base_path = config.get('base_path', 'output/')
        self.conn = duckdb.connect(':memory:')
        # Enable progress bar for long queries
        self.conn.execute("SET enable_progress_bar = false")

    def execute(self, parquet_path: str, sql: str) -> list[dict]:
        """Execute SQL against a parquet file.

        The SQL should use 'data' as the table name. This method creates
        a view pointing to the parquet file and executes the query.

        Args:
            parquet_path: Path to the parquet file (absolute or relative)
            sql: SQL query using 'data' as table name

        Returns:
            List of dicts (one per row)

        Example:
            backend.execute('output/adhd.parquet',
                          'SELECT age_band, COUNT(*) as cnt FROM data GROUP BY age_band')
        """
        # Ensure path exists
        path = Path(parquet_path)
        if not path.exists():
            raise FileNotFoundError(f"Parquet file not found: {parquet_path}")

        # Register parquet as 'data' view
        self.conn.execute(f"CREATE OR REPLACE VIEW data AS SELECT * FROM '{parquet_path}'")

        # Execute query and convert to pandas then to dicts
        result = self.conn.execute(sql).fetchdf()

        # Convert to list of dicts, handling special types
        return self._df_to_dicts(result)

    def _df_to_dicts(self, df) -> list[dict]:
        """Convert DataFrame to list of dicts with JSON-safe values."""
        import pandas as pd

        rows = []
        for _, row in df.iterrows():
            row_dict = {}
            for col, val in row.items():
                if pd.isna(val):
                    row_dict[col] = None
                elif hasattr(val, 'isoformat'):  # datetime-like
                    row_dict[col] = val.isoformat()
                elif isinstance(val, (int, float, str, bool, type(None))):
                    row_dict[col] = val
                else:
                    row_dict[col] = str(val)
            rows.append(row_dict)
        return rows

    def get_schema(self, parquet_path: str) -> list[dict]:
        """Get column names and types from parquet file.

        Args:
            parquet_path: Path to the parquet file

        Returns:
            List of dicts with 'name' and 'type' keys
        """
        path = Path(parquet_path)
        if not path.exists():
            raise FileNotFoundError(f"Parquet file not found: {parquet_path}")

        self.conn.execute(f"CREATE OR REPLACE VIEW data AS SELECT * FROM '{parquet_path}'")
        result = self.conn.execute("DESCRIBE data").fetchall()

        return [
            {"name": row[0], "type": row[1]}
            for row in result
        ]

    def get_sample(self, parquet_path: str, n: int = 5) -> list[dict]:
        """Get sample rows from parquet file.

        Args:
            parquet_path: Path to the parquet file
            n: Number of sample rows (default: 5)

        Returns:
            List of dicts (sample rows)
        """
        return self.execute(parquet_path, f"SELECT * FROM data LIMIT {n}")

    def get_stats(self, parquet_path: str) -> dict:
        """Get basic statistics about the parquet file.

        Args:
            parquet_path: Path to the parquet file

        Returns:
            Dict with row_count, column_count, file_size_kb
        """
        path = Path(parquet_path)
        if not path.exists():
            raise FileNotFoundError(f"Parquet file not found: {parquet_path}")

        self.conn.execute(f"CREATE OR REPLACE VIEW data AS SELECT * FROM '{parquet_path}'")

        count = self.conn.execute("SELECT COUNT(*) FROM data").fetchone()[0]

        # Get column count from schema
        schema = self.get_schema(parquet_path)

        # Get file size
        file_size_kb = path.stat().st_size / 1024

        return {
            "row_count": count,
            "column_count": len(schema),
            "file_size_kb": round(file_size_kb, 2)
        }

    def get_distinct_values(self, parquet_path: str, column: str, limit: int = 20) -> list:
        """Get distinct values for a column.

        Args:
            parquet_path: Path to the parquet file
            column: Column name
            limit: Max distinct values to return

        Returns:
            List of distinct values
        """
        result = self.execute(
            parquet_path,
            f"SELECT DISTINCT \"{column}\" FROM data ORDER BY \"{column}\" LIMIT {limit}"
        )
        return [row[column] for row in result]

    def get_column_stats(self, parquet_path: str, column: str) -> dict:
        """Get statistics for a specific column.

        Args:
            parquet_path: Path to the parquet file
            column: Column name

        Returns:
            Dict with null_count, distinct_count, min, max (if numeric)
        """
        self.conn.execute(f"CREATE OR REPLACE VIEW data AS SELECT * FROM '{parquet_path}'")

        # Basic stats
        result = self.conn.execute(f"""
            SELECT
                COUNT(*) as total,
                COUNT("{column}") as non_null,
                COUNT(DISTINCT "{column}") as distinct_count
            FROM data
        """).fetchone()

        stats = {
            "total_rows": result[0],
            "non_null_count": result[1],
            "null_count": result[0] - result[1],
            "distinct_count": result[2]
        }

        # Try to get min/max for numeric columns
        try:
            minmax = self.conn.execute(f"""
                SELECT MIN("{column}"), MAX("{column}") FROM data
            """).fetchone()
            stats["min"] = minmax[0]
            stats["max"] = minmax[1]
        except Exception:
            pass  # Not numeric

        return stats
