#!/usr/bin/env python3
"""DataWarp MCP Server - Using official MCP SDK with PostgreSQL backend."""

import sys
import logging
from pathlib import Path
from datetime import date, datetime

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from mcp_server.backends.postgres import PostgreSQLBackend


def make_json_safe(val):
    """Convert value to JSON-serializable format."""
    if val is None or pd.isna(val):
        return None
    elif hasattr(val, 'isoformat'):  # datetime, date, Timestamp, etc.
        return val.isoformat()
    elif isinstance(val, (np.integer, np.int64)):
        return int(val)
    elif isinstance(val, (np.floating, np.float64)):
        return float(val) if not np.isnan(val) else None
    elif isinstance(val, (int, float, str, bool)):
        return val
    else:
        return str(val)

# Configure logging to stderr (stdout is reserved for MCP protocol)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Create MCP server
app = Server("datawarp-nhs")

# Initialize PostgreSQL backend
backend = PostgreSQLBackend()


def load_catalog() -> pd.DataFrame:
    """Load the catalog of available datasets."""
    return backend.load_catalog()


def load_dataset(source_code: str, limit: int = 10000) -> pd.DataFrame:
    """Load a specific dataset by source code."""
    return backend.load_dataset(source_code, limit)


def generate_sql_from_question(question: str, df: pd.DataFrame) -> tuple[str, str]:
    """Generate SQL from natural language question.

    Returns: (sql_query, description)
    """
    question_lower = question.lower()

    # Simple pattern matching for common queries
    if 'count' in question_lower or 'how many' in question_lower:
        return "SELECT COUNT(*) as count FROM data", "Row count"

    elif 'sum' in question_lower or 'total' in question_lower:
        # Try to find numeric columns
        numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
        if len(numeric_cols) > 0:
            col = numeric_cols[0]
            return f"SELECT SUM(\"{col}\") as total FROM data", f"Sum of {col}"

    elif 'average' in question_lower or 'mean' in question_lower or 'avg' in question_lower:
        numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
        if len(numeric_cols) > 0:
            col = numeric_cols[0]
            return f"SELECT AVG(\"{col}\") as average FROM data", f"Average of {col}"

    elif 'group by' in question_lower or 'by age' in question_lower or 'by month' in question_lower:
        # Try to find grouping column
        for col in df.columns:
            if 'age' in col.lower() or 'band' in col.lower() or 'group' in col.lower():
                numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
                if len(numeric_cols) > 0:
                    measure = numeric_cols[0]
                    return f"SELECT \"{col}\", SUM(\"{measure}\") as total FROM data GROUP BY \"{col}\"", f"Aggregated by {col}"

    elif 'distinct' in question_lower or 'unique' in question_lower:
        # Find first text column
        text_cols = df.select_dtypes(include=['object']).columns
        if len(text_cols) > 0:
            col = text_cols[0]
            return f"SELECT DISTINCT \"{col}\" FROM data ORDER BY \"{col}\"", f"Distinct values of {col}"

    # Default: return all rows (with safety limit)
    return "SELECT * FROM data LIMIT 1000", "All rows (limited to 1000)"


def validate_sql_query(sql: str, df: pd.DataFrame) -> tuple[bool, str]:
    """Validate SQL query before execution.

    Returns: (is_valid, error_message)
    """
    # Check 1: Empty dataframe
    if df is None or len(df) == 0:
        return False, "Dataset is empty"

    # Check 2: Column name validation
    import re
    column_refs = re.findall(r'"([^"]+)"', sql)
    missing_cols = [col for col in column_refs if col not in df.columns and col != 'data']
    if missing_cols:
        return False, f"Columns not found: {', '.join(missing_cols)}"

    # Check 3: Query has LIMIT (prevent memory issues)
    if 'SELECT' in sql.upper() and 'LIMIT' not in sql.upper():
        logger.warning("Query missing LIMIT clause, this may be expensive")

    # Check 4: Basic SQL injection prevention (shouldn't happen but paranoia)
    dangerous_keywords = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE']
    if any(keyword in sql.upper() for keyword in dangerous_keywords):
        return False, "Query contains potentially dangerous SQL keywords"

    return True, ""


