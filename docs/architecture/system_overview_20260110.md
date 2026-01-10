# DataWarp v2.1: Comprehensive Architecture & Data Flow Report

**Generated:** 2026-01-10 (Current as of this date - code moves fast, treat older docs with caution)

---

## Executive Summary

DataWarp v2.1 is a **deterministic NHS data ingestion engine** that transforms complex NHS Excel/CSV publications into agent-ready, queryable data. The system is in **production state** with a clear vision: **NHS Excel → PostgreSQL (staging + metadata) → Parquet + .md → MCP → Natural Language Querying**.

**Current Status:** Track A Day 3 - Metadata foundation proven, extraction stable (87-92% success), cross-period consolidation working with 42 validated sources.

---

## 1. CORE ARCHITECTURE & DATA FLOW

### Complete Pipeline (URL → Agent-Ready Data)

```
┌─────────────────────────────────────────────────────────────┐
│  NHS Publication URL                                         │
│  https://digital.nhs.uk/.../mi-adhd/november-2025          │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────────┐
│ PHASE 1: MANIFEST GENERATION (url_to_manifest.py)          │
│ - Scrapes NHS page, downloads files                        │
│ - Auto-detects sheets in Excel/ZIP/CSV                     │
│ - Generates raw.yaml with generic codes                    │
│ Output: adhd_nov25_raw.yaml                                │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────────┐
│ PHASE 2: LLM ENRICHMENT (enrich_manifest.py) [OPTIONAL]    │
│ Provider: Gemini (30-40s) OR Qwen (3-5min)                │
│ - Generates semantic codes (removes dates!)                │
│ - Column-level metadata (descriptions, types, keywords)    │
│ - Consolidates sources (30 → 20 sources)                   │
│ Output: adhd_nov25_enriched.yaml + llm_response.json       │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────────┐
│ PHASE 3: CANONICALIZATION (apply_enrichment.py)            │
│ - Merges LLM codes into YAML                               │
│ - Preserves original codes for audit                       │
│ Output: adhd_nov25_canonical.yaml                          │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────────┐
│ PHASE 4: EXTRACTION & LOADING (datawarp load-batch)        │
│                                                             │
│ FOR EACH SOURCE IN MANIFEST:                               │
│   1. Download → pipeline.py calls download_file()          │
│   2. Route by extension:                                   │
│      .xlsx → FileExtractor (871 lines, ~50ms)             │
│      .csv → CSVExtractor (25x faster than v1)              │
│   3. Structure Detection:                                  │
│      - Multi-tier headers (Year → Month → Metric)         │
│      - Merged cells handling                               │
│      - Footer detection (Note:, Source:, *)               │
│      - Type inference (VARCHAR, INTEGER, NUMERIC)          │
│   4. Column Mapping:                                       │
│      - Apply semantic names from enrichment                │
│      - Deterministic fallback (schema.py)                  │
│   5. Unpivot Transform (if wide date pattern):            │
│      - Wide: [Org, Oct25, Nov25] → Long: [Org, period, value] │
│   6. Schema Evolution:                                     │
│      - CREATE TABLE (if new)                               │
│      - ALTER TABLE ADD COLUMN (if drift)                   │
│   7. Data Load:                                            │
│      - Batch INSERT (1000 rows/batch)                      │
│      - Audit columns: _load_id, _period, _loaded_at        │
│   8. Metadata Capture:                                     │
│      - Store column semantics in tbl_column_metadata       │
│                                                             │
│ Output: PostgreSQL staging.tbl_* tables with lineage       │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────────┐
│ PHASE 5: PARQUET EXPORT (export_to_parquet.py)             │
│ - Export entire table (all periods) → single .parquet      │
│ - Generate companion .md file with:                        │
│   * Dataset purpose, date range, scope                     │
│   * Column descriptions grouped by type                    │
│   * System columns documented                              │
│   * Fuzzy matching ensures accuracy                        │
│ - Deterministic ordering (chronological)                   │
│ Output: clinical/adhd/prescribing_by_icb.parquet + .md     │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────────┐
│ FUTURE: MCP SERVER + AGENT QUERYING                        │
│ - catalog.parquet for discovery (semantic search)          │
│ - MCP tools: discover, query, explain, verify              │
│ - Claude Code connects via MCP protocol                    │
│ - Natural language → SQL → Results                         │
└─────────────────────────────────────────────────────────────┘
```

