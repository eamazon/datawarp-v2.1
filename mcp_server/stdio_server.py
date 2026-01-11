#!/usr/bin/env python3
"""DataWarp MCP Server - Using official MCP SDK."""

import sys
import logging
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from mcp_server.backends.duckdb_parquet import DuckDBBackend

# Configure logging to stderr (stdout is reserved for MCP protocol)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Data directory
DATA_DIR = project_root / "output"
CATALOG_PATH = DATA_DIR / "catalog.parquet"

# Create MCP server
app = Server("datawarp-nhs")

# Initialize DuckDB backend for SQL queries
duckdb_backend = DuckDBBackend({'base_path': str(DATA_DIR)})


def load_catalog() -> pd.DataFrame:
    """Load the catalog of available datasets."""
    if not CATALOG_PATH.exists():
        logger.error(f"Catalog not found: {CATALOG_PATH}")
        return pd.DataFrame()
    return pd.read_parquet(CATALOG_PATH)


def load_dataset(source_code: str) -> pd.DataFrame:
    """Load a specific dataset by source code."""
    catalog = load_catalog()
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


def get_dataset_path(source_code: str) -> str:
    """Get the file path for a dataset."""
    catalog = load_catalog()
    row = catalog[catalog['source_code'] == source_code]

    if len(row) == 0:
        raise ValueError(f"Dataset not found: {source_code}")

    file_path_str = row.iloc[0]['file_path']
    if file_path_str.startswith('output/'):
        file_path_str = file_path_str[7:]

    file_path = DATA_DIR / file_path_str
    if not file_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {file_path}")

    return str(file_path)


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


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="list_datasets",
            description="List available NHS datasets with optional filtering",
            inputSchema={
                "type": "object",
                "properties": {
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
            description="Get detailed metadata for a specific dataset",
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
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    logger.info(f"Tool called: {name} with args: {arguments}")

    try:
        if name == "list_datasets":
            catalog = load_catalog()

            # Apply filters
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
                datasets.append({
                    "code": row['source_code'],
                    "description": row.get('description', ''),
                    "rows": int(row['row_count']),
                    "columns": int(row['column_count'])
                })

            result = {
                "total_found": len(datasets),
                "datasets": datasets
            }

        elif name == "get_metadata":
            if 'dataset' not in arguments:
                raise ValueError("Missing required parameter: dataset")

            source_code = arguments['dataset']
            df = load_dataset(source_code)

            # Build metadata
            columns = []
            for col in df.columns:
                # Convert sample values to JSON-serializable format
                sample_values = []
                if len(df) > 0:
                    for val in df[col].head(3):
                        if pd.isna(val):
                            sample_values.append(None)
                        elif isinstance(val, (pd.Timestamp, pd.DatetimeTZDtype)):
                            sample_values.append(str(val))
                        else:
                            sample_values.append(val)

                columns.append({
                    "name": col,
                    "type": str(df[col].dtype),
                    "sample_values": sample_values
                })

            catalog = load_catalog()
            catalog_row = catalog[catalog['source_code'] == source_code].iloc[0]

            result = {
                "source_code": source_code,
                "description": catalog_row.get('description', ''),
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": columns
            }

        elif name == "query":
            if 'dataset' not in arguments:
                raise ValueError("Missing required parameter: dataset")
            if 'question' not in arguments:
                raise ValueError("Missing required parameter: question")

            dataset_code = arguments['dataset']
            question = arguments['question']

            # Get dataset path
            dataset_path = get_dataset_path(dataset_code)

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
                    df_sample = load_dataset(dataset_code)  # Load to inspect columns
                    sql, query_description = generate_sql_from_question(question, df_sample)
                    logger.info(f"Generated SQL: {sql}")

                # Execute with DuckDB
                rows = duckdb_backend.execute(dataset_path, sql)

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
                    "sql_executed": sql
                }

            except Exception as e:
                # Fallback to pandas for simple queries
                logger.warning(f"DuckDB query failed: {e}, falling back to pandas")
                df = load_dataset(dataset_code)

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
                            if pd.isna(val):
                                row_dict[col] = None
                            elif isinstance(val, (pd.Timestamp, pd.DatetimeTZDtype)):
                                row_dict[col] = str(val)
                            else:
                                row_dict[col] = val
                        rows.append(row_dict)
                    query_description = "First 100 rows (pandas fallback)"

                result = {
                    "rows": rows,
                    "row_count": len(rows),
                    "query_description": query_description,
                    "fallback_used": True,
                    "error": str(e)
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
    logger.info(f"Catalog path: {CATALOG_PATH}")

    # Check catalog exists
    if CATALOG_PATH.exists():
        catalog = load_catalog()
        logger.info(f"Catalog loaded: {len(catalog)} datasets")
    else:
        logger.error("Catalog not found!")

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
