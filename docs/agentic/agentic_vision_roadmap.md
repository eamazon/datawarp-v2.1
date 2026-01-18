# Agentic DataWarp Vision & Roadmap

**Created:** 2026-01-17
**Updated:** 2026-01-17 19:30 UTC (Added metadata-driven reporting layer - Steps 6-7)
**Status:** Planning Complete - Ready for Implementation

---

## Executive Summary

Transform DataWarp from a human-operated tool into an AI-assisted platform where agents handle routine work and humans provide judgment at key decision points.

**Philosophy:** Agent as intelligent assistant, not replacement. Human-in-the-loop for judgment calls.

---

## The Vision

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│                         AGENTIC DATAWARP                                     │
│                    "The AI-Native Data Platform"                             │
│                                                                              │
│           From: "Here's a tool, configure it yourself"                       │
│             To: "Tell me what data you need, I'll handle everything"         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### End State Interaction

**Scenario 1: Adding New Data (Track A)**
```
User: "I need NHS waiting times data for my healthcare analysis"

Agent: "I found 4 relevant NHS publications. Which would you like?"
       [Shows options via discover_by_keyword(['waiting', 'times'])]

User: "All of them"

Agent: [Configures, loads, validates, exports]
       "Done! 4.4M rows across 4 publications.
        I'll check for new data daily and notify you.
        Quick insight: A&E 4-hour waits hit 54% - lowest on record."
```

**Scenario 2: Querying Data (Track B)**
```
User: "Which regions have the worst A&E 4-hour performance?"

Agent: [Uses query_metric + aggregate_by]
       "Querying waiting_times_ae dataset, metric: four_hour_breaches,
        aggregating by region...

        Top 5 worst-performing regions (Q3 2024):
        1. London - 49.2% (target: 95%)
        2. South West - 51.8%
        3. East Midlands - 53.1%
        4. North West - 54.3%
        5. Yorkshire - 55.7%

        National average: 54.1%
        Data source: staging.tbl_ae_waiting_times_regional"

User: "How has London's performance changed over the last 6 months?"

Agent: [Uses compare_periods]
       "London A&E 4-hour performance trend:
        2024-Q1: 52.3%
        2024-Q2: 50.8%
        2024-Q3: 49.2%

        Declining performance - dropped 3.1 percentage points in 6 months."
```

**Scenario 3: Cross-Domain Analysis (Track B)**
```
User: "Is there a correlation between GP staffing and ADHD diagnosis rates?"

Agent: [Uses discover_by_keyword, query_metric on multiple datasets]
       "Analyzing correlation between workforce metrics and ADHD indicators...

        Found datasets:
        - pcn_workforce: GP FTE by ICB
        - adhd_indicators: Diagnosis rates by ICB

        Correlation (ICB level, Q3 2024): r = -0.42
        (Moderate negative correlation - ICBs with higher GP staffing
        tend to have lower ADHD diagnosis rates)

        Note: Correlation ≠ causation. Other factors at play."
```

---

## The Hard Truths

### Where Agents Work Well

- Repetitive, well-defined tasks (download, load, export)
- Pattern matching on stable formats
- Log analysis and error classification
- Query execution (if schema is clean)
- Scheduling and orchestration
- Notification and reporting

### Where Agents Fail

- Semantic understanding (what does this column MEAN?)
- Judgment calls (is this drift or error?)
- Context requiring domain knowledge
- Handling novel situations (format changes)
- Detecting subtle data quality issues
- Understanding user intent from ambiguous queries

### The 10 Hard Problems

1. **Semantic Column Drift** - NHS renames columns constantly
2. **Silent Extraction Failures** - Data loads but is garbage
3. **Suppressed Value Inconsistency** - Different symbols across publications
4. **Organisational Identity Changes** - NHS orgs merge/split/rename
5. **LLM Hallucinations** - Enrichment invents non-existent columns
6. **Format Evolution** - Excel → ZIP → CSV → API changes
7. **Contextual Understanding** - Footnotes contain critical info
8. **Partial/Revised Data** - Provisional data gets revised
9. **Query Understanding** - Ambiguous user requests
10. **Cascading Failures** - One bad decision propagates