### Key Orchestration Points

**1. pipeline.py (248 lines) - THE ORCHESTRATOR**
- Entry point for all loads
- Handles file routing (.xlsx vs .csv)
- Manages schema evolution
- Coordinates extraction → drift detection → DDL → insert
- Returns `LoadResult` with success/error details

**2. batch.py (300+ lines) - MANIFEST PROCESSOR**
- Parses YAML manifests
- Iterates through sources
- Calls `pipeline.load_file()` for each
- Handles deduplication (URL-based)
- Tracks progress in `tbl_manifest_files`
- Stores column metadata after successful loads

**3. FileExtractor (871 lines) - NHS INTELLIGENCE**
- **Core capability:** Detects complex NHS Excel patterns
- Row caching optimization (317x faster than column-major)
- Multi-tier header flattening
- Merged cell handling
- Sheet classification (TABULAR, METADATA, EMPTY)
- Type inference from keywords + data sampling

---

## 2. KEY CONCEPTS

### Source Registration & Tracking

**Registry Tables (datawarp schema):**

```sql
tbl_data_sources
  - code: Unique identifier (e.g., "adhd_summary_waiting_assessment_age")
  - table_name: PostgreSQL table (e.g., "tbl_adhd_summary_waiting_assessment_age")
  - schema_name: Usually "staging"

tbl_load_history
  - Audit trail of ALL loads
  - Tracks: file_url, rows_loaded, columns_added, load_mode

tbl_manifest_files
  - Tracks individual files from batch manifests
  - Status: pending, loaded, failed, skipped
  - Error details in JSONB format

tbl_column_metadata (NEW in Track A)
  - Stores LLM-generated column semantics
  - original_name, description, data_type, is_dimension, is_measure
  - query_keywords for agent discovery
  - Confidence scores (0.70 = LLM, 0.95 = profiled, 1.00 = manual)
```

### Manifests & Batch Loading

**Manifest Structure (YAML):**

```yaml
manifest:
  name: november_2025_20260108
  source_url: https://digital.nhs.uk/.../november-2025
  publication_context:
    page_title: ADHD Management Information - November 2025

sources:
  - code: adhd_summary_waiting_assessment_age  # Semantic, no dates!
    name: "ADHD Summary: Waiting Assessment by Age"
    description: "Number of people waiting for ADHD assessment by age group"
    table: tbl_adhd_summary_waiting_assessment_age
    enabled: true
    files:
      - url: https://files.digital.nhs.uk/.../ADHD_summary_Nov25.xlsx
        sheet: Table 2a
        mode: replace
        period: 2025-11
    columns:  # LLM-enriched metadata
      - original_name: "Date"
        semantic_name: "reporting_period"
        description: "The date for which the data is reported"
        data_type: date
        is_dimension: true
        is_measure: false
        query_keywords: [period, date, reporting]
      - original_name: "Age 0 to 4"
        semantic_name: "age_0_to_4_count"
        description: "Number of individuals aged 0 to 4"
        data_type: integer
        is_dimension: false
        is_measure: true
```

**Workflow:**
1. `url_to_manifest.py` → raw.yaml (generic codes)
2. `enrich_manifest.py` → enriched.yaml + llm_response.json (semantic codes, column metadata)
3. `apply_enrichment.py` → canonical.yaml (merged LLM codes into YAML)
4. `datawarp load-batch canonical.yaml` → PostgreSQL tables + metadata storage

### Schema Drift Detection & Evolution

**Drift Detection (drift.py - 30 lines):**
```python
def detect_drift(file_columns, db_columns):
    new = set(file_columns) - set(db_columns)      # New columns
    missing = set(db_columns) - set(file_columns)  # Missing columns
    return DriftResult(new_columns=new, missing_columns=missing)
```

**Schema Evolution Behavior (HARDCODED, no policies):**
- **New columns** → `ALTER TABLE ADD COLUMN` (always)
- **Missing columns** → `INSERT NULL` (always)
- **Type changes** → Log warning, continue (always)

**Example:**
```sql
-- August load creates table:
CREATE TABLE staging.tbl_adhd_prescribing (
    icb_name VARCHAR(255),
    total_items INTEGER
);

-- November load detects new column:
ALTER TABLE staging.tbl_adhd_prescribing
    ADD COLUMN patient_count INTEGER;

-- Data inserted with NULL for missing column in old rows
```

