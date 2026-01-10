"""DataWarp MCP Server - Enable agent querying of NHS data.

This server implements Model Context Protocol endpoints for Claude agents
to discover and query agent-ready NHS datasets.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="DataWarp MCP Server", version="0.1.0")

# Data directory
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
    """Load the catalog of available datasets."""
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(f"Catalog not found: {CATALOG_PATH}")
    return pd.read_parquet(CATALOG_PATH)


def load_dataset(source_code: str) -> pd.DataFrame:
    """Load a specific dataset by source code."""
    catalog = load_catalog()
    row = catalog[catalog['source_code'] == source_code]

    if len(row) == 0:
        raise ValueError(f"Dataset not found: {source_code}")

    # File path in catalog includes "output/" prefix, strip it since DATA_DIR already points to output/
    file_path_str = row.iloc[0]['file_path']
    if file_path_str.startswith('output/'):
        file_path_str = file_path_str[7:]  # Remove "output/" prefix

    file_path = DATA_DIR / file_path_str
    if not file_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {file_path}")

    return pd.read_parquet(file_path)


def get_dataset_metadata(source_code: str) -> Dict:
    """Get metadata for a dataset including column descriptions."""
    # Load dataset schema
    df = load_dataset(source_code)

    # Try to load companion .md file for descriptions
    catalog = load_catalog()
    row = catalog[catalog['source_code'] == source_code]

    # Handle md_path with same prefix stripping
    md_path_str = row.iloc[0]['md_path'] if 'md_path' in row.columns else None
    if md_path_str and md_path_str.startswith('output/'):
        md_path_str = md_path_str[7:]
    md_path = DATA_DIR / md_path_str if md_path_str else None
    column_descriptions = {}

    if md_path and md_path.exists():
        # Parse .md file for column descriptions
        content = md_path.read_text()
        import re

        # Match format: #### `column_name` followed by **Description:** on a subsequent line
        # Split content into sections by column headers
        sections = re.split(r'####\s+`([^`]+)`', content)

        # sections[0] is content before first header
        # sections[1] is first column name, sections[2] is its content
        # sections[3] is second column name, sections[4] is its content, etc.
        for i in range(1, len(sections), 2):
            col_name = sections[i]
            col_content = sections[i + 1] if i + 1 < len(sections) else ""

            # Extract description from the content
            desc_match = re.search(r'\*\*Description:\*\*\s*(.+?)(?:\n\*\*|$)', col_content, re.DOTALL)
            if desc_match:
                description = desc_match.group(1).strip()
                # Remove trailing newlines and extra whitespace
                description = ' '.join(description.split())
                column_descriptions[col_name] = description

    # Build metadata response
    columns = []
    for col in df.columns:
        col_info = {
            "name": col,
            "type": str(df[col].dtype),
            "description": column_descriptions.get(col, ""),
            "sample_values": df[col].head(3).tolist() if len(df) > 0 else []
        }
        columns.append(col_info)

    catalog_row = catalog[catalog['source_code'] == source_code].iloc[0]

    return {
        "source_code": source_code,
        "domain": catalog_row.get('domain', ''),
        "description": catalog_row.get('description', ''),
        "row_count": len(df),
        "column_count": len(df.columns),
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
    """List available datasets with optional filtering."""
    catalog = load_catalog()

    # Apply filters
    if 'domain' in params:
        catalog = catalog[catalog['domain'] == params['domain']]

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

    # Format response
    datasets = []
    for _, row in catalog.iterrows():
        datasets.append({
            "code": row['source_code'],
            "domain": row.get('domain', ''),
            "description": row.get('description', ''),
            "rows": int(row['row_count']),
            "columns": int(row['column_count']),
            "file_size_kb": float(row.get('file_size_kb', 0)),
            "date_range": f"{row.get('min_date', 'N/A')} to {row.get('max_date', 'N/A')}"
        })

    return MCPResponse(result={
        "total_found": len(catalog),
        "datasets": datasets
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
    return {
        "service": "DataWarp MCP Server",
        "status": "running",
        "version": "0.1.0",
        "catalog_datasets": len(load_catalog()) if CATALOG_PATH.exists() else 0
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
