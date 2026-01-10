# DataWarp Dataset Catalog

**Generated:** 2026-01-10
**Total Datasets:** 65
**Total Rows:** 107,466
**Total Size:** 2.78 MB

---

## Overview

This directory contains **agent-ready NHS data** exported from DataWarp v2.1. Each dataset is:

- **Self-describing:** Parquet file + companion .md file with metadata
- **Queryable:** DuckDB-compatible, lazy-loadable
- **Lineage-tracked:** Every row includes `_load_id`, `_period`, `_loaded_at`
- **Validated:** All datasets passed quality checks (3+ columns, no empty files)

---

## Catalog Structure

### catalog.parquet
**Main discovery index** - Query this file to find datasets by domain, keyword, date range.

**Schema:**
```
source_code: string         # Unique identifier
domain: string              # ADHD, Waiting Times, PCN Workforce, etc.
description: string         # What this dataset contains
row_count: int64           # Number of rows
column_count: int64        # Number of columns
file_size_kb: float64      # Size in KB
min_date: string           # Earliest date in dataset (YYYY-MM-DD)
max_date: string           # Latest date in dataset (YYYY-MM-DD)
file_path: string          # Path to .parquet file
md_path: string            # Path to .md file
```

**Example Query (DuckDB):**
```sql
-- Find all ADHD datasets
SELECT source_code, description, row_count
FROM 'catalog.parquet'
WHERE domain = 'ADHD'
ORDER BY row_count DESC;

-- Find datasets covering November 2025
SELECT source_code, domain, min_date, max_date
FROM 'catalog.parquet'
WHERE max_date >= '2025-11-01'
  AND min_date <= '2025-11-30';
```

### catalog.csv
Same data as catalog.parquet, CSV format for spreadsheet viewing.

---

## Datasets by Domain

### ADHD (42 datasets)
- Prevalence estimates (recorded + estimated)
- Waiting lists (by age, gender, ethnicity)
- Referrals (new, closed, duration)
- Medication prescribing
- Diagnosis-to-medication time
- Community paediatrics waiting lists

### Waiting Times (11 datasets)
- Assessment waiting times by demographic
- Duration breakdowns
- Contact status (first contact, no contact)
- Closed referrals

### PCN Workforce (11 datasets)
- Staff counts by role and network
- FTE (Full-Time Equivalent) tracking
- Workforce bulletins

### OpenSAFELY (1 dataset)
- ADHD medication analysis (with/without diagnosis)
- Diagnosis-to-medication time analysis

---

## Usage Examples

### Agent Querying (Future MCP)

**User:** "Which ICBs have increasing ADHD waiting times?"

**Agent workflow:**
1. Search catalog for "ADHD waiting times" datasets
2. Load relevant Parquet files via DuckDB
3. Query across periods to find trends
4. Return results with confidence scores

### Direct Querying (DuckDB CLI)

```bash
# Install DuckDB
brew install duckdb  # or: pip install duckdb

# Launch DuckDB
duckdb

# Discover datasets
SELECT * FROM 'output/catalog.parquet' WHERE domain = 'ADHD';

# Query actual data
SELECT * FROM 'output/adhd_summary_waiting_assessment_age.parquet' LIMIT 10;

# Cross-period analysis
SELECT
  _period,
  SUM(age_0_to_4) as total_young_children
FROM 'output/adhd_summary_open_referrals_age.parquet'
GROUP BY _period
ORDER BY _period;
```

### Python Analysis

```python
import pandas as pd
import duckdb

# Load catalog
catalog = pd.read_parquet('output/catalog.parquet')

# Find ADHD datasets
adhd_datasets = catalog[catalog['domain'] == 'ADHD']
print(f"Found {len(adhd_datasets)} ADHD datasets")

# Load specific dataset
df = pd.read_parquet('output/adhd_summary_open_referrals_age.parquet')
print(df.describe())

# Or use DuckDB for larger datasets (lazy loading)
conn = duckdb.connect()
result = conn.execute("""
    SELECT _period, SUM(total_count) as total_waiting
    FROM 'output/adhd_summary_open_referrals_age.parquet'
    GROUP BY _period
    ORDER BY _period
""").df()
print(result)
```

---

## Dataset Naming Convention

**Pattern:** `{domain}_{concept}_{breakdown}.parquet`

**Examples:**
- `adhd_summary_waiting_assessment_age.parquet` → ADHD waiting assessments by age
- `pcn_workforce_bulletin_table_1a.parquet` → PCN workforce bulletin Table 1a
- `waiting_list_assessment_ethnicity.parquet` → Waiting list assessments by ethnicity

**Companion .md files:** Same name with `.md` extension
- Contains: purpose, coverage, column descriptions, search terms, validation rules

---

## Metadata Quality

Each dataset's companion .md file includes:

1. **Purpose:** What the dataset contains
2. **Coverage:** Date range, geographic scope, row count
3. **Columns:**
   - **Dimensions** (grouping columns): age, gender, ethnicity, ICB, etc.
   - **Measures** (numeric metrics): counts, rates, durations, etc.
   - **System columns:** `_load_id`, `_period`, `_loaded_at`, `_manifest_file_id`
4. **Search Terms:** Query keywords for agent discovery
5. **Validation Rules:** Data quality constraints (e.g., "counts must be non-negative")

**Metadata sources:**
- **LLM-generated:** Column descriptions, search terms (confidence: 0.70)
- **Profiled:** Min/max values, null rates (confidence: 0.95)
- **Manual:** User-provided corrections (confidence: 1.00)

---

## Data Quality

All datasets have been validated:
- ✅ No empty files (0 rows)
- ✅ All have 3+ columns
- ✅ All have companion .md files
- ✅ All have lineage tracking (`_load_id`, `_period`, `_loaded_at`)
- ✅ Parquet format (compressed, column-oriented, DuckDB-compatible)

---

## Next Steps

### For Users
1. **Browse catalog.csv** in spreadsheet to find datasets
2. **Read .md files** to understand dataset structure
3. **Query .parquet files** using DuckDB, pandas, or polars

### For Agents (via MCP - Future)
1. **Semantic search** on catalog.parquet (search terms, descriptions)
2. **Load relevant datasets** via DuckDB (lazy loading for efficiency)
3. **Query across periods** using `_period` column
4. **Verify results** using metadata validation rules
5. **Track lineage** using `_load_id` for audit

---

## Technical Notes

**File Format:** Apache Parquet (v2)
- Compression: Snappy
- Row groups: Auto
- Compatible with: DuckDB, pandas, polars, Spark, Trino

**System Columns** (present in all datasets):
- `_load_id`: References `datawarp.tbl_load_history.id`
- `_period`: Format "YYYY-MM" (e.g., "2025-11")
- `_loaded_at`: Timestamp when row was loaded
- `_manifest_file_id`: References `datawarp.tbl_manifest_files.id` (if from batch load)

**Cross-Period Queries:**
All datasets with the same `source_code` prefix can be queried together across periods using the `_period` column.

Example:
```sql
-- Compare Nov vs Aug 2025
SELECT
  _period,
  AVG(total_count) as avg_waiting
FROM 'adhd_summary_open_referrals_age.parquet'
WHERE _period IN ('2025-08', '2025-11')
GROUP BY _period;
```

---

## Support

**Documentation:**
- System architecture: `docs/architecture/system_overview_20260110.md`
- Cross-period solution: `docs/architecture/cross_period_solution_20260110.md`

**Questions?**
- Check dataset's companion .md file
- Query catalog.parquet for discovery
- Read CLAUDE.md for project context

---

**Last Updated:** 2026-01-10
**DataWarp Version:** v2.1 (Production)