### Unpivot Transformation (Wide → Long)

**Problem:** NHS publications with date-as-columns cause schema drift

**Wide Format (input):**
```
| Org  | Staff_Type | Oct_2025 | Nov_2025 | Dec_2025 |  # Schema grows monthly!
| NHS  | Nurse      | 100      | 110      | 120      |
```

**Long Format (output):**
```
| Org  | Staff_Type | period     | value |  # Schema stable!
| NHS  | Nurse      | 2025-10-01 | 100   |
| NHS  | Nurse      | 2025-11-01 | 110   |
| NHS  | Nurse      | 2025-12-01 | 120   |
```

**Detection & Transform (unpivot.py - 214 lines):**
```python
# Auto-detect wide pattern (3+ date columns)
wide_date_info = detect_wide_date_pattern(headers)

if wide_date_info['is_wide']:
    df = unpivot_wide_dates(
        df,
        static_columns=['Org', 'Staff_Type'],
        date_columns=['Oct_2025', 'Nov_2025', 'Dec_2025'],
        value_name='value',
        period_name='period'
    )
```

**Benefits:**
- Schema stability (no new columns each month)
- Cross-period queries trivial (`WHERE period >= '2025-10-01'`)
- Single table for all time periods

### Enrichment Process

**Two Providers:**

**1. Gemini (External, Production)**
- Speed: 30-40 seconds per publication
- Quality: Excellent consolidation, semantic naming
- Cost: ~$0.05 per enrichment
- Model: gemini-2.0-flash-exp

**2. Qwen (Local, Privacy-Sensitive)**
- Speed: 3-5 minutes per publication
- Quality: Good with 8 generic improvements
- Cost: $0 (runs locally)
- Model: qwen2.5:32b-instruct

**LLM-Generated Metadata (stored in tbl_column_metadata):**
```yaml
columns:
  - original_name: "Women known to be smokers at time of delivery - Number"
    semantic_name: "smokers_count"
    description: "Number of women who were known to be smokers at delivery"
    data_type: "integer"
    is_dimension: false
    is_measure: true
    query_keywords: ["smoker count", "number of smokers", "total smokers"]
```

**Key Insight:** LLM is OPTIONAL. DataWarp v2.1 core is fully deterministic. LLM adds semantic richness but isn't required for loading.

---

## 3. NHS DATA EXTRACTION INTELLIGENCE

### FileExtractor Capabilities (extractor.py - 871 lines)

**1. Multi-Tier Hierarchical Headers**

NHS Excel files often have nested headers:
```
Row 1:           [blank]    |  April 2024           |  May 2024
Row 2:           [blank]    |  Patients  |  Items   |  Patients  |  Items
Row 3 (data):    Region A   |  100       |  250     |  105       |  260
```

**Detection Logic:**
- Scans for merged cells (indicates header tiers)
- Identifies header row count (max 10 rows scanned)
- Flattens to: `april_2024_patients`, `april_2024_items`, etc.
- Uses `>` separator: "April 2024 > Patients"

**2. Wide Date Pattern Detection**

Triggers when 3+ columns match date patterns:
```python
DATE_PATTERNS = [
    r'^(jan|feb|mar|...|dec)[-_\s]?\d{2,4}',  # Nov-25
    r'^\d{4}[-_](0?[1-9]|1[0-2])',            # 2025-01
    r'^(q[1-4])[-_\s]?\d{2,4}',               # Q1 2025
]
```

**Action:** Recommends unpivot transformation to prevent schema drift.

**3. Suppressed Value Handling**

NHS uses privacy suppression for values <5:
- `*` = suppressed (stored as NULL)
- `-` = not applicable (stored as NULL)
- `.` = missing data (stored as NULL)

**Type inference handles mixed content:**
```python
# Column contains: [100, 250, "*", 340, "-", 500]
# Inferred type: INTEGER (parse numbers, NULL for symbols)
```

**4. Footer Detection**

Common NHS footer patterns:
- "Note:", "Source:", "Copyright", "www."
- Empty rows followed by text
- Merged cells at bottom

**Logic:** Scans last 100 rows, stops when footer pattern found.

**5. Type Inference**

**Two-phase approach:**
1. **Keyword-based:** Column name contains "date", "code", "name", "count", etc.
2. **Data sampling:** Scan first 25 rows, check cell types

