# Semantic Model Design - Metadata-Driven Agent Querying

**Created:** 2026-01-17 18:45 UTC
**Updated:** 2026-01-17 19:00 UTC (Pivoted to metadata-driven approach)
**Purpose:** Enable agents to query 1000s of datasets without schema knowledge

---

## The Problem We're Solving

**Current State:**
```
staging.tbl_adhd_prevalence_estimate        (15 columns, raw NHS schema)
staging.tbl_adhd_indicators                 (12 columns, different schema)
staging.tbl_adhd_meds_prescribed_prev_6m    (18 columns, another schema)
...181 staging tables (1000s planned)...
```

**Agent Question:** "What's the national ADHD prevalence rate?"

**Problem:** Agent has to:
1. Discover which table has prevalence data (search 181 tables)
2. Understand the schema of that table (15 columns with NHS naming)
3. Filter for national-level geography (which column is that?)
4. Find the right measure column (prevalence_rate? count? percentage?)
5. Aggregate if needed

**Takes:** 3-5 MCP calls, agent needs deep schema knowledge

---

## The Solution: Metadata-Driven Semantic Layer

**Key Insight:** We already have semantic metadata in `tbl_column_metadata`!

Each column has:
- `is_dimension` - Is this a grouping column? (geography, time, category)
- `is_measure` - Is this a numeric metric? (prevalence_rate, count, percentage)
- `query_keywords` - Searchable terms (["prevalence", "ADHD", "diagnosis rate"])

**Solution:** Use this metadata to **generate queries dynamically**

**Agent Question:** "What's the national ADHD prevalence rate?"

**MCP Server:**
1. Search `query_keywords` for "prevalence" + "ADHD" → finds `adhd_prevalence_estimate`
2. Query `tbl_column_metadata` for columns where `is_measure=true` → finds `prevalence_rate`
3. Query for columns where `is_dimension=true` and name contains "geography" → finds `geography_level`
4. Generate SQL: `SELECT prevalence_rate FROM staging.tbl_adhd_prevalence_estimate WHERE geography_level = 'national'`
5. Return result

**Takes:** 1 MCP call, agent just asks the question in natural language

---

## Semantic Model Architecture