### The Solution: Human-in-the-Loop

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     REALISTIC AGENTIC DATAWARP                               │
│                     "Agent Does Work, Human Validates"                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                          ┌─────────────────┐                                │
│                          │     HUMAN       │                                │
│                          │   (Judgment)    │                                │
│                          └────────┬────────┘                                │
│                                   │                                          │
│           ┌───────────────────────┼───────────────────────┐                 │
│           ▼                       ▼                       ▼                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │ Schema Review   │    │ Quality Review  │    │ Query Approval  │         │
│  │ [Approve/Edit]  │    │ [Accept/Flag]   │    │ [Run/Modify]    │         │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘         │
│           └───────────────────────┴───────────────────────┘                 │
│                                   │                                          │
│                                   ▼                                          │
│                          ┌─────────────────┐                                │
│                          │     AGENT       │                                │
│                          │  (Execution)    │                                │
│                          └─────────────────┘                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Roadmap

### Build Order

| Step | Component | Time | Value | Complexity |
|------|-----------|------|-------|------------|
| **TRACK A: Ingestion Automation** ||||
| 1 | `add_publication.py` CLI | 1 hr | Add URLs without manual YAML | Low |
| 2 | Log MCP Tools | 2 hrs | "What failed?" via Claude | Low |
| 3 | Golden Tests | 1.5 hrs | Catch bad loads early | Medium |
| 4 | Schema Fingerprinting | 2 hrs | Detect column drift/renames | Medium |
| 5 | Config MCP Tools | 2 hrs | Full config management via Claude | Low |
| **TRACK B: Intelligent Querying** ||||
| 6 | Populate Metadata Layer | 1 hr | Enrich metadata with KPI definitions | Low |
| 7 | Enhanced Query Tools | 4 hrs | Semantic discovery and intelligent queries | Medium |

### Step 1: add_publication.py CLI

**Purpose:** Classify URLs and generate YAML config automatically

**Input:**
```bash
python scripts/add_publication.py https://digital.nhs.uk/.../new-publication
```

**Output:**
```
Detected: NHS Digital, templatable, monthly
Landing page: https://digital.nhs.uk/.../new-publication
Pattern: {landing_page}/{month_name}-{year}

Generated config:
  new_publication:
    name: "New Publication Name"
    frequency: monthly
    landing_page: https://digital.nhs.uk/.../new-publication
    periods:
      mode: schedule
      start: "2024-01"
      end: current
      publication_lag_weeks: 6
    url:
      mode: template
      pattern: "{landing_page}/{month_name}-{year}"

Append to publications_v2.yaml? [y/n]: y
Added to config.
```

**Implementation:**
1. Parse URL to detect source (NHS Digital vs NHS England)
2. Check for hash codes (indicates explicit mode needed)
3. Extract landing page and period from URL
4. Detect frequency (monthly/quarterly) from URL pattern
5. Generate YAML config block
6. Optionally append to publications_v2.yaml

**Files to create:**
- `scripts/add_publication.py` (~150 lines)

### Step 2: Log MCP Tools

**Purpose:** Query logs conversationally via Claude Desktop

**Tools:**
```python
list_runs(limit=10)           # Recent backfill runs
get_summary(run_id)           # Success/fail/skipped counts
find_errors(run_id)           # All ERROR entries
find_failures(run_id)         # Failed periods with reasons
trace_period(run_id, period)  # Full pipeline trace
is_running(run_id)            # Check if active
```

**Example interaction:**
```
User: "What happened in the last backfill?"

Claude: [calls list_runs(), get_summary(), find_failures()]
        "The last backfill ran at 6am. 5 succeeded, 2 failed.

         Failures:
         - A&E: 404 (URL changed)
         - RTT: Schema drift (new column)

         Suggested fixes:
         - A&E: Update URL pattern
         - RTT: Approve new column

         Want me to fix these?"
```

**Implementation:**
- Add tools to existing MCP server
- Parse log files (append-only, safe to read during backfill)
- Detect active runs via file mtime

**Files to modify:**
- `mcp_server/stdio_server.py` (+100 lines)

### Step 3: Golden Tests

**Purpose:** Validate every load, catch problems before commit

**Tests:**
```python
GOLDEN_TESTS = [
    {
        "name": "row_count_sanity",
        "query": "SELECT COUNT(*) FROM {table} WHERE _period = '{period}'",
        "expect": "BETWEEN 100 AND 50000"
    },
    {
        "name": "no_future_dates",
        "query": "SELECT COUNT(*) FROM {table} WHERE _period_end > CURRENT_DATE",
        "expect": "= 0"
    },
    {
        "name": "null_rate_check",
        "query": "SELECT COUNT(*) FILTER (WHERE org_code IS NULL) * 100.0 / COUNT(*) FROM {table}",
        "expect": "< 5"
    },
    {
        "name": "required_columns",
        "query": "SELECT {required_cols} FROM {table} LIMIT 1",
        "expect": "NO_ERROR"
    }
]
```

