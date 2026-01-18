# Metadata-Driven Reporting Layer

**Created:** 2026-01-17 19:20 UTC
**Updated:** 2026-01-17 20:00 UTC (Aligned with real ICB scorecard structure)
**Purpose:** Use existing metadata to enable intelligent agent querying (no new tables needed)
**Reference:** See `icb_scorecard_structure.md` for real-world ICB scorecard analysis

---

## The Insight (Updated with Real ICB Scorecard Context)

**We already have the semantic layer foundation!**

```
tbl_column_metadata:
├─ is_measure = true     → These are the metrics/KPIs
├─ is_dimension = true   → These are the filters (geography, time, age, provider)
├─ query_keywords        → Searchable terms for discovery
└─ description           → What the column means
```

**Real ICB Scorecard Structure (485 metrics across 40+ domains):**
- **4 operational lenses**: Provider, ICB, Sub-ICB, GP Practice
- **2 benchmarking lenses**: Region, National
- **37% have targets** (performance metrics), **63% are intelligence** (trend/correlation analysis)
- **Multi-level**: Same metric available at different organizational levels

**We need to EXTEND metadata to capture:**
1. Which organizational lens(es) this metric supports
2. Whether it has a performance target or is intelligence-only
3. Domain classification (Cancer, Diagnostics, Mental Health, etc.)
4. Benchmark availability (regional/national comparators)

---

## What We Have (Already Exists)

### Column-Level Metadata (tbl_column_metadata)

```sql
SELECT
    canonical_source_code,     -- 'adhd_prevalence_estimate'
    column_name,               -- 'prevalence_rate'
    is_measure,                -- true (this is a KPI!)
    is_dimension,              -- false
    query_keywords,            -- {'prevalence', 'ADHD', 'diagnosis rate'}
    description,               -- 'Percentage of registered patients with ADHD'
    data_type                  -- 'numeric'
FROM datawarp.tbl_column_metadata
WHERE canonical_source_code = 'adhd_prevalence_estimate';
```

**Example data:**
```
canonical_source_code       | column_name       | is_measure | is_dimension | query_keywords
---------------------------|-------------------|------------|--------------|------------------
adhd_prevalence_estimate   | prevalence_rate   | true       | false        | {prevalence, ADHD, rate}
adhd_prevalence_estimate   | geography_level   | false      | true         | {geography, level, area}
adhd_prevalence_estimate   | time_period       | false      | true         | {period, date, quarter}
adhd_prevalence_estimate   | age_band          | false      | true         | {age, band, group}
```

**Status:** ✅ Already populated by LLM enrichment during backfill

---

### Dataset-Level Metadata (tbl_canonical_sources)

```sql
SELECT
    canonical_code,            -- 'adhd_prevalence_estimate'
    description,               -- 'ADHD prevalence estimates by geography and age'
    domain,                    -- 'mental_health'
    metadata                   -- JSONB (mostly empty currently)
FROM datawarp.tbl_canonical_sources;
```

**Status:** 🟡 Schema exists, metadata JSONB mostly unpopulated

---

## What We Need to Add

### Enhanced metadata JSONB Structure (Aligned with ICB Scorecard)

```sql
UPDATE datawarp.tbl_canonical_sources
SET metadata = '{
  "domain": "mental_health",  -- Maps to ICB scorecard domains
  "scorecard_category": "MHSMS",  -- ICB scorecard category if applicable

  "organizational_lenses": {
    "provider": true,      -- Available at provider level?
    "icb": true,          -- Available at ICB system level?
    "sub_icb": false,     -- Available at locality level?
    "gp_practice": false, -- Available at practice level?
    "region": true,       -- Regional benchmarking available?
    "national": true      -- National benchmarking available?
  },

  "kpis": [
    {
      "column": "prevalence_rate",
      "label": "ADHD Prevalence Rate",
      "description": "Percentage of registered patients with ADHD diagnosis",
      "unit": "percentage",
      "aggregation": "weighted_average",
      "has_target": false,  -- Is this a performance metric with target?
      "metric_type": "intelligence",  -- "performance" or "intelligence"
      "target_value": null,  -- If has_target=true, what's the target?
      "target_direction": null,  -- "higher_better", "lower_better", or null
      "benchmark_sources": ["national_average", "regional_average", "icb_peers"]
    },
    {
      "column": "diagnosis_count",
      "label": "ADHD Diagnosis Count",
      "description": "Number of patients diagnosed with ADHD",
      "unit": "count",
      "aggregation": "sum"
    }
  ],
  "dimensions": [
    {
      "column": "geography_level",
      "values": ["national", "region", "icb", "subicb", "provider"]
    },
    {
      "column": "time_period",
      "type": "quarterly",
      "range": "2023-Q1 to current"
    },
    {
      "column": "age_band",
      "values": ["0-17", "18-64", "65+", "All"]
    }
  ],
  "granularity": "icb_quarterly",
  "record_type": "aggregations",
  "typical_queries": [
    "National prevalence trend over time",
    "ICB-level prevalence by age group",
    "Regional comparisons"
  ],
  "related_datasets": [
    "adhd_indicators",
    "adhd_meds_prescribed_prev_6m"
  ]
}'::jsonb
WHERE canonical_code = 'adhd_prevalence_estimate';
```