**Type mapping:**
```python
"date" in name.lower()          → DATE
"code" in name.lower()          → VARCHAR(255)
"count", "number", "total"      → INTEGER
Decimals detected in samples    → DOUBLE PRECISION
Mixed numeric + text            → VARCHAR(255)
```

**Recent enhancement (Track A Day 3):**
- Uses `cell.data_type` metadata instead of parsing values
- Scans ALL rows (not just first 25) for type consistency
- Handles mixed content (numeric + suppression symbols)

---

## 4. DATABASE SCHEMA

### Registry Tables (datawarp schema)

```sql
-- Source registry
tbl_data_sources (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) UNIQUE,      -- "adhd_summary_waiting_assessment_age"
    name VARCHAR(255),
    table_name VARCHAR(100),       -- "tbl_adhd_summary_waiting_assessment_age"
    schema_name VARCHAR(50),       -- "staging"
    default_sheet VARCHAR(100),
    created_at TIMESTAMP,
    last_load_at TIMESTAMP
)

-- Load audit trail
tbl_load_history (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES tbl_data_sources(id),
    file_url VARCHAR(500),
    rows_loaded INTEGER,
    columns_added TEXT[],           -- Array of new column names
    load_mode VARCHAR(20),          -- 'append' or 'replace'
    loaded_at TIMESTAMP
)

-- Manifest tracking
tbl_manifest_files (
    id SERIAL PRIMARY KEY,
    manifest_name VARCHAR(100),
    source_code VARCHAR(100),
    file_url VARCHAR(500),
    period VARCHAR(10),
    status VARCHAR(20),             -- pending, loaded, failed, skipped
    error_details JSONB,
    rows_loaded INTEGER,
    columns_added JSONB,
    loaded_at TIMESTAMP
)

-- Column metadata (Track A - NEW)
tbl_column_metadata (
    canonical_source_code VARCHAR(100),
    column_name VARCHAR(100),
    original_name VARCHAR(500),     -- From Excel header
    description TEXT,               -- LLM-generated
    data_type VARCHAR(50),
    is_dimension BOOLEAN,
    is_measure BOOLEAN,
    query_keywords TEXT[],          -- For semantic search
    min_value NUMERIC,              -- From profiling (optional)
    max_value NUMERIC,
    null_rate NUMERIC(5,2),
    metadata_source VARCHAR(20),    -- 'llm', 'profiled', 'manual'
    confidence NUMERIC(3,2),        -- 0.70, 0.95, 1.00
    created_at TIMESTAMP,
    PRIMARY KEY (canonical_source_code, column_name)
)
```

### Staging Table Convention (staging schema)

**Dynamically created per canonical source:**

```sql
CREATE TABLE staging.tbl_adhd_summary_waiting_assessment_age (
    -- Business columns (from NHS data, auto-detected)
    reporting_period DATE,
    age_0_to_4_count INTEGER,
    age_5_to_11_count INTEGER,
    age_12_to_17_count INTEGER,
    total_count INTEGER,

    -- DataWarp audit columns (injected automatically)
    _load_id INTEGER REFERENCES datawarp.tbl_load_history(id),
    _loaded_at TIMESTAMP DEFAULT NOW(),
    _period VARCHAR(20),              -- "2025-11"
    _manifest_file_id INTEGER REFERENCES datawarp.tbl_manifest_files(id)
);
```

**Lineage Tracking:**
- `_load_id` → Join to `tbl_load_history` → Get file_url, load timestamp
- `_period` → Identifies data reporting period
- `_manifest_file_id` → Join to `tbl_manifest_files` → Get manifest context

**Cross-Period Consolidation:**
```sql
-- August load:
INSERT INTO staging.tbl_adhd_prescribing VALUES (..., _period='2025-08');

-- November load (SAME TABLE):
INSERT INTO staging.tbl_adhd_prescribing VALUES (..., _period='2025-11');

-- Query across periods:
SELECT AVG(total_items)
FROM staging.tbl_adhd_prescribing
WHERE _period IN ('2025-08', '2025-11')
GROUP BY icb_name;
```

---

## 5. DETERMINISTIC NAMING SYSTEM

### The Problem (Why schema.py exists)

**LLM variance causes schema drift:**
```
August enrichment:   "age_0_to_4_referral_count"   # LLM choice 1
November enrichment: "age_0_to_4_count"            # LLM choice 2
```

