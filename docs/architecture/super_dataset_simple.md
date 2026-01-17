# Super Dataset - Simple Universal Schema

**Created:** 2026-01-17 19:05 UTC
**Purpose:** ONE table, ALL metrics, agent-ready

---

## The Design (Dead Simple)

### ONE Table for Everything

```sql
CREATE TABLE semantic.metrics (
    -- What is being measured
    dataset_code VARCHAR(100),           -- 'adhd_prevalence_estimate'
    measure_code VARCHAR(100),           -- 'prevalence_rate'
    measure_name VARCHAR(200),           -- 'ADHD Prevalence Rate'

    -- Dimensions (flexible)
    geography_level VARCHAR(50),         -- 'national', 'icb', 'provider', NULL
    geography_code VARCHAR(20),          -- 'E92000001', 'E54000033', NULL
    geography_name VARCHAR(200),         -- 'England', 'NHS Norfolk ICB', NULL
    age_band VARCHAR(50),                -- '0-17', '18-64', '65+', NULL
    gender VARCHAR(20),                  -- 'Male', 'Female', 'All', NULL
    category VARCHAR(100),               -- Flexible dimension (varies by dataset)

    -- Time
    time_period VARCHAR(20),             -- '2024-Q3', '2024-08', '2024'

    -- Value
    value NUMERIC,                       -- The actual metric value
    unit VARCHAR(50),                    -- 'percentage', 'count', 'rate_per_100k'

    -- Metadata
    data_quality VARCHAR(20),            -- 'good', 'suppressed', 'estimated'
    suppression_reason VARCHAR(200),     -- '* = value <5' or NULL

    -- Provenance
    source_table VARCHAR(100),           -- 'staging.tbl_adhd_prevalence_estimate'
    loaded_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for fast agent queries
CREATE INDEX idx_metrics_dataset ON semantic.metrics(dataset_code);
CREATE INDEX idx_metrics_measure ON semantic.metrics(measure_code);
CREATE INDEX idx_metrics_geography ON semantic.metrics(geography_level, geography_code);
CREATE INDEX idx_metrics_time ON semantic.metrics(time_period);
CREATE INDEX idx_metrics_composite ON semantic.metrics(dataset_code, measure_code, geography_level, time_period);
```

---

## Example Data

### ADHD Prevalence (National Level)
```
dataset_code | measure_code          | geography_level | geography_code | time_period | value | unit
-------------|----------------------|-----------------|----------------|-------------|-------|-----
adhd         | prevalence_rate      | national        | E92000001      | 2024-Q3     | 4.2   | percentage
adhd         | prevalence_rate      | national        | E92000001      | 2024-Q2     | 4.1   | percentage
adhd         | diagnosis_rate       | national        | E92000001      | 2024-Q3     | 85.3  | percentage
adhd         | medication_rate      | national        | E92000001      | 2024-Q3     | 72.1  | percentage
```

### ADHD Prevalence (ICB Level, with Age Breakdown)
```
dataset_code | measure_code     | geography_level | geography_code | age_band | time_period | value | unit
-------------|------------------|-----------------|----------------|----------|-------------|-------|-----
adhd         | prevalence_rate  | icb             | E54000033      | 0-17     | 2024-Q3     | 2.1   | percentage
adhd         | prevalence_rate  | icb             | E54000033      | 18-64    | 2024-Q3     | 5.3   | percentage
adhd         | prevalence_rate  | icb             | E54000033      | 65+      | 2024-Q3     | 1.8   | percentage
```

### PCN Workforce (Provider Level)
```
dataset_code | measure_code     | geography_level | geography_code | category      | time_period | value | unit
-------------|------------------|-----------------|----------------|---------------|-------------|-------|-----
pcn_wf       | fte_total        | provider        | X26            | GP            | 2024-08     | 12.5  | count
pcn_wf       | fte_total        | provider        | X26            | Nurse         | 2024-08     | 8.3   | count
pcn_wf       | fte_total        | provider        | X26            | Admin         | 2024-08     | 3.2   | count
```

---

## How Agents Query This

### Simple Queries

**Q: "What's national ADHD prevalence?"**
```sql
SELECT value, unit, time_period
FROM semantic.metrics
WHERE measure_code = 'prevalence_rate'
  AND dataset_code = 'adhd'
  AND geography_level = 'national'
ORDER BY time_period DESC
LIMIT 1;
```

**Q: "Show me ADHD prevalence by age group for Norfolk ICB"**
```sql
SELECT age_band, value
FROM semantic.metrics
WHERE measure_code = 'prevalence_rate'
  AND dataset_code = 'adhd'
  AND geography_code = 'E54000033'
  AND time_period = (SELECT MAX(time_period) FROM semantic.metrics)
ORDER BY age_band;
```