### Layer Structure (Metadata-Driven)

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: AGENT INTERFACE (MCP Server with Semantic Tools)   │
│   • discover_datasets(keywords) → uses query_keywords       │
│   • query_metric(measure, filters) → uses is_measure flags  │
│   • aggregate_by(dimension) → uses is_dimension flags        │
│   • compare_periods(measure) → auto-detects time columns    │
└─────────────────────────────────────────────────────────────┘
                            ↑
                    [Metadata-Driven Query Generation]
                            ↑
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: SEMANTIC METADATA (The Intelligence)               │
│   • tbl_column_metadata (is_dimension, is_measure, keywords)│
│   • tbl_canonical_sources (domain, description, metadata)   │
│   → MCP reads metadata, generates SQL dynamically           │
└─────────────────────────────────────────────────────────────┘
                            ↑
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: STAGING TABLES (Raw ingestion)                     │
│   • staging.tbl_* (181 tables, raw NHS data)                │
│   • Heterogeneous schemas (different column names)          │
│   → Metadata tells MCP how to query them                    │
└─────────────────────────────────────────────────────────────┘
```

**Key Point:** No materialized views, no manual schema mapping. Metadata IS the semantic model.

---

## Super Dataset Design Pattern

### Pattern 1: Star Schema (Dimensional Model)

**Fact Table:** `fact_clinical_metrics`
```sql
CREATE TABLE semantic.fact_clinical_metrics (
    metric_id BIGSERIAL PRIMARY KEY,

    -- Foreign Keys to Dimensions
    measure_key INTEGER REFERENCES semantic.dim_measures(measure_key),
    geography_key INTEGER REFERENCES semantic.dim_geography(geography_key),
    time_key INTEGER REFERENCES semantic.dim_time(time_key),

    -- Measure
    value NUMERIC,

    -- Metadata
    data_quality_flag VARCHAR(20),    -- 'good', 'suppressed', 'estimated'
    suppression_reason VARCHAR(100),  -- '* = value <5', NULL
    confidence_interval_lower NUMERIC,
    confidence_interval_upper NUMERIC,

    -- Provenance
    source_publication VARCHAR(100),  -- 'adhd_aug25'
    source_table VARCHAR(100),        -- 'staging.tbl_adhd_prevalence_estimate'
    source_row_id INTEGER,
    loaded_at TIMESTAMP DEFAULT NOW()
);
```

**Dimension: Measures**
```sql
CREATE TABLE semantic.dim_measures (
    measure_key SERIAL PRIMARY KEY,
    measure_code VARCHAR(100) UNIQUE,  -- 'adhd_prevalence_rate'
    measure_name VARCHAR(200),         -- 'ADHD Prevalence Rate'

    -- Classification
    domain VARCHAR(50),                -- 'mental_health'
    category VARCHAR(50),              -- 'prevalence'

    -- Metadata
    definition TEXT,                   -- 'Number of patients with ADHD diagnosis...'
    unit VARCHAR(50),                  -- 'percentage', 'count', 'rate per 100k'
    aggregation_method VARCHAR(50),    -- 'sum', 'average', 'weighted_average'
    is_additive BOOLEAN,               -- Can you SUM across geographies?

    -- Validation
    expected_min_value NUMERIC,
    expected_max_value NUMERIC,

    -- Keywords for agent discovery
    query_keywords TEXT[]              -- {'prevalence', 'ADHD', 'diagnosis rate'}
);
```

**Dimension: Geography**
```sql
CREATE TABLE semantic.dim_geography (
    geography_key SERIAL PRIMARY KEY,
    geography_code VARCHAR(20),        -- 'E54000033' (ICB code)
    geography_name VARCHAR(200),       -- 'NHS Norfolk and Waveney ICB'

    -- Hierarchy
    geography_level VARCHAR(20),       -- 'national', 'region', 'icb', 'subicb', 'provider'
    parent_geography_key INTEGER REFERENCES semantic.dim_geography(geography_key),

    -- Codes
    ods_code VARCHAR(20),
    onspd_code VARCHAR(20),

    -- Metadata
    region VARCHAR(100),               -- 'East of England'
    population INTEGER,
    active_from DATE,
    active_to DATE
);
```

**Dimension: Time**
```sql
CREATE TABLE semantic.dim_time (
    time_key SERIAL PRIMARY KEY,
    time_period VARCHAR(20) UNIQUE,    -- '2024-Q3', '2024-08', '2024-W32'

    -- Breakdowns
    year INTEGER,                      -- 2024
    quarter INTEGER,                   -- 3
    month INTEGER,                     -- 8
    fiscal_year VARCHAR(10),           -- '2024/25'
    fiscal_quarter INTEGER,            -- 2

    -- Ranges
    period_start_date DATE,
    period_end_date DATE,

    -- Metadata
    period_type VARCHAR(20)            -- 'quarter', 'month', 'week'
);
```

---

### Pattern 2: Super Dataset Views (Simplified)

For each domain, create a materialized view that UNIONS all related sources into one semantic table:

**Example: mental_health_metrics**
```sql
CREATE MATERIALIZED VIEW semantic.mental_health_metrics AS

-- ADHD Prevalence
SELECT
    'adhd_prevalence_rate' AS measure,
    'percentage' AS unit,
    geography_level,
    geography_code,
    geography_name,
    time_period,
    prevalence_rate AS value,
    'adhd_prevalence_estimate' AS source_publication,
    data_quality_flag,
    suppression_reason
FROM staging.tbl_adhd_prevalence_estimate

UNION ALL

