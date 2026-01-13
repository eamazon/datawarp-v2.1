"""DataWarp MCP Server - Enable agent querying of NHS data.

This server implements Model Context Protocol endpoints for Claude agents
to discover and query agent-ready NHS datasets.

v2.0: PostgreSQL-native - queries database directly (no parquet dependency)
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import date, datetime
from decimal import Decimal

import pandas as pd
import numpy as np
import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import database connection
from datawarp.storage.connection import get_connection


def make_json_safe(val):
    """Convert value to JSON-serializable format."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    elif pd.isna(val):
        return None
    elif hasattr(val, 'isoformat'):  # datetime, date, Timestamp, etc.
        return val.isoformat()
    elif isinstance(val, Decimal):
        return float(val)
    elif isinstance(val, (np.integer, np.int64)):
        return int(val)
    elif isinstance(val, (np.floating, np.float64)):
        return float(val) if not np.isnan(val) else None
    elif isinstance(val, (int, float, str, bool)):
        return val
    else:
        return str(val)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="DataWarp MCP Server", version="2.0.0")

# Mode: 'postgres' (default) or 'parquet' (legacy)
MCP_MODE = os.environ.get('MCP_MODE', 'postgres')

# Data directory (for legacy parquet mode)
DATA_DIR = Path(__file__).parent.parent / "output"
CATALOG_PATH = DATA_DIR / "catalog.parquet"


class MCPRequest(BaseModel):
    """MCP protocol request format."""
    method: str
    params: Dict[str, Any] = {}


class MCPResponse(BaseModel):
    """MCP protocol response format."""
    result: Any = None
    error: Optional[str] = None


def load_catalog() -> pd.DataFrame:
    """Load the catalog of available datasets from PostgreSQL or parquet."""
    if MCP_MODE == 'postgres':
        return load_catalog_from_postgres()
    else:
        return load_catalog_from_parquet()