def execute_sql_with_duckdb(df: pd.DataFrame, sql: str) -> list[dict]:
    """Execute SQL query against DataFrame using DuckDB.

    Args:
        df: DataFrame to query
        sql: SQL query using 'data' as table name

    Returns:
        List of result rows as dicts
    """
    import duckdb

    # Register DataFrame as 'data' table
    conn = duckdb.connect(':memory:')
    conn.register('data', df)

    # Execute query
    result = conn.execute(sql).fetchdf()
    conn.close()

    # Convert to list of dicts with JSON-safe values
    rows = []
    for _, row in result.iterrows():
        row_dict = {}
        for col, val in row.items():
            row_dict[col] = make_json_safe(val)
        rows.append(row_dict)

    return rows


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="list_datasets",
            description="List available NHS datasets with optional filtering by domain or keyword",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Filter by domain/topic: ADHD, PCN Workforce, GP Practice, Online Consultation, Mental Health, Waiting Times"
                    },
                    "keyword": {
                        "type": "string",
                        "description": "Filter datasets by keyword in code or description"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of results to return (default: 20)"
                    }
                }
            }
        ),
        Tool(
            name="get_metadata",
            description="Get detailed metadata for a specific dataset including column types and sample values",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset": {
                        "type": "string",
                        "description": "Dataset source code (e.g., 'practice_oc_submissions')"
                    }
                },
                "required": ["dataset"]
            }
        ),
        Tool(
            name="get_schema",
            description="Get dataset schema with column names, types, statistics and suggested queries. Use this before writing SQL queries.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset": {
                        "type": "string",
                        "description": "Dataset source code"
                    }
                },
                "required": ["dataset"]
            }
        ),
        Tool(
            name="query",
            description="Execute a query against a dataset. Supports natural language questions OR SQL queries (use 'data' as table name in SQL).",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset": {
                        "type": "string",
                        "description": "Dataset source code to query"
                    },
                    "question": {
                        "type": "string",
                        "description": "Natural language question OR SQL query (using 'data' as table name)"
                    }
                },
                "required": ["dataset", "question"]
            }
        ),
        Tool(
            name="discover_by_keyword",
            description="Discover datasets by searching column-level metadata. More powerful than list_datasets - searches actual KPIs and dimensions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Keywords to search (e.g., ['waiting', 'time'], ['prevalence', 'adhd'])"
                    }
                },
                "required": ["keywords"]
            }
        ),
        Tool(
            name="get_kpis",
            description="Get all available KPIs (metrics/measures) for a dataset with their descriptions and properties.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset": {
                        "type": "string",
                        "description": "Dataset source code"
                    }
                },
                "required": ["dataset"]
            }
        ),
        Tool(
            name="query_metric",
            description="Query a specific metric/KPI from a dataset with optional filters. Easier than writing SQL - just specify the metric name.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset": {
                        "type": "string",
                        "description": "Dataset source code"
                    },
                    "metric": {
                        "type": "string",
                        "description": "Column name of the KPI to query (use get_kpis to see available metrics)"
                    },
                    "filters": {
                        "type": "object",
                        "description": "Optional filters as column:value pairs (e.g., {'age_band': '18-64', 'period': '2024-Q3'})"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum rows to return (default: 100)"
                    }
                },
                "required": ["dataset", "metric"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    logger.info(f"Tool called: {name} with args: {arguments}")

    try:
        if name == "list_datasets":
            catalog = load_catalog()

            # Apply domain filter (match against source_code patterns)
            if 'domain' in arguments:
                domain = arguments['domain'].lower()
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

            # Apply keyword filter
            if 'keyword' in arguments:
                keyword = arguments['keyword'].lower()
                catalog = catalog[
                    catalog['source_code'].str.contains(keyword, case=False) |
                    catalog['description'].str.contains(keyword, case=False, na=False)
                ]

            # Limit results
            limit = arguments.get('limit', 20)
            catalog = catalog.head(int(limit))

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

                datasets.append({
                    "code": row['source_code'],
                    "description": row.get('description', ''),
                    "rows": int(row['row_count']),
                    "columns": int(row['column_count']),
                    "date_range": date_range
                })

            result = {
                "total_found": len(datasets),
                "datasets": datasets
            }

        elif name == "get_metadata":
            if 'dataset' not in arguments:
                raise ValueError("Missing required parameter: dataset")

            source_code = arguments['dataset']

            # Get metadata from PostgreSQL backend
            result = backend.get_dataset_metadata(source_code)

            # Add sample values for first 3 columns
            df = load_dataset(source_code, limit=3)
            for col_info in result.get('columns', [])[:5]:  # Only first 5 columns
                col_name = col_info['name']
                if col_name in df.columns:
                    sample_values = [make_json_safe(val) for val in df[col_name].head(3)]
                    col_info['sample_values'] = sample_values

        elif name == "get_schema":
            if 'dataset' not in arguments:
                raise ValueError("Missing required parameter: dataset")

            source_code = arguments['dataset']

            # Get metadata from PostgreSQL
            metadata = backend.get_dataset_metadata(source_code)

            # Load sample to infer column types
            df = load_dataset(source_code, limit=100)

            # Identify column types for query suggestions
            numeric_cols = df.select_dtypes(include=['int64', 'float64', 'int32', 'float32']).columns.tolist()
            text_cols = df.select_dtypes(include=['object']).columns.tolist()
            date_cols = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()]

            # Generate suggested queries
            suggested_queries = []
            if numeric_cols:
                suggested_queries.append(f"SELECT SUM(\"{numeric_cols[0]}\") as total FROM data")
            if text_cols:
                suggested_queries.append(f"SELECT DISTINCT \"{text_cols[0]}\" FROM data ORDER BY 1")
            if date_cols and numeric_cols:
                suggested_queries.append(f"SELECT \"{date_cols[0]}\", SUM(\"{numeric_cols[0]}\") as total FROM data GROUP BY 1 ORDER BY 1")

            result = {
                "source_code": source_code,
                "description": metadata.get('description', ''),
                "row_count": metadata['row_count'],
                "column_count": metadata['column_count'],
                "columns": metadata['columns'],
                "numeric_columns": numeric_cols,
                "text_columns": text_cols,
                "date_columns": date_cols,
                "suggested_queries": suggested_queries
            }

        elif name == "query":
            if 'dataset' not in arguments:
                raise ValueError("Missing required parameter: dataset")
            if 'question' not in arguments:
                raise ValueError("Missing required parameter: question")

            dataset_code = arguments['dataset']
            question = arguments['question']

            # Load dataset from PostgreSQL
            df = load_dataset(dataset_code, limit=10000)

            # Determine if question is SQL or natural language
            question_lower = question.lower().strip()
            is_sql = question_lower.startswith('select ') or 'from data' in question_lower

            try:
                if is_sql:
                    # Direct SQL execution
                    sql = question
                    query_description = "SQL query"
                    logger.info(f"Executing SQL: {sql}")
                else:
                    # Generate SQL from natural language
                    sql, query_description = generate_sql_from_question(question, df)
                    logger.info(f"Generated SQL: {sql}")

                # Validate SQL before execution
                is_valid, error_msg = validate_sql_query(sql, df)
                if not is_valid:
                    result = {
                        "error": "Query validation failed",
                        "details": error_msg,
                        "sql_attempted": sql,
                        "suggestion": "Check column names and query structure"
                    }
                    # Don't execute - return error result
                    import json
                    return [TextContent(
                        type="text",
                        text=json.dumps(result, indent=2)
                    )]

                # Execute with DuckDB (hybrid approach)
                rows = execute_sql_with_duckdb(df, sql)

                # Safety limit: prevent memory issues with huge results
                MAX_ROWS = 10000
                if len(rows) > MAX_ROWS:
                    logger.warning(f"Result truncated from {len(rows)} to {MAX_ROWS} rows")
                    rows = rows[:MAX_ROWS]
                    query_description += f" (truncated to {MAX_ROWS} rows)"

                result = {
                    "rows": rows,
                    "row_count": len(rows),
                    "query_description": query_description,
                    "sql_executed": sql,
                    "backend": "postgresql+duckdb"
                }

            except Exception as e:
                # Fallback to simple pandas operations
                logger.warning(f"SQL query failed: {e}, falling back to pandas")

                if 'count' in question_lower or 'how many' in question_lower:
                    rows = [{"count": len(df)}]
                    query_description = "Row count (pandas fallback)"
                else:
                    result_data = df.head(100)
                    # Convert to JSON-serializable format
                    rows = []
                    for _, row in result_data.iterrows():
                        row_dict = {}
                        for col, val in row.items():
                            row_dict[col] = make_json_safe(val)
                        rows.append(row_dict)
                    query_description = "First 100 rows (pandas fallback)"

                result = {
                    "rows": rows,
                    "row_count": len(rows),
                    "query_description": query_description,
                    "fallback_used": True,
                    "error": str(e)
                }

        elif name == "discover_by_keyword":
            keywords = arguments.get('keywords', [])
            if not keywords:
                raise ValueError("Keywords parameter is required")

            # Search column metadata for matching query_keywords
            with backend.config or {}:
                from datawarp.storage.connection import get_connection
                with get_connection() as conn:
                    cur = conn.cursor()

                    # Search in column metadata query_keywords (array column)
                    placeholders = ' OR '.join(['%s = ANY(query_keywords)'] * len(keywords))
                    query = f"""
                        SELECT DISTINCT canonical_source_code, COUNT(*) as match_count
                        FROM datawarp.tbl_column_metadata
                        WHERE {placeholders}
                        GROUP BY canonical_source_code
                        ORDER BY match_count DESC
                        LIMIT 50
                    """
                    cur.execute(query, keywords)
                    matching_sources = [row[0] for row in cur.fetchall()]

                    if not matching_sources:
                        result = {
                            "datasets": [],
                            "message": f"No datasets found matching keywords: {keywords}",
                            "suggestion": "Try broader keywords or use list_datasets to see all available data"
                        }
                    elif len(matching_sources) > 20:
                        # Too many results - ask user to be more specific
                        result = {
                            "datasets": [],
                            "message": f"Found {len(matching_sources)} datasets matching {keywords}. Please be more specific.",
                            "suggestion": "Try adding more keywords to narrow down results",
                            "sample_matches": matching_sources[:10]
                        }
                    else:
                        # Get full details for matching datasets
                        source_placeholders = ','.join(['%s'] * len(matching_sources))
                        details_query = f"""
                            SELECT
                                s.code,
                                s.name,
                                s.description,
                                s.metadata->>'measure_count' as kpi_count,
                                s.metadata->>'dimension_count' as dimension_count,
                                s.metadata
                            FROM datawarp.tbl_data_sources s
                            WHERE s.code IN ({source_placeholders})
                        """
                        cur.execute(details_query, matching_sources)

                        datasets = []
                        for row in cur.fetchall():
                            ds = {
                                "source_code": row[0],
                                "name": row[1],
                                "description": row[2],
                                "kpi_count": row[3],
                                "dimension_count": row[4]
                            }
                            # Add typical queries if available
                            if row[5] and 'typical_queries' in row[5]:
                                ds['typical_queries'] = row[5]['typical_queries']
                            datasets.append(ds)

                        result = {
                            "datasets": datasets,
                            "keywords_searched": keywords,
                            "match_count": len(datasets)
                        }

        elif name == "get_kpis":
            dataset = arguments.get('dataset')
            if not dataset:
                raise ValueError("Dataset parameter is required")

            # Get metadata from PostgreSQL
            metadata = backend.get_dataset_metadata(dataset)

            if not metadata.get('metadata'):
                result = {
                    "dataset": dataset,
                    "kpis": [],
                    "message": "No enriched metadata available for this dataset"
                }
            else:
                md = metadata['metadata']
                kpis = md.get('kpis', [])

                result = {
                    "dataset": dataset,
                    "dataset_name": metadata.get('name'),
                    "kpis": kpis,
                    "kpi_count": len(kpis),
                    "dimensions_available": md.get('dimensions', []),
                    "organizational_lenses": md.get('organizational_lenses', {}),
                    "typical_queries": md.get('typical_queries', [])
                }

        elif name == "query_metric":
            dataset = arguments.get('dataset')
            metric = arguments.get('metric')
            filters = arguments.get('filters', {})
            limit = arguments.get('limit', 100)

            if not dataset or not metric:
                raise ValueError("Both dataset and metric parameters are required")

            # Load dataset
            df = load_dataset(dataset, limit=10000)

            # Check if dataset is empty
            if len(df) == 0:
                result = {
                    "dataset": dataset,
                    "metric": metric,
                    "error": "Dataset is empty",
                    "suggestion": "This dataset may not have been loaded yet or contains no data"
                }
            # Check if metric column exists
            elif metric not in df.columns:
                available_cols = list(df.columns)
                # Try to suggest similar columns
                similar = [col for col in available_cols if metric.lower() in col.lower() or col.lower() in metric.lower()]

                result = {
                    "dataset": dataset,
                    "metric": metric,
                    "error": f"Metric '{metric}' not found in dataset",
                    "available_columns": available_cols[:20],  # Limit to prevent overflow
                    "suggested_columns": similar[:5] if similar else []
                }
            else:
                # Apply filters if provided
                filtered_df = df.copy()
                invalid_filters = []
                for col, value in filters.items():
                    if col in filtered_df.columns:
                        filtered_df = filtered_df[filtered_df[col] == value]
                    else:
                        invalid_filters.append(col)
                        logger.warning(f"Filter column '{col}' not found in dataset, skipping")

                # Check if filters removed all data
                if len(filtered_df) == 0:
                    # Find latest available period for helpful error message
                    latest_period = "unknown"
                    period_cols = [c for c in df.columns if 'period' in c.lower() or 'date' in c.lower()]
                    if period_cols:
                        latest_period = str(df[period_cols[0]].max())

                    result = {
                        "dataset": dataset,
                        "metric": metric,
                        "filters_applied": filters,
                        "error": "No data available matching the specified filters",
                        "suggestion": f"Latest available period: {latest_period}",
                        "invalid_filters": invalid_filters,
                        "total_rows_before_filter": len(df)
                    }
                else:
                    # Select relevant columns (metric + filter columns + common dimensions)
                    result_cols = [metric]
                    for col in df.columns:
                        col_lower = col.lower()
                        if any(dim in col_lower for dim in ['date', 'period', 'age', 'geography', 'icb', 'provider']):
                            if col not in result_cols:
                                result_cols.append(col)

                    # Get metadata to find label
                    metadata = backend.get_dataset_metadata(dataset)
                    metric_label = metric
                    metric_unit = 'unknown'
                    if metadata.get('metadata') and 'kpis' in metadata['metadata']:
                        for kpi in metadata['metadata']['kpis']:
                            if kpi['column'] == metric:
                                metric_label = kpi.get('label', metric)
                                metric_unit = kpi.get('unit', 'unknown')
                                break

                    # Return results
                    result_data = filtered_df[result_cols].head(limit)
                    rows = []
                    for _, row in result_data.iterrows():
                        row_dict = {}
                        for col, val in row.items():
                            row_dict[col] = make_json_safe(val)
                        rows.append(row_dict)

                    result = {
                        "dataset": dataset,
                        "metric": metric,
                        "metric_label": metric_label,
                        "metric_unit": metric_unit,
                        "filters_applied": filters,
                        "invalid_filters": invalid_filters,
                        "rows": rows,
                        "row_count": len(rows),
                        "total_after_filter": len(filtered_df),
                        "truncated": len(filtered_df) > limit
                    }

        else:
            raise ValueError(f"Unknown tool: {name}")

        # Format result as JSON text
        import json
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]

    except Exception as e:
        logger.error(f"Error in tool {name}: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]


async def main():
    """Main entry point for stdio server."""
    logger.info("DataWarp MCP stdio server starting...")
    logger.info("Backend: PostgreSQL + DuckDB hybrid")

    # Check PostgreSQL connection
    try:
        catalog = load_catalog()
        logger.info(f"PostgreSQL connected: {len(catalog)} datasets available")
    except Exception as e:
        logger.error(f"PostgreSQL connection failed: {e}")
        logger.error("Check .env file has correct POSTGRES_* credentials")

    # Run the stdio server
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