**Result:** Both map to same Excel header "Age 0 to 4", but different semantic names → `INSERT` fails because column names don't match.

### The Solution (schema.py - 266 lines)

**Deterministic column naming function:**

```python
def to_schema_name(header: str) -> str:
    """Convert Excel header to PostgreSQL column name (ALWAYS same output)."""
    # 1. Lowercase
    clean = header.lower()

    # 2. Remove currency symbols (£$€%)
    clean = re.sub(r'[£$€%]', '', clean)

    # 3. Replace non-alphanumeric with underscore
    clean = re.sub(r'[^a-z0-9]+', '_', clean)

    # 4. Collapse multiple underscores
    clean = re.sub(r'_+', '_', clean)

    # 5. Strip leading/trailing underscores
    clean = clean.strip('_')

    # 6. Handle empty result
    if not clean:
        return 'col_unnamed'

    # 7. Suffix reserved words (date, month, year, etc.)
    if clean in RESERVED_WORDS:
        clean = f"{clean}_val"

    # 8. Prefix if starts with digit
    if clean[0].isdigit():
        clean = f"col_{clean}"

    # 9. Truncate to 63 chars (PostgreSQL limit)
    return clean[:63]
```

**Examples:**
```python
"Age 0 to 4"                    → "age_0_to_4"
"Date"                          → "date_val"  (reserved word)
"Waiting time Up to 12 weeks"   → "waiting_time_up_to_12_weeks"
"£ Cost Per Unit"               → "cost_per_unit"
"2024 Total"                    → "col_2024_total"
```

### Collision Detection

**Problem:** "Age 0-4" and "Age 0 to 4" both → "age_0_4"

**Solution:**
```python
seen_names = {}
for col in columns:
    schema_name = to_schema_name(original)

    if schema_name in seen_names:
        seen_names[schema_name] += 1
        schema_name = f"{schema_name}_{seen_names[schema_name]}"  # age_0_4_2
    else:
        seen_names[schema_name] = 1
```

**Result:** `age_0_4`, `age_0_4_2`, `age_0_4_3`, etc.

### Wide Date Detection

**Integrated into schema.py:**

```python
def is_date_column(header: str) -> bool:
    """Check if header looks like a date/period column."""
    patterns = [
        r'^(jan|feb|...|dec)[-_\s]?\d{2,4}',  # Nov-25
        r'^\d{4}[-_](0?[1-9]|1[0-2])',        # 2025-01
        r'^(q[1-4])[-_\s]?\d{2,4}',           # Q1 2025
    ]
    return any(re.match(p, header.lower()) for p in patterns)

def detect_wide_date_pattern(headers: List[str]) -> dict:
    date_cols = [h for h in headers if is_date_column(h)]
    static_cols = [h for h in headers if not is_date_column(h)]

    return {
        'is_wide': len(date_cols) >= 3,  # Threshold
        'date_columns': date_cols,
        'static_columns': static_cols,
        'recommendation': "Use unpivot transformation" if len(date_cols) >= 3 else ""
    }
```

---

## 6. TRANSFORM LAYER

### Unpivot Engine (unpivot.py - 214 lines)

**Core Function:**

```python
def unpivot_wide_dates(
    df: pd.DataFrame,
    static_columns: List[str],      # Keep as-is
    date_columns: List[str],        # Unpivot these
    value_name: str = 'value',
    period_name: str = 'period'
) -> pd.DataFrame:
    """Transform wide date format to long format."""

    # 1. Pandas melt (unpivot)
    df_long = pd.melt(
        df,
        id_vars=static_columns,
        value_vars=date_columns,
        var_name='_raw_period',
        value_name=value_name
    )

    # 2. Parse period column headers to ISO dates
    df_long[period_name] = df_long['_raw_period'].apply(parse_date_column)

    # 3. Reorder columns: static + period + value
    final_cols = static_columns + [period_name, '_raw_period', value_name]
    return df_long[final_cols]
```

**Date Parsing Logic:**