---

## The 4-Lens Query Model

### Real ICB Analytics Operate at Multiple Levels

```
Same metric "ADHD Waiting Time", different organizational lens:

Provider Lens:
  Question: "Is Norfolk & Suffolk FT delivering on ADHD contract?"
  Data: Provider-level performance
  Use: Contract monitoring, provider comparison

ICB Lens:
  Question: "How is Norfolk & Waveney ICB performing on ADHD overall?"
  Data: System-wide aggregate (all providers + primary care)
  Use: System performance, national benchmarking

Sub-ICB Lens:
  Question: "Which localities in Norfolk have longest ADHD waits?"
  Data: Place-based analysis (Norwich, Great Yarmouth, etc.)
  Use: Resource allocation, health inequalities

GP Practice Lens:
  Question: "Which practices refer high volumes to ADHD services?"
  Data: Practice-level referrals
  Use: Primary care performance, outlier identification
```

### Lens-Aware Data Model

**DataWarp tables must capture organizational level:**

```sql
-- Example ADHD table with lens support
CREATE TABLE staging.tbl_adhd_prevalence_estimate (
    -- Organizational lens dimensions
    provider_code VARCHAR(20),        -- Provider lens
    icb_code VARCHAR(20),             -- ICB lens
    sub_icb_code VARCHAR(20),         -- Sub-ICB lens
    gp_practice_code VARCHAR(20),     -- GP Practice lens

    -- Or use a flexible lens column
    geography_level VARCHAR(20),      -- 'provider', 'icb', 'sub_icb', 'gp_practice'
    geography_code VARCHAR(20),       -- The actual code
    geography_name VARCHAR(200),      -- Display name

    -- Time dimension
    time_period VARCHAR(20),

    -- Measures
    prevalence_rate NUMERIC,
    diagnosis_count INTEGER,

    -- Metadata
    _load_id INTEGER,
    _loaded_at TIMESTAMP
);
```

**Metadata captures lens availability:**

```json
{
  "organizational_lenses": {
    "provider": false,     -- ADHD prevalence not tracked at provider level
    "icb": true,          -- Available at ICB level ✓
    "sub_icb": true,      -- Available at locality level ✓
    "gp_practice": true   -- Available at practice level ✓
  }
}
```

---

## How MCP Server Uses This

### Enhanced Tool: `discover_datasets()`

**Agent asks:** "What ADHD data is available?"

**MCP logic:**
```python
def discover_datasets(keywords: List[str]) -> List[Dict]:
    """Find datasets using column-level query_keywords."""

    # Search tbl_column_metadata.query_keywords
    sql = """
    SELECT DISTINCT canonical_source_code, description
    FROM datawarp.tbl_column_metadata
    WHERE query_keywords && %s  -- Array overlap operator
    """

    results = query(sql, keywords=['adhd', 'prevalence'])

    # Returns:
    # - adhd_prevalence_estimate
    # - adhd_indicators
    # - adhd_meds_prescribed_prev_6m

    return results
```

---

### Enhanced Tool: `get_kpis()`

**Agent asks:** "What KPIs are available in ADHD prevalence dataset?"

**MCP logic:**
```python
def get_kpis(dataset_code: str) -> List[Dict]:
    """Get list of KPIs (measures) for a dataset."""

    # Option 1: From metadata JSONB
    sql = """
    SELECT metadata->'kpis' as kpis
    FROM datawarp.tbl_canonical_sources
    WHERE canonical_code = %s
    """

    # Option 2: From column metadata (if JSONB not populated)
    sql = """
    SELECT column_name, description, data_type, query_keywords
    FROM datawarp.tbl_column_metadata
    WHERE canonical_source_code = %s
      AND is_measure = true
    """

    # Returns:
    # [
    #   {"column": "prevalence_rate", "label": "ADHD Prevalence Rate", "unit": "percentage"},
    #   {"column": "diagnosis_count", "label": "Diagnosis Count", "unit": "count"}
    # ]
```

---

### Enhanced Tool: `query_metric()`

**Agent asks:** "What's national ADHD prevalence for Q3 2024?"

**MCP logic:**
```python
def query_metric(dataset: str, metric: str, filters: Dict) -> Dict:
    """Query a specific metric with filters."""

    # 1. Get metadata to understand schema
    metadata = get_dataset_metadata(dataset)

    # 2. Find the measure column
    measure_col = find_column(metadata, is_measure=True, name=metric)
    # → 'prevalence_rate'

    # 3. Find dimension columns for filtering
    geography_col = find_column(metadata, is_dimension=True, keywords=['geography'])
    time_col = find_column(metadata, is_dimension=True, keywords=['time', 'period'])

    # 4. Generate SQL
    sql = f"""
    SELECT {measure_col} as value, {time_col} as period
    FROM staging.tbl_{dataset}
    WHERE {geography_col} = %s
      AND {time_col} = %s
    """

    # 5. Execute
    result = query(sql, filters['geography_level'], filters['time_period'])

    return result
```