**Workflow:**
1. After load, run golden tests
2. If all pass → commit
3. If any fail → rollback, alert human

**Files to create:**
- `src/datawarp/validation/golden_tests.py` (~100 lines)

**Files to modify:**
- `scripts/backfill.py` (integrate validation)

### Step 4: Schema Fingerprinting

**Purpose:** Detect column drift/renames across periods

**Fingerprint structure:**
```yaml
schema_fingerprint:
  adhd:
    columns:
      - name: "org_code"
        type: VARCHAR
        nullable: false
        patterns: ["^[A-Z0-9]{3,5}$"]
      - name: "referrals"
        type: INTEGER
        nullable: true
        aliases: ["Referrals", "Referrals Received", "New Referrals"]
```

**Detection logic:**
```python
def detect_drift(new_schema, golden_schema):
    drift = []
    for col in new_schema:
        if col.name in golden_schema:
            continue  # Exact match

        # Check for rename (fuzzy match)
        for golden_col in golden_schema:
            similarity = fuzzy_match(col.name, golden_col.aliases)
            if similarity > 0.85:
                drift.append({
                    "type": "RENAME",
                    "old": golden_col.name,
                    "new": col.name,
                    "confidence": similarity,
                    "suggestion": f"Map '{col.name}' to '{golden_col.name}'"
                })
                break
        else:
            drift.append({
                "type": "NEW",
                "name": col.name,
                "suggestion": "Add new column"
            })

    return drift
```

**Files to create:**
- `src/datawarp/validation/schema_fingerprint.py` (~150 lines)
- `config/schema_fingerprints/` (per-publication YAML files)

### Step 5: Config MCP Tools

**Purpose:** Full config management via Claude

**Tools:**
```python
list_publications()           # Current config
classify_url(url)             # Pattern detection
generate_config(url)          # YAML generation
add_publication(config)       # Append to YAML
update_urls(pub, urls)        # Update existing
validate_config()             # Validate syntax
```

**Example interaction:**
```
User: "Add the new CAMHS waiting times publication"

Claude: [calls classify_url, generate_config]
        "Found it. NHS Digital, monthly, template pattern.
         Here's the config: [shows YAML]
         Add to publications_v2.yaml?"

User: "Yes"

Claude: [calls add_publication]
        "Added. Run backfill now?"
```

**Files to modify:**
- `mcp_server/stdio_server.py` (+150 lines)

---

### Step 6: Populate Metadata Layer

**Purpose:** Enrich dataset metadata with KPI definitions using existing column metadata

**The Insight:** We already have semantic metadata in `tbl_column_metadata`:
- `is_measure = true` → These are the KPIs
- `is_dimension = true` → These are the filters (geography, time, age)
- `query_keywords` → Searchable terms for discovery

**Just need to consolidate this into dataset-level metadata for agent consumption.**

**Implementation:**
```python
# Script: scripts/populate_dataset_metadata.py

def populate_metadata(source_code: str):
    """Extract metadata from tbl_column_metadata and populate JSONB."""

    # Get all measures for this dataset
    measures = query("""
        SELECT column_name, description, data_type, query_keywords
        FROM datawarp.tbl_column_metadata
        WHERE canonical_source_code = %s AND is_measure = true
    """, source_code)

    # Get all dimensions
    dimensions = query("""
        SELECT column_name, description, query_keywords
        FROM datawarp.tbl_column_metadata
        WHERE canonical_source_code = %s AND is_dimension = true
    """, source_code)

    # Build metadata JSON
    metadata = {
        "kpis": [
            {
                "column": m['column_name'],
                "label": m['description'],
                "unit": infer_unit(m['description']),  # 'percentage', 'count', etc.
                "aggregation": infer_aggregation(m['data_type']),
                "query_keywords": m['query_keywords']
            }
            for m in measures
        ],
        "dimensions": [
            {
                "column": d['column_name'],
                "type": infer_dimension_type(d['query_keywords']),
                "query_keywords": d['query_keywords']
            }
            for d in dimensions
        ],
        "granularity": infer_granularity(dimensions),
        "record_type": infer_record_type(source_code),
        "typical_queries": generate_typical_queries(measures, dimensions)
    }

    # Update tbl_canonical_sources
    update("""
        UPDATE datawarp.tbl_canonical_sources
        SET metadata = %s::jsonb
        WHERE canonical_code = %s
    """, json.dumps(metadata), source_code)
```