```python
def parse_date_column(col_name: str) -> Optional[str]:
    """Parse date column header to ISO date string."""
    col_lower = col_name.lower().strip()

    # "Nov-25" → "2025-11-01"
    for month_str, month_num in MONTH_MAP.items():
        if col_lower.startswith(month_str):
            match = re.search(r'(\d{2,4})', col_lower)
            if match:
                year = int(match.group(1))
                if year < 100:
                    year += 2000  # 25 → 2025
                return f"{year}-{month_num:02d}-01"

    # "2025-11" → "2025-11-01"
    match = re.match(r'(\d{4})[-_](\d{1,2})', col_lower)
    if match:
        year, month = int(match.group(1)), int(match.group(2))
        return f"{year}-{month:02d}-01"

    # "Q1 2025" → "2025-01-01"
    match = re.match(r'q([1-4])[-_\s]?(\d{2,4})', col_lower)
    if match:
        quarter, year = int(match.group(1)), int(match.group(2))
        month = (quarter - 1) * 3 + 1  # Q1→1, Q2→4, Q3→7, Q4→10
        return f"{year}-{month:02d}-01"
```

**When to Use:**
- Auto-detection: `unpivot=True` in manifest + wide date pattern detected
- Manual: Specify in manifest YAML

**Integration with Pipeline:**

```python
# pipeline.py (lines 150-174)
if unpivot and wide_date_info and wide_date_info.get('is_wide'):
    date_cols = wide_date_info.get('date_columns', [])
    static_cols = wide_date_info.get('static_columns', [])

    original_shape = df.shape
    df = unpivot_wide_dates(df, static_cols, date_cols, 'value', 'period')
    print(f"📊 Unpivot: {original_shape} → {df.shape} (wide→long)")
```

---

## 7. EXAMPLE WORKFLOWS

### Example 1: Single File Load (No LLM)

```bash
# Register source
datawarp register adhd_prescribing "ADHD Prescribing Data" \
    --table tbl_adhd_prescribing \
    --sheet "Table 4"

# Load file
datawarp load \
    https://files.digital.nhs.uk/.../ADHD_Nov25.xlsx \
    --source adhd_prescribing \
    --sheet "Table 4" \
    --mode append \
    --period 2025-11
```

**What happens:**
1. Download file
2. FileExtractor detects structure (deterministic)
3. Create/alter table
4. Insert data with audit columns
5. Log to `tbl_load_history`

### Example 2: Batch Load with LLM Enrichment

```bash
# 1. Generate manifest
python scripts/url_to_manifest.py \
    "https://digital.nhs.uk/.../november-2025" \
    manifests/adhd_nov25_raw.yaml

# 2. Enrich with Gemini
python scripts/enrich_manifest.py \
    manifests/adhd_nov25_raw.yaml \
    manifests/adhd_nov25_enriched.yaml

# 3. Apply enrichment (canonicalize)
python scripts/apply_enrichment.py \
    manifests/adhd_nov25_enriched.yaml \
    manifests/adhd_nov25_enriched_llm_response.json \
    manifests/adhd_nov25_canonical.yaml

# 4. Load batch
datawarp load-batch manifests/adhd_nov25_canonical.yaml

# 5. Export to Parquet
python scripts/export_to_parquet.py --publication adhd output/clinical/adhd/
```

**Result:**
- 11 PostgreSQL tables (staging schema)
- 11 Parquet files + 11 .md files (agent-ready)
- Column metadata stored for agent querying

### Example 3: Cross-Period Consolidation

```bash
# Load August
datawarp load-batch manifests/adhd_aug25_canonical.yaml
# Creates: staging.tbl_adhd_prescribing (50 rows, _period='2025-08')

# Load November (SAME tables)
datawarp load-batch manifests/adhd_nov25_canonical.yaml
# Appends to: staging.tbl_adhd_prescribing (100 rows total, _period='2025-11')

# Export (consolidates both periods)
python scripts/export_to_parquet.py adhd_prescribing output/
# Output: adhd_prescribing.parquet (100 rows, period column distinguishes Aug/Nov)
```

---

## 8. AGENT-READY DATA PHILOSOPHY

### Vision: NHS Excel → PostgreSQL → Parquet → MCP → NL Querying

**Problem Traditional BI Solves:**
```
NHS Excel → SQL Server → Power BI Dashboard
                           ↓
                    Static Reports
                    Analyst Bottleneck
```

**Problem DataWarp Solves:**
```
NHS Excel → PostgreSQL (metadata-rich) → Parquet + .md → MCP Server → NL Queries
                           ↓                    ↓              ↓
                   Semantic context    Self-describing   Zero-Shot
                   Column definitions       format       Intelligence
                   Lineage tracking
```