-- ADHD Diagnosis Rate
SELECT
    'adhd_diagnosis_rate' AS measure,
    'rate_per_100k' AS unit,
    geography_level,
    geography_code,
    geography_name,
    time_period,
    diagnosis_rate AS value,
    'adhd_indicators' AS source_publication,
    data_quality_flag,
    suppression_reason
FROM staging.tbl_adhd_indicators

UNION ALL

-- ADHD Medication Rate
SELECT
    'adhd_medication_rate' AS measure,
    'percentage' AS unit,
    geography_level,
    geography_code,
    geography_name,
    time_period,
    medication_rate AS value,
    'adhd_meds_prescribed_prev_6m' AS source_publication,
    data_quality_flag,
    suppression_reason
FROM staging.tbl_adhd_meds_prescribed_prev_6m;

-- Indexes for fast agent queries
CREATE INDEX idx_mh_metrics_measure ON semantic.mental_health_metrics(measure);
CREATE INDEX idx_mh_metrics_geography ON semantic.mental_health_metrics(geography_level, geography_code);
CREATE INDEX idx_mh_metrics_time ON semantic.mental_health_metrics(time_period);
```

**Agent Query (Simple):**
```sql
-- "What's the national ADHD prevalence rate?"
SELECT value
FROM semantic.mental_health_metrics
WHERE measure = 'adhd_prevalence_rate'
  AND geography_level = 'national'
ORDER BY time_period DESC
LIMIT 1;
```

**Agent Query (Comparison):**
```sql
-- "Compare ADHD prevalence vs medication rate at ICB level"
SELECT
    geography_name,
    MAX(CASE WHEN measure = 'adhd_prevalence_rate' THEN value END) as prevalence,
    MAX(CASE WHEN measure = 'adhd_medication_rate' THEN value END) as medication_rate
FROM semantic.mental_health_metrics
WHERE geography_level = 'icb'
  AND time_period = '2024-Q3'
GROUP BY geography_name
ORDER BY prevalence DESC;
```

---

## Super Dataset Registry

Each domain gets a super dataset combining related publications:

| Super Dataset | Domain | Sources Combined | Measures | Geographies | Time Periods |
|---------------|--------|------------------|----------|-------------|--------------|
| `mental_health_metrics` | Mental Health | 42 ADHD tables | 15 measures | National → Provider | 2023-Q1 → Current |
| `workforce_metrics` | Workforce | 17 PCN tables | 8 measures | National → Practice | 2019-04 → Current |
| `primary_care_metrics` | Primary Care | 14 GP tables | 12 measures | National → Practice | 2018-01 → Current |
| `waiting_time_metrics` | Waiting Times | 11 RTT tables | 6 measures | National → Provider | 2020-Q1 → Current |
| `digital_services_metrics` | Digital | 37 OC tables | 9 measures | National → Practice | 2022-01 → Current |

---

## Implementation Strategy

### Phase 1: Define Dimension Tables (1 day)

**Script:** `scripts/build_semantic_dimensions.py`

1. Extract unique geographies from all staging tables → `dim_geography`
2. Generate time periods from data → `dim_time`
3. Define measures from `tbl_column_metadata` → `dim_measures`

**Input:**
- `datawarp.tbl_column_metadata` (has is_measure flags)
- `staging.tbl_*` (scan for geography codes, time periods)

**Output:**
- `semantic.dim_measures` (100-200 measures)
- `semantic.dim_geography` (500-1000 geographies)
- `semantic.dim_time` (100+ time periods)

---

### Phase 2: Build Fact Table (2 days)

**Script:** `scripts/build_fact_table.py`

For each staging table:
1. Identify measure columns (use `is_measure` flag)
2. Identify dimension columns (geography, time)
3. Unpivot if needed (wide → long)
4. Map to dimension keys
5. Insert into `fact_clinical_metrics`

**Challenge:** Standardizing heterogeneous schemas
**Solution:** Use `tbl_column_metadata.query_keywords` to match columns to standard measures

---

### Phase 3: Create Super Dataset Views (1 day)

**Script:** `scripts/create_super_datasets.py`

For each domain:
1. Identify staging tables in domain (use `domain` classification)
2. Generate UNION ALL query
3. Standardize column names (measure, geography_level, time_period, value)
4. Create materialized view
5. Add indexes

**Output:** 8-10 super dataset views

---

### Phase 4: Update MCP Server (1 day)

**Changes to:** `mcp_server/stdio_server.py`

1. Add new tools:
   - `list_super_datasets()` - List available super datasets
   - `query_metrics()` - Simplified metric queries
   - `compare_periods()` - Time series comparisons
   - `aggregate_by_geography()` - Roll up/drill down

2. Default to semantic layer instead of staging:
   - `list_datasets()` → show super datasets first
   - `query()` → route to semantic views when possible

---

## Metric Definition Framework

Each measure needs a canonical definition:

**Example: ADHD Prevalence Rate**
```yaml
measure_code: adhd_prevalence_rate
measure_name: ADHD Prevalence Rate
definition: |
  Percentage of registered patients with ADHD diagnosis code in clinical
  record, based on GP practice data submissions.