**Example metadata JSONB:**
```json
{
  "kpis": [
    {
      "column": "prevalence_rate",
      "label": "ADHD Prevalence Rate",
      "unit": "percentage",
      "aggregation": "weighted_average",
      "query_keywords": ["prevalence", "ADHD", "rate"]
    }
  ],
  "dimensions": [
    {
      "column": "geography_level",
      "type": "geography",
      "query_keywords": ["geography", "level", "area"]
    },
    {
      "column": "time_period",
      "type": "temporal",
      "query_keywords": ["period", "date", "quarter"]
    }
  ],
  "granularity": "icb_quarterly",
  "record_type": "aggregations",
  "typical_queries": [
    "National prevalence trend over time",
    "ICB-level prevalence by age group"
  ]
}
```

**Usage:**
```bash
# Populate all datasets
python scripts/populate_dataset_metadata.py --all

# Populate specific domain
python scripts/populate_dataset_metadata.py --domain mental_health

# Update single dataset
python scripts/populate_dataset_metadata.py --dataset adhd_prevalence_estimate
```

**Files to create:**
- `scripts/populate_dataset_metadata.py` (~150 lines)

**Time:** 1 hour (script) + 10 minutes (run for 181 datasets)

---

### Step 7: Enhanced Query Tools

**Purpose:** Enable semantic discovery and intelligent querying without schema knowledge

**New MCP Tools:**

#### 1. `discover_by_keyword(keywords)`
```python
def discover_by_keyword(keywords: List[str]) -> List[Dict]:
    """Find datasets using semantic search on query_keywords."""

    # Search tbl_column_metadata.query_keywords (uses GIN index)
    sql = """
    SELECT DISTINCT
        cm.canonical_source_code,
        cs.description,
        cs.domain,
        COUNT(*) FILTER (WHERE cm.is_measure = true) as kpi_count
    FROM datawarp.tbl_column_metadata cm
    JOIN datawarp.tbl_canonical_sources cs
        ON cm.canonical_source_code = cs.canonical_code
    WHERE cm.query_keywords && %s  -- Array overlap operator
    GROUP BY cm.canonical_source_code, cs.description, cs.domain
    ORDER BY kpi_count DESC
    """

    return query(sql, keywords)
```

**Example:**
```
Agent: discover_by_keyword(['adhd', 'prevalence'])

Returns:
[
  {
    "dataset": "adhd_prevalence_estimate",
    "description": "ADHD prevalence by geography and age",
    "domain": "mental_health",
    "kpi_count": 3
  },
  {
    "dataset": "adhd_indicators",
    "description": "Key ADHD performance indicators",
    "domain": "mental_health",
    "kpi_count": 5
  }
]
```

#### 2. `get_kpis(dataset)`
```python
def get_kpis(dataset_code: str) -> List[Dict]:
    """Get list of KPIs (measures) for a dataset."""

    # Option 1: From metadata JSONB
    sql = """
    SELECT metadata->'kpis' as kpis
    FROM datawarp.tbl_canonical_sources
    WHERE canonical_code = %s
    """

    # Option 2: Live from column metadata (if JSONB not populated)
    sql_fallback = """
    SELECT
        column_name,
        description,
        data_type,
        query_keywords
    FROM datawarp.tbl_column_metadata
    WHERE canonical_source_code = %s
      AND is_measure = true
    ORDER BY column_name
    """
```

**Example:**
```
Agent: get_kpis('adhd_prevalence_estimate')

Returns:
[
  {
    "column": "prevalence_rate",
    "label": "ADHD Prevalence Rate",
    "unit": "percentage",
    "aggregation": "weighted_average"
  },
  {
    "column": "diagnosis_count",
    "label": "Number of Diagnoses",
    "unit": "count",
    "aggregation": "sum"
  }
]
```

#### 3. `query_metric(dataset, metric, filters)`
```python
def query_metric(dataset: str, metric: str, filters: Dict) -> Dict:
    """Query a specific metric with dimensional filters."""

    # 1. Get metadata to understand schema
    metadata = get_dataset_metadata(dataset)

    # 2. Find the measure column
    measure_col = find_column(metadata, is_measure=True, name=metric)

    # 3. Find dimension columns for filtering
    geography_col = find_column(metadata, is_dimension=True,
                               keywords=['geography', 'location'])
    time_col = find_column(metadata, is_dimension=True,
                          keywords=['time', 'period', 'date'])

    # 4. Generate SQL dynamically
    sql = f"""
    SELECT
        {measure_col} as value,
        {time_col} as period,
        {geography_col} as geography
    FROM staging.tbl_{dataset}
    WHERE {geography_col} = %(geography)s
      AND {time_col} = %(period)s
    """

    return query(sql, filters)
```

