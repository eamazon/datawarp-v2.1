"""PostgreSQL backend for MCP server - queries database directly."""

import sys
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional

# Add project to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from datawarp.storage.connection import get_connection


class PostgreSQLBackend:
    """Backend that queries PostgreSQL directly for catalog and data."""

    def __init__(self, config: Dict = None):
        """Initialize PostgreSQL backend."""
        self.config = config or {}

    def load_catalog(self) -> pd.DataFrame:
        """Load catalog from PostgreSQL registry."""
        with get_connection() as conn:
            query = """
            SELECT
                s.code as source_code,
                s.name as description,
                COALESCE(s.schema_name, 'staging') as schema_name,
                s.table_name,
                COALESCE(st.n_live_tup, 0) as row_count,
                (SELECT COUNT(*) FROM information_schema.columns c
                 WHERE c.table_schema = COALESCE(s.schema_name, 'staging')
                 AND c.table_name = s.table_name) as column_count,
                s.last_load_at,
                CASE
                    WHEN s.code LIKE 'adhd%' THEN 'mental_health'
                    WHEN s.code LIKE 'gp%' THEN 'primary_care'
                    WHEN s.code LIKE 'pcn%' THEN 'workforce'
                    WHEN s.code LIKE 'oc%' OR s.code LIKE '%consultation%' THEN 'digital_services'
                    WHEN s.code LIKE 'mhsds%' THEN 'mental_health'
                    ELSE 'other'
                END as domain,
                s.metadata,
                s.domain as custom_domain,
                s.tags
            FROM datawarp.tbl_data_sources s
            LEFT JOIN pg_stat_user_tables st
                ON st.relname = s.table_name AND st.schemaname = COALESCE(s.schema_name, 'staging')
            WHERE COALESCE(st.n_live_tup, 0) > 0
            ORDER BY s.code
            """
            return pd.read_sql(query, conn)

    def load_dataset(self, source_code: str, limit: int = 10000) -> pd.DataFrame:
        """Load dataset from PostgreSQL table."""
        with get_connection() as conn:
            # Get table info from registry
            cur = conn.cursor()
            cur.execute("""
                SELECT COALESCE(schema_name, 'staging'), table_name
                FROM datawarp.tbl_data_sources
                WHERE code = %s
            """, (source_code,))
            row = cur.fetchone()
            cur.close()

            if not row:
                raise ValueError(f"Dataset not found: {source_code}")

            schema, table = row
            full_table = f"{schema}.{table}"

            # Query with limit
            query = f"SELECT * FROM {full_table} LIMIT {limit}"
            return pd.read_sql(query, conn)

    def execute_sql(self, sql: str) -> pd.DataFrame:
        """Execute arbitrary SQL query."""
        with get_connection() as conn:
            return pd.read_sql(sql, conn)

    def get_dataset_metadata(self, source_code: str) -> Dict:
        """Get detailed metadata for a dataset."""
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    code,
                    name,
                    description,
                    metadata,
                    domain,
                    tags,
                    table_name,
                    schema_name,
                    last_load_at
                FROM datawarp.tbl_data_sources
                WHERE code = %s
            """, (source_code,))
            row = cur.fetchone()

            if not row:
                return {"error": f"Source '{source_code}' not found"}

            code, name, description, metadata, domain, tags, table_name, schema_name, last_load_at = row

            # Get column info
            schema = schema_name or 'staging'
            cur.execute(f"""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
            """, (schema, table_name))

            columns = []
            for col_name, col_type in cur.fetchall():
                columns.append({
                    "name": col_name,
                    "type": col_type
                })

            # Get row count
            cur.execute(f"SELECT COUNT(*) FROM {schema}.{table_name}")
            row_count = cur.fetchone()[0]

            cur.close()

            return {
                "source_code": code,
                "name": name,
                "description": description or f"DataWarp source: {code}",
                "domain": domain,
                "tags": tags or [],
                "metadata": metadata or {},
                "row_count": row_count,
                "column_count": len(columns),
                "columns": columns,
                "last_load_at": last_load_at.isoformat() if last_load_at else None
            }