### What Makes Data "Agent-Ready"

**1. Self-Describing Format (Parquet + .md)**

**Traditional:**
```
File: data.parquet
Schema: {total_items: int64, ...}
```

**Agent-Ready:**
```
File: adhd_prescribing.parquet
Companion: adhd_prescribing.md

## Purpose
Monthly ADHD prescription volumes by Integrated Care Board (Wales)

## Coverage
- Date Range: 2024-06-01 to 2025-11-01
- Geographic Scope: NHS Wales (All Health Boards)
- Rows: 135

## Columns

### Dimensions (Grouping)
#### `icb_name`
- **Description:** Integrated Care Board name
- **Type:** VARCHAR(255)
- **Distinct Values:** 7
- **Search Terms:** icb, board, region

### Measures (Metrics)
#### `total_items`
- **Description:** Total prescription items dispensed
- **Type:** INTEGER
- **Range:** 100 to 45,000
- **Null Rate:** 0.2%
- **Search Terms:** total, items, prescriptions, count

## System Columns
- `_load_id`: Unique identifier for the batch load
- `_period`: Period identifier (YYYY-MM)
- `_loaded_at`: Timestamp when row was loaded
```

**2. Rich Column Metadata**

**Traditional BI:**
```sql
Column: total_items
Type: INTEGER
```

**Agent-Ready:**
```json
{
  "column_name": "total_items",
  "original_name": "Total Items",
  "description": "Number of ADHD prescription items dispensed",
  "data_type": "integer",
  "is_dimension": false,
  "is_measure": true,
  "query_keywords": ["total", "items", "prescriptions", "count"],
  "min_value": 100,
  "max_value": 45000,
  "null_rate": 0.2,
  "metadata_source": "llm",
  "confidence": 0.70
}
```

**3. Lineage Tracking**

Every row knows:
- Which load it came from (`_load_id`)
- When it was loaded (`_loaded_at`)
- What period it represents (`_period`)
- Which manifest file (`_manifest_file_id`)

**Query example:**
```sql
SELECT * FROM staging.tbl_adhd_prescribing
WHERE _load_id = 42;  -- Get all rows from specific load

SELECT * FROM staging.tbl_adhd_prescribing t
JOIN datawarp.tbl_load_history h ON t._load_id = h.id
WHERE h.file_url LIKE '%Nov25%';  -- Get all November data
```

**4. Metadata Confidence Scoring**

Agents know what to trust:
```markdown
### `total_items`
**Metadata Source:** LLM-generated, validated by profiling ✓
**Confidence:** 0.95

Interpretation:
- Confidence > 0.90 → Trust and use directly
- Confidence 0.70-0.89 → Use but verify results
- Confidence < 0.70 → Flag for human review
```

### Example Agent Interaction

**User Ask:** "Which ICBs have increasing ADHD prescribing?"

**Agent Workflow (via future MCP):**

1. **Discovery:** "Find datasets about ADHD prescribing"
   - Searches `.md` files using semantic embeddings
   - Returns: `adhd_prescribing.parquet`

2. **Read Metadata:** `adhd_prescribing.md`
   - Understands: Monthly data, ICB-level, prescription counts
   - Knows: Values <5 suppressed as NULL
   - Sees: Date range 2024-06 to 2025-11

3. **Generate Query:**
   ```sql
   SELECT icb_name,
          LAG(total_items) OVER (PARTITION BY icb_name ORDER BY _period) as prev_items,
          total_items as curr_items,
          (total_items - prev_items) / prev_items * 100 as pct_change
   FROM 'adhd_prescribing.parquet'
   WHERE _period IN ('2025-10-01', '2025-11-01')
   ORDER BY pct_change DESC;
   ```

4. **Execute & Verify:**
   - Runs query via DuckDB
   - Checks if `pct_change` values are plausible (using metadata validation rules)
   - Flags outliers for review

5. **Answer:** "5 ICBs show increasing prescribing:
   - Betsi Cadwaladr: +12.3%
   - Cardiff and Vale: +8.7%
   ..."

**No dashboard needed. No analyst bottleneck.**

---

## 9. CRITICAL ISSUES & LESSONS LEARNED

### Current Blocker: Cross-Period Column Name Inconsistency

**Problem:**
```
August LLM enrichment:   age_0_to_4_referral_count
November LLM enrichment: age_0_to_4_count
Same Excel header: "Age 0 to 4"
```