**Example:**
```
Agent: query_metric(
    dataset='adhd_prevalence_estimate',
    metric='prevalence_rate',
    filters={'geography': 'national', 'period': '2024-Q3'}
)

Returns:
{
  "value": 4.2,
  "period": "2024-Q3",
  "geography": "national",
  "unit": "percentage"
}
```

#### 4. `aggregate_by(dataset, metric, dimension, filters)`
```python
def aggregate_by(dataset: str, metric: str, group_by: str,
                 filters: Dict = None) -> List[Dict]:
    """Aggregate a metric by a dimension."""

    metadata = get_dataset_metadata(dataset)

    # Find columns
    measure_col = find_column(metadata, is_measure=True, name=metric)
    dimension_col = find_column(metadata, is_dimension=True,
                               keywords=[group_by])

    # Determine aggregation method from metadata
    kpi_meta = get_kpi_metadata(dataset, metric)
    agg_method = kpi_meta.get('aggregation', 'AVG')

    # Build GROUP BY query
    sql = f"""
    SELECT
        {dimension_col} as dimension_value,
        {agg_method}({measure_col}) as metric_value
    FROM staging.tbl_{dataset}
    WHERE geography_level = %(geography_level)s
    GROUP BY {dimension_col}
    ORDER BY {dimension_col}
    """

    return query(sql, filters or {})
```

**Example:**
```
Agent: aggregate_by(
    dataset='adhd_prevalence_estimate',
    metric='prevalence_rate',
    group_by='age_band',
    filters={'geography_level': 'icb', 'geography_code': 'E54000033'}
)

Returns:
[
  {"dimension_value": "0-17", "metric_value": 2.1},
  {"dimension_value": "18-64", "metric_value": 5.3},
  {"dimension_value": "65+", "metric_value": 1.8}
]
```

#### 5. `compare_periods(dataset, metric, periods, filters)`
```python
def compare_periods(dataset: str, metric: str, periods: List[str],
                   filters: Dict = None) -> List[Dict]:
    """Compare a metric across multiple time periods."""

    metadata = get_dataset_metadata(dataset)
    measure_col = find_column(metadata, is_measure=True, name=metric)
    time_col = find_column(metadata, is_dimension=True,
                          keywords=['time', 'period'])

    sql = f"""
    SELECT
        {time_col} as period,
        {measure_col} as value
    FROM staging.tbl_{dataset}
    WHERE {time_col} = ANY(%(periods)s)
      AND geography_level = %(geography_level)s
    ORDER BY {time_col}
    """

    return query(sql, {'periods': periods, **filters})
```

**Example:**
```
Agent: compare_periods(
    dataset='adhd_prevalence_estimate',
    metric='prevalence_rate',
    periods=['2024-Q2', '2024-Q3'],
    filters={'geography_level': 'national'}
)

Returns:
[
  {"period": "2024-Q2", "value": 4.1},
  {"period": "2024-Q3", "value": 4.2}
]
```

**Files to modify:**
- `mcp_server/stdio_server.py` (+250 lines for new tools)
- `mcp_server/backends/postgres.py` (+100 lines for metadata queries)

**Time:** 4 hours

---

### Track A vs Track B

**Track A (Steps 1-5): Ingestion Automation**
- Focus: Automate adding publications and handling failures
- Benefit: Reduce human effort from 100% → 10% for data ingestion
- User: Data engineers managing the pipeline

**Track B (Steps 6-7): Intelligent Querying**
- Focus: Enable semantic discovery and query without schema knowledge
- Benefit: Agents can answer questions without knowing table structures
- User: Analysts, agents, end-users querying the data

**They work together:**
```
Track A loads data  →  staging.tbl_* + tbl_column_metadata populated
                                ↓
Track B enables queries  →  Agents discover and query KPIs intelligently
```

**Implementation order:**
- Can work in parallel (different code paths)
- Step 6 depends on enrichment already running (is_measure flags)
- Step 7 depends on Step 6 (needs metadata JSONB populated)

---

## Architecture