def load_catalog_from_postgres() -> pd.DataFrame:
    """Load catalog directly from PostgreSQL registry."""
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
                ELSE 'other'
            END as domain
        FROM datawarp.tbl_data_sources s
        LEFT JOIN pg_stat_user_tables st
            ON st.relname = s.table_name AND st.schemaname = COALESCE(s.schema_name, 'staging')
        ORDER BY s.code
        """
        return pd.read_sql(query, conn)


def load_catalog_from_parquet() -> pd.DataFrame:
    """Legacy: Load catalog from parquet file."""
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(f"Catalog not found: {CATALOG_PATH}")
    return pd.read_parquet(CATALOG_PATH)


def load_dataset(source_code: str, limit: int = 10000) -> pd.DataFrame:
    """Load a specific dataset from PostgreSQL or parquet."""
    if MCP_MODE == 'postgres':
        return load_dataset_from_postgres(source_code, limit)
    else:
        return load_dataset_from_parquet(source_code)


def load_dataset_from_postgres(source_code: str, limit: int = 10000) -> pd.DataFrame:
    """Load dataset directly from PostgreSQL table."""
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


def load_dataset_from_parquet(source_code: str) -> pd.DataFrame:
    """Legacy: Load dataset from parquet file."""
    catalog = load_catalog_from_parquet()
    row = catalog[catalog['source_code'] == source_code]

    if len(row) == 0:
        raise ValueError(f"Dataset not found: {source_code}")

    file_path_str = row.iloc[0]['file_path']
    if file_path_str.startswith('output/'):
        file_path_str = file_path_str[7:]

    file_path = DATA_DIR / file_path_str
    if not file_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {file_path}")

    return pd.read_parquet(file_path)


def get_database_stats(source_codes: List[str]) -> Dict[str, Dict]:
    """Fetch live database stats for sources (row counts, freshness, load history).

    Args:
        source_codes: List of source codes to fetch stats for

    Returns:
        Dict mapping source_code to stats dict with keys:
        - db_row_count: Current rows in database table
        - db_size_mb: Table size in MB
        - last_loaded_at: Timestamp of most recent load
        - load_count: Total number of loads
        - table_exists: Whether table exists in database
    """
    if not source_codes:
        return {}

    try:
        with get_connection() as conn:
            cur = conn.cursor()

            # Build query to get stats for all requested sources
            placeholders = ','.join(['%s'] * len(source_codes))

            query = f"""
            SELECT
                s.code,
                COALESCE(st.n_live_tup, 0) as db_row_count,
                COALESCE(pg_total_relation_size('staging.' || s.table_name) / 1024.0 / 1024.0, 0)::numeric(10,2) as db_size_mb,
                s.last_load_at,
                COUNT(lh.id) as load_count
            FROM datawarp.tbl_data_sources s
            LEFT JOIN pg_stat_user_tables st
                ON st.relname = s.table_name AND st.schemaname = 'staging'
            LEFT JOIN datawarp.tbl_load_history lh
                ON lh.source_id = s.id
            WHERE s.code IN ({placeholders})
            GROUP BY s.code, s.table_name, st.n_live_tup, s.last_load_at
            """

            cur.execute(query, source_codes)
            rows = cur.fetchall()
            cur.close()

            # Build result dict
            stats = {}
            for row in rows:
                source_code, db_rows, db_size, last_load, load_count = row
                stats[source_code] = {
                    'db_row_count': int(db_rows) if db_rows else 0,
                    'db_size_mb': float(db_size) if db_size else 0.0,
                    'last_loaded_at': last_load.isoformat() if last_load else None,
                    'load_count': int(load_count),
                    'table_exists': db_rows is not None and db_rows > 0
                }

            return stats

    except Exception as e:
        logger.warning(f"Failed to fetch database stats: {e}")
        return {}


def get_dataset_metadata(source_code: str) -> Dict:
    """Get metadata for a dataset including enrichment metadata from database."""
    # Load dataset schema from PostgreSQL
    with get_connection() as conn:
        # Get source metadata from registry
        cur = conn.cursor()
        cur.execute("""
            SELECT code, name, description, metadata, domain, tags, table_name, schema_name
            FROM datawarp.tbl_data_sources
            WHERE code = %s
        """, (source_code,))
        source_row = cur.fetchone()

        if not source_row:
            return {"error": f"Source '{source_code}' not found"}

        code, name, description, metadata, domain, tags, table_name, schema_name = source_row
        # PostgreSQL JSONB returns as dict already, no need to parse

        # Get actual table stats and column info
        cur.execute(f"""
            SELECT *
            FROM {schema_name}.{table_name}
            LIMIT 3
        """)

        # Get column names and sample values
        columns = []
        if cur.description:
            sample_rows = cur.fetchall()
            for i, col_desc in enumerate(cur.description):
                col_name = col_desc[0]
                # Get sample values from the 3 rows
                sample_values = [make_json_safe(row[i]) for row in sample_rows if row]

                col_info = {
                    "name": col_name,
                    "type": str(col_desc[1]),
                    "sample_values": sample_values[:3]
                }
                columns.append(col_info)

        # Get row count
        cur.execute(f"SELECT COUNT(*) FROM {schema_name}.{table_name}")
        row_count = cur.fetchone()[0]

    # Extract source file info from metadata for top-level access
    source_files = metadata.get('source_files', []) if metadata else []
    if source_files:
        first_file = source_files[0]
        source_url = first_file.get('url')
        source_period = first_file.get('period')
        source_sheet = first_file.get('sheet')
        source_extract = first_file.get('extract')  # File extracted from ZIP
    else:
        source_url = source_period = source_sheet = source_extract = None

    return {
        "source_code": code,
        "name": name,
        "description": description or f"DataWarp source: {code}",
        "source_url": source_url,
        "source_period": source_period,
        "source_sheet": source_sheet,
        "source_extract": source_extract,
        "domain": domain,
        "tags": tags or [],
        "metadata": metadata,
        "row_count": row_count,
        "column_count": len(columns),
        "columns": columns
    }


@app.post("/mcp")
async def handle_mcp_request(request: MCPRequest) -> MCPResponse:
    """Handle MCP protocol requests."""
    try:
        logger.info(f"MCP Request: {request.method} with params: {request.params}")

        if request.method == "list_datasets":
            return handle_list_datasets(request.params)

        elif request.method == "query":
            return handle_query(request.params)

        elif request.method == "get_metadata":
            return handle_get_metadata(request.params)

        else:
            return MCPResponse(error=f"Unknown method: {request.method}")

    except Exception as e:
        logger.error(f"Error handling request: {e}", exc_info=True)
        return MCPResponse(error=str(e))


def handle_list_datasets(params: Dict) -> MCPResponse:
    """List available datasets with optional filtering and live database stats."""
    catalog = load_catalog()

    # Apply domain filter (match against source_code patterns)
    if 'domain' in params:
        domain = params['domain'].lower()
        # Map domain names to source_code patterns
        domain_patterns = {
            'adhd': ['adhd'],
            'pcn workforce': ['pcn', 'workforce'],
            'pcn': ['pcn'],
            'workforce': ['workforce'],
            'gp practice': ['gp_', 'practice'],
            'gp': ['gp_'],
            'online consultation': ['oc_', 'consultation'],
            'mental health': ['mental_health', 'mhsds'],
            'waiting times': ['wait', 'rtt'],
            'dementia': ['dementia'],
        }
        patterns = domain_patterns.get(domain, [domain])
        mask = catalog['source_code'].str.lower().apply(
            lambda x: any(p in x for p in patterns)
        )
        catalog = catalog[mask]

    if 'min_rows' in params:
        catalog = catalog[catalog['row_count'] >= params['min_rows']]

    if 'keyword' in params:
        keyword = params['keyword'].lower()
        catalog = catalog[
            catalog['source_code'].str.contains(keyword, case=False) |
            catalog['description'].str.contains(keyword, case=False)
        ]

    # Limit results
    limit = params.get('limit', 20)
    catalog = catalog.head(limit)

    # Optionally fetch live database stats
    include_stats = params.get('include_stats', False)
    db_stats = {}
    if include_stats:
        source_codes = catalog['source_code'].tolist()
        db_stats = get_database_stats(source_codes)

    # Format response
    datasets = []
    for _, row in catalog.iterrows():
        # Build date range string
        min_date = make_json_safe(row.get('min_date'))
        max_date = make_json_safe(row.get('max_date'))
        if min_date and max_date:
            date_range = f"{min_date} to {max_date}"
        elif min_date:
            date_range = f"from {min_date}"
        elif max_date:
            date_range = f"to {max_date}"
        else:
            date_range = "N/A"

        dataset = {
            "code": row['source_code'],
            "domain": row.get('domain', ''),
            "description": row.get('description', ''),
            "rows": int(row['row_count']),
            "columns": int(row['column_count']),
            "file_size_kb": float(row.get('file_size_kb', 0)),
            "date_range": date_range
        }

        # Add database stats if requested
        if include_stats and row['source_code'] in db_stats:
            stats = db_stats[row['source_code']]
            dataset['db_stats'] = {
                "row_count": stats['db_row_count'],
                "size_mb": stats['db_size_mb'],
                "last_loaded": stats['last_loaded_at'],
                "load_count": stats['load_count'],
                "exists": stats['table_exists']
            }

        datasets.append(dataset)

    return MCPResponse(result={
        "total_found": len(catalog),
        "datasets": datasets,
        "includes_db_stats": include_stats
    })


def handle_get_metadata(params: Dict) -> MCPResponse:
    """Get detailed metadata for a dataset."""
    if 'dataset' not in params:
        return MCPResponse(error="Missing required parameter: dataset")

    metadata = get_dataset_metadata(params['dataset'])
    return MCPResponse(result=metadata)


def handle_query(params: Dict) -> MCPResponse:
    """Execute a natural language query against a dataset.

    For prototype, we do simple aggregations. In production, use LLM to generate pandas code.
    """
    if 'dataset' not in params:
        return MCPResponse(error="Missing required parameter: dataset")

    if 'question' not in params:
        return MCPResponse(error="Missing required parameter: question")

    dataset_code = params['dataset']
    question = params['question'].lower()

    # Load dataset
    df = load_dataset(dataset_code)

    # Simple query interpretation (prototype level)
    # In production, use LLM to generate pandas code

    result_data = None
    query_description = ""

    # Pattern: "show me..." or "what is..."
    if 'group by' in question or 'by age' in question or 'by geography' in question:
        # Try to find group column
        group_cols = [c for c in df.columns if not c.startswith('_')]
        if group_cols:
            group_col = group_cols[0]  # Use first business column
            numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
            if len(numeric_cols) > 0:
                result_data = df.groupby(group_col)[numeric_cols[0]].sum().reset_index()
                query_description = f"Grouped by {group_col}, summed {numeric_cols[0]}"

    # Pattern: "count" or "how many"
    elif 'count' in question or 'how many' in question:
        result_data = pd.DataFrame([{"total_rows": len(df)}])
        query_description = "Row count"

    # Default: return first 10 rows
    else:
        result_data = df.head(10)
        query_description = "First 10 rows"

    # Convert to JSON-serializable format
    if result_data is not None:
        result_json = result_data.to_dict(orient='records')
    else:
        result_json = []

    return MCPResponse(result={
        "rows": result_json,
        "row_count": len(result_json),
        "query_description": query_description,
        "total_dataset_rows": len(df),
        "note": "Prototype query engine - production version will use LLM for complex queries"
    })


@app.get("/")
async def root():
    """Health check endpoint."""
    try:
        catalog = load_catalog()
        dataset_count = len(catalog)
    except Exception as e:
        logger.warning(f"Failed to load catalog: {e}")
        dataset_count = 0

    return {
        "service": "DataWarp MCP Server",
        "status": "running",
        "version": "2.0.0",
        "mode": MCP_MODE,
        "catalog_datasets": dataset_count
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