unit: percentage
aggregation_method: weighted_average  # By population
is_additive: false  # Can't sum percentages across geographies

validation:
  expected_min: 0.0
  expected_max: 15.0  # Prevalence >15% would be suspicious
  null_rate_threshold: 0.05  # <5% nulls expected

source_publications:
  - adhd_prevalence_estimate
  - adhd_indicators

related_measures:
  - adhd_diagnosis_rate
  - adhd_medication_rate

keywords:
  - prevalence
  - ADHD
  - attention deficit
  - diagnosis rate
  - registered patients
```

**Storage:** Either YAML files or `dim_measures` table

---

## Benefits for Agents

### Before (Staging Layer)
```
Agent: "What's national ADHD prevalence?"

Steps:
1. list_datasets(domain="ADHD") → 42 tables returned
2. Pick adhd_prevalence_estimate
3. get_metadata(adhd_prevalence_estimate) → 15 columns
4. Figure out which column is prevalence
5. Figure out which geography level is national
6. query() with complex WHERE clause

Time: 3-5 MCP calls, agent has to understand schema
```

### After (Semantic Layer)
```
Agent: "What's national ADHD prevalence?"

Steps:
1. query_metrics(
     measure="adhd_prevalence_rate",
     geography_level="national"
   )

Time: 1 MCP call, agent just needs to know measure name
```

---

## Governance & Maintenance

### Metric Ownership
- Each measure has a canonical definition
- Domain experts validate definitions
- Changes require version control

### Refresh Strategy
- Materialized views refresh daily (after backfill runs)
- Incremental refresh (only new periods)
- Agent queries hit cached views (fast)

### Quality Checks
- Expected value ranges checked during insert
- Null rates monitored
- Anomaly detection (sudden spikes/drops)

---

## Next Steps

1. **User Decision:** Star schema (fact/dim tables) OR simplified views?
2. **Measure Catalog:** Define first 20-30 key measures across domains
3. **Dimension Extraction:** Build dim_geography, dim_time, dim_measures
4. **Pilot Super Dataset:** Start with `mental_health_metrics` (42 ADHD sources)
5. **Agent Testing:** Validate queries simplified and faster

---

## Open Questions

1. **Granularity:** Do we need row-level fact table OR just aggregated views?
2. **Historical Data:** How far back do we materialize? (All periods or recent only?)
3. **Schema Mapping:** Manual YAML configs OR automated from `tbl_column_metadata`?
4. **Refresh Timing:** Daily materialized view refresh OR real-time staging queries?
5. **Geography Hierarchy:** Do we need drill-down paths (National → Region → ICB → Provider)?

---

**Status:** Proposal stage - awaiting user feedback on approach

