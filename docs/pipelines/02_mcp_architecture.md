# MCP Architecture

**Created:** 2026-01-11 UTC
**Purpose:** Multi-dataset MCP server design with backend routing

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MCP Multi-Dataset Architecture                        │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                       Claude Desktop / Agent                                 │
│   "What is the ADHD prevalence rate for 18-24 age group?"                   │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │ MCP Protocol (stdio)
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      MCP Server (stdio_server.py)                            │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────────────┐ │
│  │ list_datasets  │  │ get_metadata   │  │ query                          │ │
│  │ search_columns │  │ describe_col   │  │ aggregate                      │ │
│  └────────────────┘  └────────────────┘  └────────────────────────────────┘ │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────────┐ ┌─────────────────────────────────────────────┐
│    Dataset Registry         │ │              Query Router                    │
│    (datasets.yaml)          │ │              (router.py)                     │
│                             │ │                                              │
│ 181 datasets                │ │ Dispatches to appropriate backend           │
│ 8 domains                   │ │ based on dataset configuration              │
└─────────────┬───────────────┘ └───────────────┬─────────────────────────────┘
              │                                 │
              │         ┌───────────────────────┼───────────────────────┐
              │         ▼                       ▼                       ▼
              │  ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
              │  │   DuckDB    │         │  Postgres   │         │   DuckDB    │
              │  │  (Parquet)  │         │  (Direct)   │         │  (PG ext)   │
              │  │             │         │             │         │  (future)   │
              │  └─────────────┘         └─────────────┘         └─────────────┘
              │         ▲                       ▲                       ▲
              │         │                       │                       │
              │  output/*.parquet        staging.tbl_*            (future)
              │
              ▼
┌─────────────────────────────┐
│     Metadata Store          │
│   (metadata/*.yaml)         │
│   + catalog.parquet         │
│                             │
│ Column descriptions         │
│ Value domains               │
│ Example questions           │
└─────────────────────────────┘
```

---

## Component Details

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Dataset Registry                                    │
└─────────────────────────────────────────────────────────────────────────────┘

mcp_server/config/datasets.yaml
┌─────────────────────────────────────────────────────────────────────────────┐
│ version: '1.0'                                                               │
│ generated_from: catalog.parquet                                              │
│ default_backend: duckdb_parquet                                              │
│                                                                              │
│ datasets:                                                                    │
│   adhd_prevalence_estimate:              ◀── 181 datasets registered        │
│     backend: duckdb_parquet                                                  │
│     path: output/adhd_prevalence_estimate.parquet                            │
│     metadata_file: metadata/mental_health.yaml                               │
│     domain: mental_health                                                    │
│     tags: [adhd, prevalence, estimate]                                       │
│                                                                              │
│   pcn_wf_fte_roles_national:                                                 │
│     backend: duckdb_parquet                                                  │
│     path: output/pcn_wf_fte_roles_national.parquet                           │
│     ...                                                                      │
│                                                                              │
│ backends:                                                                    │
│   duckdb_parquet:                                                            │
│     type: duckdb                                                             │
│     base_path: output/                                                       │
│   postgres:                               ◀── Future: Direct DB access       │
│     type: postgres                                                           │
│     schema: staging                                                          │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                          Domain Organization                                 │
└─────────────────────────────────────────────────────────────────────────────┘

                        181 Datasets across 8 Domains
                        ┌───────────────────────────────┐
                        │                               │
    ┌───────────────────┼───────────────────────────────┼───────────────────┐
    │                   │                               │                   │
    ▼                   ▼                               ▼                   ▼
┌─────────┐       ┌─────────┐                     ┌─────────┐       ┌─────────┐
│geography│       │mental   │                     │workforce│       │primary  │
│   (43)  │       │health   │                     │   (17)  │       │care (14)│
└─────────┘       │  (42)   │                     └─────────┘       └─────────┘
                  └─────────┘
    ┌───────────────────┼───────────────────────────────┼───────────────────┐
    │                   │                               │                   │
    ▼                   ▼                               ▼                   ▼
┌─────────┐       ┌─────────┐                     ┌─────────┐       ┌─────────┐
│pubs (37)│       │waiting  │                     │other    │       │research │
│         │       │times(11)│                     │   (16)  │       │   (1)   │
└─────────┘       └─────────┘                     └─────────┘       └─────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                          Metadata Layer                                      │
└─────────────────────────────────────────────────────────────────────────────┘

mcp_server/metadata/mental_health.yaml
┌─────────────────────────────────────────────────────────────────────────────┐
│ domain: mental_health                                                        │
│ description: NHS Mental Health datasets                                      │
│                                                                              │
│ datasets:                                                                    │
│   adhd_prevalence_estimate:                                                  │
│     purpose: |                              ◀── Context for LLM              │
│       Estimates of ADHD prevalence in the population based on               │
│       GP practice registrations and clinical coding patterns.               │
│                                                                              │
│     example_questions:                      ◀── Query interpretation         │
│       - "What is the estimated ADHD prevalence rate?"                        │
│       - "How has ADHD prevalence changed over time?"                         │
│                                                                              │
│     columns:                                                                 │
│       age_band:                                                              │
│         description: Age group classification                                │
│         data_type: varchar                                                   │
│         role: dimension                     ◀── Column role                  │
│         value_domain:                       ◀── Valid values                 │
│           type: categorical                                                  │
│           values: ["0-17", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"]│
│                                                                              │
│       prevalence_rate:                                                       │
│         description: Estimated ADHD prevalence rate as percentage            │
│         data_type: numeric                                                   │
│         role: measure                                                        │
│         unit: percentage                    ◀── Unit for display             │
│         aggregation: weighted_average       ◀── How to aggregate             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Query Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Query Execution Flow                                │
└─────────────────────────────────────────────────────────────────────────────┘

User Query: "What is the ADHD prevalence rate for 18-24 age group?"
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 1: Discovery                                                            │
│                                                                              │
│   Agent calls: list_datasets(keyword="adhd")                                 │
│                                                                              │
│   Registry returns:                                                          │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ adhd_prevalence_estimate  - 8149 rows  - mental_health              │   │
│   │ adhd_diagnosis_to_med     - 5234 rows  - mental_health              │   │
│   │ adhd_summary_referrals    - 12000 rows - mental_health              │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 2: Metadata Inspection                                                  │
│                                                                              │
│   Agent calls: get_metadata("adhd_prevalence_estimate")                      │
│                                                                              │
│   Returns:                                                                   │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ columns:                                                             │   │
│   │   - age_band (dimension) - values: ["0-17", "18-24", ...]           │   │
│   │   - prevalence_rate (measure) - percentage                          │   │
│   │   - patient_count (measure) - integer                               │   │
│   │                                                                      │   │
│   │ purpose: Estimates of ADHD prevalence...                            │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 3: Query Execution                                                      │
│                                                                              │
│   Agent generates SQL:                                                       │
│   SELECT age_band, AVG(prevalence_rate) as avg_rate                         │
│   FROM data                                                                  │
│   WHERE age_band = '18-24'                                                   │
│   GROUP BY age_band                                                          │
│                                                                              │
│   Agent calls: query("adhd_prevalence_estimate", sql)                        │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 4: Backend Routing                                                      │
│                                                                              │
│   Router checks dataset config:                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ adhd_prevalence_estimate:                                            │   │
│   │   backend: duckdb_parquet  ◀── Route to DuckDB                       │   │
│   │   path: output/adhd_prevalence_estimate.parquet                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   DuckDB Backend:                                                            │
│   1. CREATE VIEW data AS SELECT * FROM 'path/to/file.parquet'               │
│   2. Execute user SQL                                                        │
│   3. Return results as list[dict]                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 5: Response                                                             │
│                                                                              │
│   Agent receives:                                                            │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ [{"age_band": "18-24", "avg_rate": 4.2}]                            │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   Agent formats answer:                                                      │
│   "The average ADHD prevalence rate for the 18-24 age group is 4.2%"        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Tool Surface

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MCP Tools                                       │
└─────────────────────────────────────────────────────────────────────────────┘

DISCOVERY TOOLS
┌───────────────────────────────────────────────────────────────────────────┐
│ list_datasets                                                              │
│   Parameters: domain, tags, keyword, limit                                 │
│   Returns: [{code, domain, description, row_count, tags}]                  │
│                                                                            │
│   Example: list_datasets(domain="mental_health", limit=10)                 │
├───────────────────────────────────────────────────────────────────────────┤
│ search_columns                                                             │
│   Parameters: keyword, role                                                │
│   Returns: [{dataset, column, description, role}]                          │
│                                                                            │
│   Example: search_columns(keyword="age", role="dimension")                 │
└───────────────────────────────────────────────────────────────────────────┘

METADATA TOOLS
┌───────────────────────────────────────────────────────────────────────────┐
│ get_metadata                                                               │
│   Parameters: dataset                                                      │
│   Returns: {columns, purpose, example_questions, row_count}                │
│                                                                            │
│   Example: get_metadata("adhd_prevalence_estimate")                        │
├───────────────────────────────────────────────────────────────────────────┤
│ describe_column                                                            │
│   Parameters: dataset, column                                              │
│   Returns: {description, type, role, value_domain, aggregation}            │
│                                                                            │
│   Example: describe_column("adhd_prevalence_estimate", "age_band")         │
└───────────────────────────────────────────────────────────────────────────┘

QUERY TOOLS
┌───────────────────────────────────────────────────────────────────────────┐
│ query                                                                      │
│   Parameters: dataset, sql                                                 │
│   Returns: [{...row_data}]                                                 │
│   Note: Use 'data' as table name in SQL                                    │
│                                                                            │
│   Example: query("adhd_prevalence_estimate",                               │
│                  "SELECT age_band, COUNT(*) FROM data GROUP BY 1")         │
├───────────────────────────────────────────────────────────────────────────┤
│ preview                                                                    │
│   Parameters: dataset, rows                                                │
│   Returns: [{...row_data}] (first N rows)                                  │
│                                                                            │
│   Example: preview("adhd_prevalence_estimate", rows=5)                     │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
mcp_server/
├── __init__.py
├── stdio_server.py              # Main MCP server (entry point)
├── config/
│   └── datasets.yaml            # Dataset registry (181 datasets)
├── metadata/
│   ├── mental_health.yaml       # 42 datasets
│   ├── geography.yaml           # 43 datasets
│   ├── workforce.yaml           # 17 datasets
│   ├── primary_care.yaml        # 14 datasets
│   ├── publications.yaml        # 37 datasets
│   ├── waiting_times.yaml       # 11 datasets
│   ├── research.yaml            # 1 dataset
│   └── other.yaml               # 16 datasets
├── core/
│   ├── __init__.py
│   ├── registry.py              # Dataset registry loader
│   └── router.py                # Query routing logic
├── backends/
│   ├── __init__.py
│   ├── duckdb_parquet.py        # DuckDB for parquet files
│   └── postgres.py              # Direct Postgres (future)
└── tools/
    └── __init__.py              # Tool handlers (future)
```

---

*See MCP_PIPELINE_DESIGN.md for detailed implementation specifications.*