**Impact:** Schema drift → INSERT fails

**Root Cause:** LLM enriches each period independently, no cross-period awareness

**Solution Designed (not implemented):**
```bash
# Reference-based enrichment
python scripts/enrich_manifest.py \
  manifests/adhd_nov25.yaml \
  manifests/adhd_nov25_enriched.yaml \
  --reference manifests/adhd_aug25_enriched.yaml  # Use August as reference
```

**Next Session:** Re-enrich ADHD Nov with `--reference` flag

### Mission Drift Lesson (2026-01-09)

**What Happened:**
- Got stuck perfecting ingestion (80% → 100% success rate)
- Lost sight of PRIMARY OBJECTIVE: Enable agent querying via MCP
- Never built catalog.parquet, never built MCP server, never tested actual agent querying

**Correction:**
- Accept 42 working sources (80% success)
- Build catalog.parquet (Track A Day 3) - ENABLES DISCOVERY
- Build basic MCP server (Track A Day 4) - ENABLES QUERYING
- Test actual agent querying (Track A Day 5) - VALIDATES PRIMARY OBJECTIVE
- THEN evaluate if ingestion bugs matter

**Lesson:** Ingestion is a MEANS, not the END. Test the primary objective first, then optimize.

### Validation-First Mindset

**Wrong metrics:**
- ❌ "Loaded 3.4M rows" (row count)
- ❌ "Fast" (speed without correctness)

**Right metrics:**
- ✅ "6/6 tests passing on N sources" (validation pass rate)
- ✅ "Agent confidence 95%+" (metadata quality)
- ✅ "Column names match Parquet" (query accuracy)

---

## 10. PRODUCTION READINESS STATUS

### Track A Day 1 Complete (2026-01-08)
- ✅ Metadata storage schema
- ✅ Parquet exporter (300 lines)
- ✅ Validation framework (8 tests: 6 validation + 2 meta-tests)
- ✅ 11 ADHD sources exported and validated
- ✅ Agent test: 95%+ confidence
- ✅ Row ordering bug fixed
- ✅ Fuzzy column matching implemented

### Track A Day 2 Partial (2026-01-09)
- ✅ 4 publications tested (GP Practice, PCN Workforce, ADHD, Dementia)
- ✅ 60 tables, 3.4M rows loaded
- ✅ CSV performance fix (25x speedup)
- ⚠️ Validation not run properly (orphaned files, missing search terms)
- ⚠️ LLM enrichment failures fell back to originals

### Track A Day 3 Partial (2026-01-09 night)
- ✅ Extraction stability proven (ADHD 92%, PCN Workforce 87.5%)
- ✅ Extractor fixes (cell type scanning, decimal detection)
- ✅ Enrichment prompt improvements
- ✅ Schema fixes (VARCHAR(500) for long headers)
- ❌ ADHD Nov blocked by cross-period column name inconsistency
- 🔧 Root cause identified, solution designed but not implemented

### Current State (2026-01-10)
- **Working:** 42 validated sources
- **Blockers:** Cross-period enrichment workflow needs `--reference` flag
- **Next:** Re-enrich ADHD Nov, complete validation, build catalog.parquet

---

## SUMMARY

DataWarp v2.1 is a **production-grade deterministic NHS data ingestion engine** with a clear vision for agent-ready data. The system excels at:

1. **Intelligent Extraction:** Handles complex NHS Excel patterns (multi-tier headers, merged cells, suppressions)
2. **Deterministic Processing:** Core pipeline is LLM-free, ensuring consistency
3. **Schema Evolution:** Automatic drift detection and table alteration
4. **Cross-Period Consolidation:** Single table per source across all time periods
5. **Metadata Capture:** Rich column semantics for agent querying
6. **Agent-Ready Export:** Parquet + .md companions with comprehensive metadata

**Current focus:** Completing metadata foundation (Track A) before scaling to 500+ sources. The primary objective is **enabling natural language querying via MCP**, not perfecting ingestion.

**Architecture Stats:**
- ~27 Python files (~2,500 lines production code)
- ~8 SQL schema files
- 8 comprehensive tests (validation framework)
- 147 registered sources
- 42 validated sources (Track A)

---

**Remember:** Code moves fast. This document is current as of 2026-01-10. Always verify against actual codebase when in doubt.