**Q: "Compare Q2 vs Q3 ADHD medication rates nationally"**
```sql
SELECT
    time_period,
    value as medication_rate
FROM semantic.metrics
WHERE measure_code = 'medication_rate'
  AND dataset_code = 'adhd'
  AND geography_level = 'national'
  AND time_period IN ('2024-Q2', '2024-Q3')
ORDER BY time_period;
```

### Cross-Dataset Queries

**Q: "Compare ADHD prevalence vs workforce levels by ICB"**
```sql
SELECT
    m1.geography_code,
    m1.geography_name,
    MAX(CASE WHEN m1.measure_code = 'prevalence_rate' THEN m1.value END) as adhd_prevalence,
    MAX(CASE WHEN m2.measure_code = 'fte_total' THEN m2.value END) as gp_fte
FROM semantic.metrics m1
LEFT JOIN semantic.metrics m2
    ON m1.geography_code = m2.geography_code
    AND m2.dataset_code = 'pcn_wf'
    AND m2.category = 'GP'
WHERE m1.dataset_code = 'adhd'
  AND m1.measure_code = 'prevalence_rate'
  AND m1.geography_level = 'icb'
  AND m1.time_period = '2024-Q3'
GROUP BY m1.geography_code, m1.geography_name;
```

---

## Transformation Logic (Staging → Semantic)

### Script: `scripts/build_semantic_metrics.py`

For each staging table:

1. **Read metadata:**
   ```python
   # Get column roles from metadata
   measures = get_columns(source_code, is_measure=True)
   dimensions = get_columns(source_code, is_dimension=True)
   ```

2. **Identify dimensions:**
   ```python
   geography_col = find_column(dimensions, keywords=['geography', 'location', 'org'])
   time_col = find_column(dimensions, keywords=['period', 'date', 'month', 'quarter'])
   age_col = find_column(dimensions, keywords=['age', 'age_band'])
   category_col = [other dimension columns]
   ```

3. **Unpivot if needed:**
   ```python
   if is_wide_format(staging_table):
       # Wide format (50 month columns) → Long format
       df = unpivot(df, static_cols=dimensions, value_cols=measures)
   ```

4. **Map to semantic schema:**
   ```python
   semantic_rows = []
   for measure_col in measures:
       for _, row in df.iterrows():
           semantic_rows.append({
               'dataset_code': source_code,
               'measure_code': measure_col,
               'measure_name': metadata[measure_col]['description'],
               'geography_level': detect_geography_level(row[geography_col]),
               'geography_code': row[geography_col],
               'age_band': row.get(age_col),
               'time_period': row[time_col],
               'value': row[measure_col],
               'unit': metadata[measure_col]['unit'],
               'source_table': f'staging.{table_name}'
           })
   ```

5. **Insert to semantic.metrics:**
   ```python
   df_semantic = pd.DataFrame(semantic_rows)
   df_semantic.to_sql('metrics', conn, schema='semantic', if_exists='append')
   ```

---

## Automation Strategy

### Daily Refresh (After Backfill)

1. **Backfill runs** → New data loaded to staging tables
2. **Trigger** → `build_semantic_metrics.py`
3. **Process** → Only new/updated staging tables (check last_load_at)
4. **Insert** → Append new rows to semantic.metrics
5. **Agents** → Query updated semantic layer

### Incremental Processing

```python
# Only process staging tables that changed today
sql = """
SELECT code, table_name
FROM datawarp.tbl_data_sources
WHERE last_load_at::date = CURRENT_DATE
"""

for source_code, table_name in cursor.execute(sql):
    # Transform and load to semantic.metrics
    transform_to_semantic(source_code, table_name)
```

---

## Benefits

### For Agents
- **ONE table to query** (not 181 staging tables)
- **Consistent schema** (always measure_code, geography_level, time_period, value)
- **Cross-dataset joins** (compare ADHD vs workforce by geography)
- **Simple filters** (WHERE measure_code = 'prevalence_rate')

### For Users
- **No schema knowledge needed** (standardized column names)
- **Fast queries** (indexed on measure, geography, time)
- **Historical trends** (all time periods in one table)
- **Multi-dimensional** (filter by geography + age + time)

### For System
- **Scales to 1000s of datasets** (same schema for all)
- **Automated transformation** (driven by tbl_column_metadata)
- **No manual mapping** (metadata tells us what's a measure/dimension)
- **Incremental refresh** (only process changed tables)

---

## Open Questions for User

1. **Nullable dimensions:** If a dataset has no age_band, is NULL OK? Or skip those rows?
2. **Category column:** Some datasets have extra dimensions (staff_type, diagnosis_type). Use generic "category" column?
3. **Multiple measures per row:** If staging table has 5 measure columns, create 5 semantic rows (unpivot measures too)?
4. **Geography detection:** Auto-detect national/icb/provider from code patterns OR require metadata?
5. **Refresh strategy:** Truncate+reload daily OR incremental append-only?

---

**Next Step:** Get your feedback, then I'll implement `build_semantic_metrics.py`

