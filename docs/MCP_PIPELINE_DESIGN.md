# Multi-Dataset MCP Server Design

**Created:** 2026-01-11 UTC
**Purpose:** Design document for extending MCP server to support multiple datasets and backends

---

## 1. Overview

This document describes the design for a multi-dataset MCP server that enables natural language querying of NHS public datasets. The design builds on the existing DataWarp pipeline outputs (Parquet files, catalog.parquet) and extends the current MCP server implementation.

### Goals

1. **Dataset Registry** - Structured configuration to register multiple datasets with metadata, backend type, and connection details
2. **Metadata Layer** - Rich schema metadata to give LLMs sufficient context for accurate query generation
3. **Query Routing** - Dispatch queries to appropriate backend (DuckDB for Parquet, PostgreSQL for live data)
4. **MCP Tool Surface** - Enhanced tools for discovery, metadata inspection, and querying

### Constraints

- Solo developer - favor simplicity over enterprise patterns
- Build on existing DataWarp output structure
- Stepping stone toward internal NHS data integration

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Claude Desktop / Agent                      │
└─────────────────────────────┬───────────────────────────────────┘
                              │ MCP Protocol (stdio)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MCP Server (stdio_server.py)                 │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ list_datasets│  │ get_metadata │  │ query                  │ │