### Component Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         HOW COMPONENTS CONNECT                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                        ┌───────────────────┐                                │
│                        │   Claude Desktop  │                                │
│                        │   / Claude Code   │                                │
│                        │   (Orchestrator)  │                                │
│                        └─────────┬─────────┘                                │
│                                  │                                           │
│                    ┌─────────────┼─────────────┐                            │
│                    │             │             │                            │
│                    ▼             ▼             ▼                            │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         MCP TOOLS LAYER                              │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │                                                                      │   │
│  │  CONFIG TOOLS          LOG TOOLS           DATA TOOLS (existing)    │   │
│  │  ┌────────────────┐   ┌────────────────┐   ┌────────────────┐       │   │
│  │  │• classify_url  │   │• list_runs     │   │• list_datasets │       │   │
│  │  │• generate_cfg  │   │• get_summary   │   │• get_metadata  │       │   │
│  │  │• add_pub       │   │• find_errors   │   │• query         │       │   │
│  │  │• update_urls   │   │• trace_period  │   │                │       │   │
│  │  └───────┬────────┘   └───────┬────────┘   └───────┬────────┘       │   │
│  │          │                    │                    │                │   │
│  │  ┌───────────────────────────────────────────────────────────────┐  │   │
│  │  │              ENHANCED QUERY TOOLS (Track B - Steps 6-7)       │  │   │
│  │  │  ┌────────────────────┐  ┌────────────────────┐               │  │   │
│  │  │  │ Semantic Discovery │  │ Intelligent Query  │               │  │   │
│  │  │  ├────────────────────┤  ├────────────────────┤               │  │   │
│  │  │  │• discover_by_      │  │• get_kpis          │               │  │   │
│  │  │  │  keyword           │  │• query_metric      │               │  │   │
│  │  │  │                    │  │• aggregate_by      │               │  │   │
│  │  │  │                    │  │• compare_periods   │               │  │   │
│  │  │  └──────────┬─────────┘  └──────────┬─────────┘               │  │   │
│  │  │             └────────────────────────┘                         │  │   │
│  │  │                          │                                     │  │   │
│  │  │             Reads: tbl_column_metadata.is_measure,             │  │   │
│  │  │                    tbl_canonical_sources.metadata JSONB        │  │   │
│  │  └───────────────────────────────────────────────────────────────┘  │   │
│  │          │                    │                    │                │   │
│  └──────────┼────────────────────┼────────────────────┼────────────────┘   │
│             │                    │                    │                     │
│             ▼                    ▼                    ▼                     │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                       CORE DATAWARP                                  │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │                                                                      │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │   Config    │  │   Backfill  │  │  Extractor  │  │   Loader    │ │   │
│  │  │publications │  │ backfill.py │  │ extractor.py│  │ pipeline.py │ │   │
│  │  │_v2.yaml     │  │             │  │             │  │             │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  │         │                │                │                │        │   │
│  │         ▼                ▼                ▼                ▼        │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │                    VALIDATION LAYER                         │    │   │
│  │  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐   │    │   │
│  │  │  │ Golden Tests  │  │   Schema      │  │  Confidence   │   │    │   │
│  │  │  │ (Step 3)      │  │ Fingerprint   │  │    Scores     │   │    │   │
│  │  │  │               │  │ (Step 4)      │  │               │   │    │   │
│  │  │  └───────────────┘  └───────────────┘  └───────────────┘   │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  │                                │                                    │   │
│  │                                ▼                                    │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │                      DATA LAYER                             │    │   │
│  │  │  PostgreSQL  │  Parquet  │  Logs  │  State  │  Catalog      │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  │                                                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Human-Agent Interaction Pattern

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HUMAN-AGENT INTERACTION PATTERN                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                          ┌─────────────────┐                                │
│                          │      HUMAN      │                                │
│                          │                 │                                │
│                          │  • Intent       │                                │
│                          │  • Approval     │                                │
│                          │  • Judgment     │                                │
│                          └────────┬────────┘                                │
│                                   │                                          │
│                                   │ "Add new publication"                   │
│                                   │ "Yes, approve that"                     │
│                                   │ "No, that looks wrong"                  │
│                                   │                                          │
│                                   ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                             AGENT                                      │  │
│  │                                                                        │  │
│  │   DOES AUTOMATICALLY:              ASKS HUMAN:                        │  │
│  │   ├─ Discover new periods          ├─ "Add this publication?"         │  │
│  │   ├─ Generate config               ├─ "This column renamed, map it?"  │  │
│  │   ├─ Run backfill                  ├─ "Unusual data, investigate?"    │  │
│  │   ├─ Validate results              ├─ "Low confidence, please review" │  │
│  │   ├─ Detect schema drift           └─ "Unknown error, need help"      │  │
│  │   ├─ Export to parquet                                                │  │
│  │   ├─ Update catalog                                                   │  │
│  │   └─ Generate insights                                                │  │
│  │                                                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Workflow Evolution

### Human Effort Reduction

