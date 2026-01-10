# DataWarp MCP Server

**Purpose:** Enable Claude agents to query NHS data using natural language via Model Context Protocol.

**Status:** Prototype (PRIMARY OBJECTIVE validation)

---

## Architecture

```
Claude Agent
    ↓
MCP Protocol
    ↓
DataWarp MCP Server
    ↓
catalog.parquet + exported datasets
```

## Endpoints

### 1. `list_datasets`
Browse available datasets by domain, keyword, or date range.

**Example Request:**
```json
{
  "method": "list_datasets",
  "params": {
    "domain": "ADHD",
    "min_rows": 100
  }
}
```

**Response:**
```json
{
  "datasets": [
    {
      "code": "adhd_prevalence_estimate",
      "domain": "ADHD",
      "description": "ADHD prevalence estimates by age and geography",
      "rows": 8149,
      "columns": 11
    }
  ]
}
```

### 2. `query`
Execute natural language queries against datasets.

**Example Request:**
```json
{
  "method": "query",
  "params": {
    "question": "Show me PCN workforce trends by age group",
    "dataset": "pcn_wf_fte_age_staff_group"
  }
}
```

**Response:**
```json
{
  "results": [...],
  "row_count": 301,
  "sql_generated": "SELECT age_band, SUM(march_2025) FROM ... GROUP BY age_band"
}
```

### 3. `get_metadata`
Get detailed column metadata for a dataset.

**Example Request:**
```json
{
  "method": "get_metadata",
  "params": {
    "dataset": "adhd_prevalence_estimate"
  }
}
```

**Response:**
```json
{
  "columns": [
    {
      "name": "age_0_to_4",
      "type": "INTEGER",
      "description": "Patient count aged 0-4 years",
      "keywords": ["age", "pediatric"]
    }
  ]
}
```

---

## Installation

```bash
# Install dependencies
pip install fastapi uvicorn pandas pyarrow

# Run server
python mcp_server/server.py
```

---

## Testing

```bash
# Test list endpoint
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"method": "list_datasets", "params": {"domain": "ADHD"}}'

# Test query endpoint
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"method": "query", "params": {"question": "How many ADHD patients by age?", "dataset": "adhd_prevalence_estimate"}}'
```

---

## Design Principles

1. **Agent-First**: Optimize for natural language querying
2. **Self-Describing**: Metadata enables discovery without documentation
3. **Lightweight**: No database, just Parquet + pandas
4. **Stateless**: Each query is independent
5. **Observable**: Log all queries for learning

---

**Created:** 2026-01-10
**Goal:** Prove PRIMARY OBJECTIVE (agent querying works!)