│  │ search_cols  │  │ describe_col │  │ aggregate              │ │
│  └──────────────┘  └──────────────┘  └────────────────────────┘ │
└─────────────────────────────┬───────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│   Dataset Registry      │     │    Query Router         │
│   (datasets.yaml)       │     │    (router.py)          │
└───────────┬─────────────┘     └───────────┬─────────────┘
            │                               │
            │         ┌─────────────────────┼─────────────────────┐
            │         ▼                     ▼                     ▼
            │  ┌─────────────┐       ┌─────────────┐       ┌─────────────┐
            │  │  DuckDB     │       │  Postgres   │       │  DuckDB     │
            │  │  (Parquet)  │       │  (Direct)   │       │  (PG ext)   │
            │  └─────────────┘       └─────────────┘       └─────────────┘
            │         ▲                     ▲                     ▲
            │         │                     │                     │
            │  output/*.parquet      staging.tbl_*         (future)
            │
            ▼
┌─────────────────────────┐
│   Metadata Store        │
│   (metadata/*.yaml)     │
│   + catalog.parquet     │
└─────────────────────────┘
```

---

## 3. File Structure

```
mcp_server/
├── __init__.py
├── stdio_server.py          # Main MCP server (extend existing)
├── config/
│   └── datasets.yaml        # Dataset registry (generated from catalog)
├── metadata/
│   ├── mental_health.yaml   # Rich metadata per domain
│   ├── workforce.yaml
│   ├── primary_care.yaml
│   ├── waiting_times.yaml
│   ├── geography.yaml
│   ├── publications.yaml
│   ├── research.yaml
│   └── other.yaml
├── core/
│   ├── __init__.py
│   ├── registry.py          # Dataset registry loader
│   └── router.py            # Query routing logic
├── backends/
│   ├── __init__.py
│   ├── duckdb_parquet.py    # DuckDB for parquet files
│   └── postgres.py          # Direct Postgres queries (optional)
└── tools/                   # (future) Tool-specific handlers
    └── __init__.py
```

---

## 4. Dataset Registry Schema

**File:** `mcp_server/config/datasets.yaml`

```yaml
version: '1.0'
generated_from: catalog.parquet
default_backend: duckdb_parquet

datasets:
  adhd_prevalence_estimate:
    backend: duckdb_parquet
    path: output/adhd_prevalence_estimate.parquet
    metadata_file: metadata/mental_health.yaml
    domain: mental_health
    tags: [adhd, prevalence, estimate]

  pcn_wf_fte_roles_national:
    backend: duckdb_parquet
    path: output/pcn_wf_fte_roles_national.parquet
    metadata_file: metadata/workforce.yaml
    domain: workforce
    tags: [pcn, fte, workforce, national]

  # For live Postgres access (future)
  gp_practice_live:
    backend: postgres
    table: staging.tbl_gp_prac_reg_all
    metadata_file: metadata/primary_care.yaml
    domain: primary_care
    tags: [gp, registration, practice]

backends:
  duckdb_parquet:
    type: duckdb
    description: Query Parquet files via DuckDB (default)
    base_path: output/

  postgres:
    type: postgres
    description: Query PostgreSQL staging tables directly
    schema: staging
    note: Uses POSTGRES_* env vars from .env
```

**Key Features:**
- Single file to register all datasets
- Backend type per dataset (flexibility without complexity)
- Links to detailed metadata files
- Tags for semantic discovery

---

## 5. Metadata Layer Schema

**File:** `mcp_server/metadata/mental_health.yaml`

```yaml
domain: mental_health
description: NHS Mental Health datasets
datasets:
  adhd_prevalence_estimate:
    purpose: |
      Estimates of ADHD prevalence in the population based on
      GP practice registrations and clinical coding patterns.

    row_count: 8149
    column_count: 11

    example_questions:
      - "What is the estimated ADHD prevalence rate?"
      - "How has ADHD prevalence changed over time?"
      - "Which age groups have highest ADHD prevalence?"

    columns:
      reporting_period_start_date:
        description: Start date of the reporting period
        data_type: date
        role: dimension
        query_keywords: [date, period, month, time]

      age_band:
        description: Age group classification
        data_type: varchar
        role: dimension
        value_domain:
          type: categorical
          values: ["0-17", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
        query_keywords: [age, age group, band]

      prevalence_rate:
        description: Estimated ADHD prevalence rate as percentage
        data_type: numeric
        role: measure
        unit: percentage
        aggregation: weighted_average
        query_keywords: [prevalence, rate, percentage]

      patient_count:
        description: Number of patients with ADHD diagnosis
        data_type: integer
        role: measure
        aggregation: sum
        query_keywords: [count, patients, number, total]

      _load_id:
        description: DataWarp load batch identifier
        data_type: integer
        role: system
```

**Key Features:**
- `purpose` gives LLM context for dataset selection
- `example_questions` help with query interpretation
- `value_domain` prevents invalid filter values
- `aggregation` hints tell LLM how to aggregate properly
- `query_keywords` enable semantic column search

---

## 6. Query Router

**File:** `mcp_server/core/router.py`

The router dispatches queries to the appropriate backend based on dataset configuration:

```python
class QueryRouter:
    def __init__(self, registry: DatasetRegistry):
        self.registry = registry
        self.backends = {}  # Lazy-loaded

    def query(self, dataset_code: str, sql: str) -> list[dict]:
        config = self.registry.get_dataset_config(dataset_code)
        backend = self._get_backend(config['backend'])
        source = self._resolve_path(config)
        return backend.execute(source, sql)
```

**Features:**
- Lazy backend loading (only creates when needed)
- Path resolution (relative to project root)
- Unified interface across backends

---

## 7. Backend Implementations

### DuckDB Backend (Parquet)

**File:** `mcp_server/backends/duckdb_parquet.py`

```python
class DuckDBBackend:
    def execute(self, parquet_path: str, sql: str) -> list[dict]:
        # Register parquet as 'data' view
        self.conn.execute(f"CREATE OR REPLACE VIEW data AS SELECT * FROM '{parquet_path}'")
        result = self.conn.execute(sql).fetchdf()
        return self._df_to_dicts(result)

    def get_schema(self, parquet_path: str) -> list[dict]:
        # Returns column names and types

    def get_stats(self, parquet_path: str) -> dict:
        # Returns row_count, column_count, file_size_kb

    def get_distinct_values(self, parquet_path: str, column: str) -> list:
        # Returns unique values for a column

    def get_column_stats(self, parquet_path: str, column: str) -> dict:
        # Returns null_count, distinct_count, min, max
```

### PostgreSQL Backend (Future)

**File:** `mcp_server/backends/postgres.py`

```python
class PostgresBackend:
    def execute(self, table: str, sql: str) -> list[dict]:
        # Replace 'data' placeholder with actual table
        actual_sql = sql.replace('data', table)
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(actual_sql)
                return [dict(row) for row in cur.fetchall()]
```

---

## 8. MCP Tool Surface

### Discovery Tools

| Tool | Parameters | Description |
|------|------------|-------------|
| `list_datasets` | domain, tags, keyword, limit | List datasets with filtering |
| `search_columns` | keyword, role | Find columns across all datasets |

### Metadata Tools

| Tool | Parameters | Description |
|------|------------|-------------|
| `get_metadata` | dataset | Get dataset structure, purpose, example questions |
| `describe_column` | dataset, column | Get column details, value domain |

### Query Tools

| Tool | Parameters | Description |
|------|------------|-------------|
| `query` | dataset, sql | Execute SQL (use 'data' as table name) |
| `aggregate` | dataset, group_by, measures, filters | Structured aggregation |
| `preview` | dataset, rows | Quick sample of data |

### Tool Schema Examples

```json
{
  "name": "query",
  "description": "Execute SQL query against a dataset. Use 'data' as the table name.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "dataset": {"type": "string", "description": "Dataset code"},
      "sql": {"type": "string", "description": "SQL using 'data' as table name"}
    },
    "required": ["dataset", "sql"]
  }
}

{
  "name": "search_columns",
  "description": "Search for columns across all datasets by keyword",
  "inputSchema": {
    "type": "object",
    "properties": {
      "keyword": {"type": "string", "description": "Search term"},
      "role": {"type": "string", "enum": ["dimension", "measure", "system"]}
    },
    "required": ["keyword"]
  }
}
```

---

## 9. Current State (Generated)

**Registry Generated:** 2026-01-11

| Metric | Value |
|--------|-------|
| Total Datasets | 181 |
| Domains | 8 |

**Domain Breakdown:**
- geography: 43 datasets
- mental_health: 42 datasets
- publications: 37 datasets
- workforce: 17 datasets
- other: 16 datasets
- primary_care: 14 datasets
- waiting_times: 11 datasets
- research: 1 dataset

**Files Created:**
- `mcp_server/config/datasets.yaml` - Dataset registry
- `mcp_server/metadata/*.yaml` - 8 domain metadata files
- `mcp_server/backends/duckdb_parquet.py` - DuckDB backend
- `mcp_server/core/registry.py` - Registry loader
- `mcp_server/core/router.py` - Query router

---

## 10. Implementation Roadmap

### Phase 0: Foundation (Completed)

- [x] Generate registry from existing catalog
- [x] Create DuckDB backend
- [x] Create registry loader
- [x] Create query router

### Phase 1: Integration (Next)

- [ ] Update stdio_server.py with new tools
- [ ] Add search_columns tool
- [ ] Test with Claude Desktop

### Phase 2: Enhancement (When Needed)

- [ ] Manually enrich metadata for key datasets (ADHD, PCN)
- [ ] Add example_questions to help query interpretation
- [ ] Add value_domain for categorical columns

### Phase 3: Postgres Backend (When Needed)

- [ ] Implement PostgresBackend
- [ ] Add datasets with backend: postgres to registry
- [ ] Test unified querying

---

## 11. Usage Examples

### List Datasets by Domain

```python
from mcp_server.core.registry import DatasetRegistry

registry = DatasetRegistry()
mental_health = registry.list_datasets(domain='mental_health')
# Returns 42 datasets
```

### Query Dataset via Router

```python
from mcp_server.core.router import QueryRouter

router = QueryRouter()
results = router.query(
    'adhd_prevalence_estimate',
    'SELECT age_band, SUM(patient_count) as total FROM data GROUP BY age_band'
)
```

### Search for Columns

```python
registry = DatasetRegistry()
age_columns = registry.search_columns(keyword='age', role='dimension')
# Returns columns matching 'age' across all datasets
```

---

## 12. Reconciliation with Existing System

**What Exists:**
- `catalog.parquet` (181 datasets)
- `.md` metadata files
- `stdio_server.py` with 3 tools
- `include_stats=True` for PostgreSQL stats

**What This Design Adds:**
- Structured `datasets.yaml` registry
- Domain-organized metadata YAML files
- DuckDB backend for SQL queries
- Query router for backend dispatch
- Enhanced tool surface

**Integration Points:**
- Registry generated from existing catalog
- Metadata parsed from existing .md files
- Parquet files unchanged
- PostgreSQL backend uses existing connection

---

## 13. Next Steps

1. **Test DuckDB Backend**
   ```bash
   python -c "
   from mcp_server.backends.duckdb_parquet import DuckDBBackend
   backend = DuckDBBackend({'base_path': 'output/'})
   print(backend.get_stats('output/adhd_prevalence_estimate.parquet'))
   "
   ```

2. **Test Query Router**
   ```bash
   python -c "
   from mcp_server.core.router import QueryRouter
   router = QueryRouter()
   results = router.query('adhd_prevalence_estimate', 'SELECT COUNT(*) FROM data')
   print(results)
   "
   ```

3. **Update stdio_server.py**
   - Add search_columns tool
   - Replace pattern-matching query with DuckDB execution
   - Add aggregate tool

4. **Enrich Key Datasets**
   - Add example_questions to ADHD datasets
   - Add value_domain for categorical columns
   - Document typical query patterns

---

## 14. Design Decisions

| Decision | Rationale |
|----------|-----------|
| YAML over JSON | More readable, supports comments |
| DuckDB over pandas | Better SQL support, columnar efficiency |
| Lazy backend loading | Only create when needed |
| Domain-based metadata files | Natural organization, manageable file sizes |
| 'data' as table alias | Consistent interface across backends |
| Registry + Router separation | Single responsibility, testable |

---

**Document Version:** 1.0
**Last Updated:** 2026-01-11 UTC