```
TODAY:
┌─────────────────────────────────────────────────────────────────────────────┐
│ Human ──► YAML ──► CLI ──► Logs ──► grep ──► Fix ──► Repeat                │
│ Human effort: ████████████████████████████████████ 100%                    │
└─────────────────────────────────────────────────────────────────────────────┘

AFTER STEP 1 (add_publication.py):
┌─────────────────────────────────────────────────────────────────────────────┐
│ Human ──► URL ──► Agent generates ──► Human approves ──► CLI ──► ...       │
│ Human effort: ██████████████████████████████░░░░░░ 80%                     │
└─────────────────────────────────────────────────────────────────────────────┘

AFTER STEP 2 (Log MCP):
┌─────────────────────────────────────────────────────────────────────────────┐
│ ... ──► CLI ──► Agent explains results ──► Human decides ──► ...           │
│ Human effort: ████████████████████░░░░░░░░░░░░░░░░ 60%                     │
└─────────────────────────────────────────────────────────────────────────────┘

AFTER STEP 3 (Golden Tests):
┌─────────────────────────────────────────────────────────────────────────────┐
│ ... ──► Auto-validation ──► Only failures need human ──► ...               │
│ Human effort: ████████████░░░░░░░░░░░░░░░░░░░░░░░░ 40%                     │
└─────────────────────────────────────────────────────────────────────────────┘

AFTER STEP 4 (Schema Fingerprinting):
┌─────────────────────────────────────────────────────────────────────────────┐
│ ... ──► Auto-mapping ──► Human confirms suggestions ──► ...                │
│ Human effort: ██████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 25%                     │
└─────────────────────────────────────────────────────────────────────────────┘

AFTER STEP 5 (Full Track A - Ingestion Automation):
┌─────────────────────────────────────────────────────────────────────────────┐
│ Human: "Add CAMHS data" ──► Agent does everything ──► Human: "OK"          │
│ Ingestion effort: ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 10%                    │
└─────────────────────────────────────────────────────────────────────────────┘

AFTER STEP 7 (Full Track B - Intelligent Querying):
┌─────────────────────────────────────────────────────────────────────────────┐
│ Human: "What's ADHD prevalence?" ──► Agent: "4.2%" (no schema knowledge)   │
│ Query complexity: ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 5%                    │
│ (Before: Find table, understand schema, write SQL, debug)                  │
│ (After: Ask question in natural language, get answer)                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Next Session: Start Building

### Recommended Start Options

#### Option A: Track A First (Ingestion Automation)

**Start with Step 1:** `add_publication.py`

**Why:**
- Immediately useful for adding new publications
- No infrastructure dependencies
- Foundation for Config MCP tools
- Quick win, builds momentum

**Deliverable:**
```bash
python scripts/add_publication.py https://digital.nhs.uk/.../new-publication
# Detects pattern, generates YAML, optionally appends to config
```

**Time:** 1 hour

**Then continue:** Steps 2-5 (Log tools, Golden tests, Fingerprinting, Config MCP)

---

#### Option B: Track B First (Intelligent Querying)

**Start with Step 6:** `populate_dataset_metadata.py`

**Why:**
- Unlocks agent querying immediately
- Uses existing data (tbl_column_metadata already populated)
- High value for end-users/analysts
- Demonstrates AI-native querying

**Deliverable:**
```bash
python scripts/populate_dataset_metadata.py --all
# Populates metadata JSONB for 181 datasets in ~10 minutes
```

**Time:** 1 hour script + 10 min execution

**Then continue:** Step 7 (Enhanced query tools)

---

#### Recommendation: Start Track B (Steps 6-7)

**Reasons:**
1. **Faster time to value** - Enables intelligent querying in ~5 hours total
2. **No dependencies** - Uses existing enriched metadata
3. **High impact** - Changes how users interact with data
4. **Demonstrates vision** - Shows "AI-native data platform" in action
5. **Works with current data** - Don't need to add new publications to see benefit

Track A is valuable but focused on pipeline operations. Track B transforms user experience.

### Files to Read First

**For Track A (Ingestion Automation):**
1. `docs/agentic/agentic_vision_roadmap.md` (this file)
2. `config/publications_v2.yaml` (understand current config format)
3. `src/datawarp/utils/url_resolver.py` (existing URL pattern logic)
4. `scripts/backfill.py` (where golden tests would integrate)

**For Track B (Intelligent Querying):**
1. `docs/agentic/agentic_vision_roadmap.md` (this file - Steps 6-7)
2. `docs/architecture/metadata_driven_reporting.md` (detailed design)
3. `scripts/schema/05_create_metadata_tables.sql` (metadata schema)
4. `src/datawarp/storage/repository.py` (where is_measure/is_dimension stored)
5. `mcp_server/stdio_server.py` (current MCP tools to enhance)

---

## Success Metrics

### Track A (Ingestion Automation)

| Metric | Current | After Step 5 |
|--------|---------|--------------|
| Time to add new publication | 15-30 min | 2 min (mostly approval) |
| Time to diagnose failure | 10-30 min | 1 min (agent explains) |
| Silent data corruption | Possible | Caught by golden tests |
| Column drift handling | Manual | Semi-automatic |
| Human effort per backfill | 100% | 10% |

### Track B (Intelligent Querying)

| Metric | Current | After Step 7 |
|--------|---------|--------------|
| MCP calls to answer "What's X metric?" | 3-5 calls | 1 call |
| Schema knowledge required | High (must know table/columns) | None (semantic search) |
| Time to discover relevant datasets | 5-10 min (manual search) | 10 sec (keyword search) |
| Query complexity for analysts | Must write SQL | Natural language |
| Cross-dataset queries | Very difficult (join staging tables) | Simple (metadata-guided) |
| Agent query success rate | ~40% (schema confusion) | ~90% (metadata-driven) |

---

## References

- Session 23 discussion (2026-01-17) - Initial agentic vision
- Session 27 discussion (2026-01-17) - Added metadata-driven reporting (Track B)
- IMPLEMENTATION_TASKS.md → "Agentic DataWarp" section
- TASKS.md → Session 23 summary
- `docs/architecture/metadata_driven_reporting.md` - Detailed Track B design
- `docs/architecture/super_dataset_simple.md` - Alternative approaches considered

---

## Quick Reference: Two Tracks

### Track A: Ingestion Automation (Steps 1-5)
**Goal:** Reduce human effort in pipeline operations
**Users:** Data engineers managing DataWarp
**Value:** 100% → 10% effort for adding/maintaining publications

| Step | Script/File | Time | Dependencies |
|------|-------------|------|--------------|
| 1 | `scripts/add_publication.py` | 1 hr | None |
| 2 | `mcp_server/stdio_server.py` (log tools) | 2 hrs | None |
| 3 | `src/datawarp/validation/golden_tests.py` | 1.5 hrs | None |
| 4 | `src/datawarp/validation/schema_fingerprint.py` | 2 hrs | None |
| 5 | `mcp_server/stdio_server.py` (config tools) | 2 hrs | Step 1 |
| **Total** | | **8.5 hrs** | |

### Track B: Intelligent Querying (Steps 6-7)
**Goal:** Enable semantic discovery and query without schema knowledge
**Users:** Analysts, agents, end-users querying data
**Value:** 3-5 MCP calls → 1 call, no schema knowledge needed

| Step | Script/File | Time | Dependencies |
|------|-------------|------|--------------|
| 6 | `scripts/populate_dataset_metadata.py` | 1 hr | Enrichment running (✅ already is) |
| 7 | `mcp_server/stdio_server.py` (query tools) | 4 hrs | Step 6 |
| **Total** | | **5 hrs** | |

### Which Track First?

**Start Track B if you want to:**
- ✅ Demonstrate AI-native querying immediately
- ✅ Improve analyst/agent experience today
- ✅ Use existing data (no need to add publications)
- ✅ Show value to end-users quickly

**Start Track A if you want to:**
- ✅ Reduce operational burden first
- ✅ Make adding publications easier
- ✅ Build monitoring/validation infrastructure
- ✅ Focus on data engineering workflows

**Both tracks are independent and can be developed in parallel.**

---

## Implementation Checklist

### Track B Quick Start (Recommended)

- [ ] Read `docs/architecture/metadata_driven_reporting.md`
- [ ] Verify `tbl_column_metadata` has data: `SELECT COUNT(*) FROM datawarp.tbl_column_metadata WHERE is_measure = true;`
- [ ] Implement `scripts/populate_dataset_metadata.py` (1 hour)
- [ ] Run: `python scripts/populate_dataset_metadata.py --all` (10 minutes)
- [ ] Verify: `SELECT metadata FROM datawarp.tbl_canonical_sources WHERE canonical_code = 'adhd_prevalence_estimate';`
- [ ] Implement enhanced MCP tools in `mcp_server/stdio_server.py` (4 hours):
  - [ ] `discover_by_keyword()`
  - [ ] `get_kpis()`
  - [ ] `query_metric()`
  - [ ] `aggregate_by()`
  - [ ] `compare_periods()`
- [ ] Test with ADHD datasets via Claude Desktop
- [ ] Document examples in `docs/agentic/query_examples.md`

**Total time:** ~6 hours to full intelligent querying

---

*"Agent as intelligent assistant, not replacement. Human-in-the-loop for judgment calls."*