**Agent gets:** `{"value": 4.2, "period": "2024-Q3", "unit": "percentage"}`

---

### Enhanced Tool: `aggregate_by()`

**Agent asks:** "Show ADHD prevalence by age group"

**MCP logic:**
```python
def aggregate_by(dataset: str, metric: str, group_by: str, filters: Dict = None) -> List[Dict]:
    """Aggregate a metric by a dimension."""

    # 1. Get metadata
    metadata = get_dataset_metadata(dataset)

    # 2. Find columns
    measure_col = find_column(metadata, is_measure=True, name=metric)
    # → 'prevalence_rate'

    dimension_col = find_column(metadata, is_dimension=True, keywords=[group_by])
    # → 'age_band'

    # 3. Build GROUP BY query
    sql = f"""
    SELECT
        {dimension_col} as dimension_value,
        AVG({measure_col}) as metric_value
    FROM staging.tbl_{dataset}
    WHERE geography_level = %s
    GROUP BY {dimension_col}
    ORDER BY {dimension_col}
    """

    # Returns:
    # [
    #   {"dimension_value": "0-17", "metric_value": 2.1},
    #   {"dimension_value": "18-64", "metric_value": 5.3},
    #   {"dimension_value": "65+", "metric_value": 1.8}
    # ]
```

---

## Implementation Plan

### Step 1: Populate Metadata JSONB (Script)

**File:** `scripts/populate_dataset_metadata.py`

```python
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
                "aggregation": infer_aggregation(m['data_type'])
            }
            for m in measures
        ],
        "dimensions": [
            {
                "column": d['column_name'],
                "type": infer_dimension_type(d['query_keywords'])
            }
            for d in dimensions
        ],
        "granularity": infer_granularity(dimensions),
        "record_type": infer_record_type(source_code)
    }

    # Update tbl_canonical_sources
    update("""
        UPDATE datawarp.tbl_canonical_sources
        SET metadata = %s::jsonb
        WHERE canonical_code = %s
    """, json.dumps(metadata), source_code)
```

**Run once:** `python scripts/populate_dataset_metadata.py --all`

**Time:** ~1 hour to populate 181 datasets

---

### Step 2: Update MCP Server Tools

**File:** `mcp_server/stdio_server.py`

Add new tools:
1. `get_kpis(dataset)` - List available KPIs
2. `query_metric(dataset, metric, filters)` - Query specific KPI with filters
3. `aggregate_by(dataset, metric, dimension)` - Group by dimension
4. `discover_by_keyword(keywords)` - Find datasets by semantic search

**Changes:**
- Read `tbl_column_metadata` to understand schema
- Use `is_measure` / `is_dimension` flags to generate queries
- Leverage `metadata` JSONB for richer context

**Time:** ~4 hours to implement

---

### Step 3: Test with Real Queries

**Test cases:**

```python
# 1. Discovery
result = mcp.discover_by_keyword(['adhd', 'prevalence'])
# → Returns: adhd_prevalence_estimate, adhd_indicators, ...

# 2. Get KPIs
kpis = mcp.get_kpis('adhd_prevalence_estimate')
# → [{'column': 'prevalence_rate', 'label': 'ADHD Prevalence Rate', ...}]

# 3. Query specific metric
value = mcp.query_metric(
    dataset='adhd_prevalence_estimate',
    metric='prevalence_rate',
    filters={'geography_level': 'national', 'time_period': '2024-Q3'}
)
# → {'value': 4.2, 'unit': 'percentage'}

# 4. Aggregate
breakdown = mcp.aggregate_by(
    dataset='adhd_prevalence_estimate',
    metric='prevalence_rate',
    group_by='age_band',
    filters={'geography_level': 'icb', 'geography_code': 'E54000033'}
)
# → [{'age_band': '0-17', 'value': 2.1}, ...]
```

---

## Benefits

### No New Tables
- ✅ Use existing staging tables
- ✅ Use existing metadata tables
- ✅ Just add intelligence to MCP layer

### Scales to 1000s of Datasets
- ✅ Metadata-driven (no manual config per dataset)
- ✅ Auto-populated from enrichment
- ✅ Works for any schema

### Agent-Friendly
- ✅ Discover datasets by keywords
- ✅ List available KPIs per dataset
- ✅ Query metrics without knowing schema
- ✅ Aggregate by any dimension

### Low Effort
- ✅ ~1 hour script to populate metadata JSONB
- ✅ ~4 hours to enhance MCP tools
- ✅ ~1 hour testing
- ✅ **Total: ~6 hours work**

---

## Open Questions

1. **Unit inference:** Can we auto-detect units from description text? ("percentage", "count", "rate per 100k")
2. **Aggregation method:** How do we know if a measure is SUM, AVG, or WEIGHTED_AVG? Store in metadata?
3. **Related datasets:** Auto-detect or manually configure? (e.g., adhd_prevalence ↔ adhd_medications)
4. **Caching:** Should MCP cache metadata queries for performance?

---

**Next Step:** Implement `populate_dataset_metadata.py` script?

