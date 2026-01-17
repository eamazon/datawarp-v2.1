# DataWarp User Guide

**The Complete Guide to NHS Data Ingestion**

*Last Updated: 2026-01-17*

---

## Table of Contents

1. [What is DataWarp?](#what-is-datawarp)
2. [Quick Start](#quick-start-5-minutes)
3. [System Architecture](#system-architecture)
4. [Database Schema](#database-schema)
5. [Configuration Patterns](#config-patterns-copy--paste)
6. [Running Backfill](#running-backfill)
7. [Verifying Loads](#verifying-loads)
8. [Reporting & Monitoring](#reporting--monitoring)
9. [Troubleshooting](#troubleshooting)
10. [Reference](#reference)

---

## What is DataWarp?

DataWarp automatically downloads NHS statistics, extracts the data from Excel/CSV files, and loads it into a PostgreSQL database. It then exports to Parquet files for fast querying.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DataWarp Pipeline Flow                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌───────┐ │
│   │   NHS    │    │  Excel   │    │  Postgres │   │ Parquet  │    │ Your  │ │
│   │ Website  │───►│  Files   │───►│   Tables  │──►│  Files   │───►│Queries│ │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘    └───────┘ │
│        │               │               │               │                     │
│        ▼               ▼               ▼               ▼                     │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│   │ Landing  │    │ Download │    │  Schema  │    │   Fast   │              │
│   │  Pages   │    │ & Parse  │    │Evolution │    │Analytics │              │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**In plain English:** You tell DataWarp which NHS publications you want, and it handles everything else.

---

## Quick Start (5 Minutes)

### 1. Setup

```bash
# Clone and enter directory
cd datawarp-v2.1

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install
pip install -e .

# Setup database
python scripts/reset_db.py
```

### 2. Run Your First Load

```bash
# Load ADHD data (3 periods)
python scripts/backfill.py --pub adhd
```

That's it! You now have NHS ADHD data in your database.

### 3. Check Your Data

```bash
# See what loaded
datawarp list

# Query the data
psql -d databot_dev -c "SELECT COUNT(*) FROM staging.tbl_adhd"
```

---

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DataWarp System                                 │
├────────────────┬────────────────┬────────────────┬─────────────────────────┤
│   Discovery    │    Extract     │      Load      │         Export          │
├────────────────┼────────────────┼────────────────┼─────────────────────────┤
│                │                │                │                         │
│ publications   │ url_to_        │ loader/        │ export_to_              │
│ _v2.yaml       │ manifest.py    │ pipeline.py    │ parquet.py              │
│                │                │                │                         │
│ ┌────────────┐ │ ┌────────────┐ │ ┌────────────┐ │ ┌─────────────────────┐ │
│ │URL Resolver│ │ │ Extractor  │ │ │DDL Generate│ │ │ Parquet Writer      │ │
│ │Period Gen  │ │ │Sheet Detect│ │ │Insert Batch│ │ │ + Metadata          │ │
│ └────────────┘ │ └────────────┘ │ └────────────┘ │ └─────────────────────┘ │
│       ↓        │       ↓        │       ↓        │           ↓             │
│ Auto-generate  │  Parse Excel   │  PostgreSQL    │  output/*.parquet       │
│ periods        │  multi-sheet   │  staging.*     │                         │
│                │                │                │                         │
└────────────────┴────────────────┴────────────────┴─────────────────────────┘
```

### Data Flow Diagram

```
                    ┌─────────────────────────────────────┐
                    │     config/publications_v2.yaml     │
                    │  (Publication definitions & URLs)   │
                    └─────────────────┬───────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────────┐
                    │        URL Resolver Module          │
                    │   - Generate periods (schedule)     │
                    │   - Build URLs (template/explicit)  │
                    │   - Apply publication lag           │
                    └─────────────────┬───────────────────┘
                                      │
            ┌─────────────────────────┼─────────────────────────┐
            ▼                         ▼                         ▼
     ┌─────────────┐          ┌─────────────┐          ┌─────────────┐
     │ Period 1    │          │ Period 2    │          │ Period N    │
     │ Download    │          │ Download    │          │ Download    │
     └──────┬──────┘          └──────┬──────┘          └──────┬──────┘
            │                        │                        │
            ▼                        ▼                        ▼
     ┌─────────────────────────────────────────────────────────────┐
     │                      Extractor Module                        │
     │  - Detect multi-tier headers                                 │
     │  - Handle merged cells                                       │
     │  - Infer column types                                        │
     │  - Find data boundaries                                      │
     └─────────────────────────────┬───────────────────────────────┘
                                   │
                                   ▼
     ┌─────────────────────────────────────────────────────────────┐
     │                    Enrichment (Optional)                     │
     │  - LLM adds semantic column names                            │
     │  - Reference manifest for consistency                        │
     └─────────────────────────────┬───────────────────────────────┘
                                   │
                                   ▼
     ┌─────────────────────────────────────────────────────────────┐
     │                       Loader Module                          │
     │  - Schema evolution (ALTER TABLE ADD)                        │
     │  - Batch INSERT with provenance                              │
     │  - Idempotent loading                                        │
     └─────────────────────────────┬───────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
           ┌───────────────┐             ┌───────────────┐
           │   PostgreSQL  │             │    Parquet    │
           │ staging.tbl_* │             │ output/*.pq   │
           └───────────────┘             └───────────────┘
```

---

## Database Schema

DataWarp uses two PostgreSQL schemas:
- **`datawarp`** - Registry and audit tables (system metadata)
- **`staging`** - Loaded data tables (NHS data)

### Schema Visual Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PostgreSQL Database                                 │
├─────────────────────────────────┬───────────────────────────────────────────┤
│         datawarp schema         │              staging schema                │
├─────────────────────────────────┼───────────────────────────────────────────┤
│                                 │                                           │
│  ┌───────────────────────────┐  │  ┌─────────────────────────────────────┐  │
│  │    tbl_data_sources       │  │  │          tbl_adhd                   │  │
│  │  (Source registry)        │  │  │  (Loaded NHS ADHD data)             │  │
│  └───────────────────────────┘  │  └─────────────────────────────────────┘  │
│            │                    │                                           │
│            ▼                    │  ┌─────────────────────────────────────┐  │
│  ┌───────────────────────────┐  │  │       tbl_gp_appointments           │  │
│  │    tbl_load_history       │  │  │  (Loaded GP Appointments data)      │  │
│  │  (Audit trail)            │  │  └─────────────────────────────────────┘  │
│  └───────────────────────────┘  │                                           │
│                                 │  ┌─────────────────────────────────────┐  │
│  ┌───────────────────────────┐  │  │       tbl_ae_waiting_times          │  │
│  │    tbl_pipeline_log       │  │  │  (Loaded A&E data)                  │  │
│  │  (Real-time events)       │  │  └─────────────────────────────────────┘  │
│  └───────────────────────────┘  │                                           │
│                                 │               ... more tables             │
│  ┌───────────────────────────┐  │                                           │
│  │   tbl_manifest_files      │  │                                           │
│  │  (Batch load tracking)    │  │                                           │
│  └───────────────────────────┘  │                                           │
│                                 │                                           │
│  ┌───────────────────────────┐  │                                           │
│  │  tbl_canonical_sources    │  │                                           │
│  │  (Cross-period registry)  │  │                                           │
│  └───────────────────────────┘  │                                           │
│                                 │                                           │
└─────────────────────────────────┴───────────────────────────────────────────┘
```

### Registry Tables (datawarp schema)

#### tbl_data_sources - Source Registry

```sql
-- Stores registered data sources with metadata
CREATE TABLE datawarp.tbl_data_sources (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,    -- Unique source identifier
    name VARCHAR(255),                    -- Human-readable name
    table_name VARCHAR(100) NOT NULL,     -- Target table in staging
    schema_name VARCHAR(50) DEFAULT 'staging',
    default_sheet VARCHAR(100),           -- Default Excel sheet
    description TEXT,                     -- What this dataset contains
    metadata JSONB,                       -- Columns, structural info
    domain VARCHAR(50),                   -- clinical, operational, financial
    tags TEXT[],                          -- Search tags
    created_at TIMESTAMP DEFAULT NOW(),
    last_load_at TIMESTAMP
);
```

**Example Query:**
```sql
-- List all registered sources
SELECT code, name, table_name, domain, last_load_at
FROM datawarp.tbl_data_sources
ORDER BY last_load_at DESC;
```

#### tbl_load_history - Audit Trail

```sql
-- Complete history of all load operations
CREATE TABLE datawarp.tbl_load_history (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES tbl_data_sources(id),
    file_url VARCHAR(500) NOT NULL,       -- Source file URL
    rows_loaded INTEGER NOT NULL,         -- Rows inserted
    columns_added TEXT[],                 -- New columns from drift
    load_mode VARCHAR(20) DEFAULT 'append',
    loaded_at TIMESTAMP DEFAULT NOW()
);
```

**Example Query:**
```sql
-- See load history for a source
SELECT lh.loaded_at, lh.rows_loaded, lh.columns_added, lh.file_url
FROM datawarp.tbl_load_history lh
JOIN datawarp.tbl_data_sources ds ON lh.source_id = ds.id
WHERE ds.code = 'adhd_summary'
ORDER BY lh.loaded_at DESC;
```

#### tbl_pipeline_log - Real-time Events

```sql
-- Pipeline events for observability
CREATE TABLE datawarp.tbl_pipeline_log (
    id SERIAL PRIMARY KEY,
    manifest_name VARCHAR(100),
    source_code VARCHAR(100),
    period VARCHAR(20),                   -- e.g., "2025-11"
    file_url VARCHAR(500),
    category VARCHAR(20) NOT NULL,        -- 'dq', 'perf', 'schema', 'op'
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) DEFAULT 'info',  -- 'info', 'warning', 'error'
    message TEXT,
    metadata JSONB,
    duration_ms NUMERIC(10,2),
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Example Query:**
```sql
-- Find recent errors
SELECT period, source_code, event_type, message, created_at
FROM datawarp.tbl_pipeline_log
WHERE severity = 'error'
ORDER BY created_at DESC
LIMIT 20;
```

#### tbl_manifest_files - Batch Load Tracking

```sql
-- Tracks individual file loads from manifests
CREATE TABLE datawarp.tbl_manifest_files (
    id SERIAL PRIMARY KEY,
    manifest_name VARCHAR(100) NOT NULL,
    manifest_file_path VARCHAR(255),
    source_code VARCHAR(100) NOT NULL,
    file_url VARCHAR(500) NOT NULL,
    period VARCHAR(10),
    status VARCHAR(20) NOT NULL,          -- pending, loaded, failed, skipped
    error_details JSONB,                  -- Detailed error info
    rows_loaded INTEGER,
    columns_added JSONB,
    loaded_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(manifest_name, file_url)
);
```

**Example Query:**
```sql
-- Check status of a batch load
SELECT source_code, period, status, rows_loaded, loaded_at
FROM datawarp.tbl_manifest_files
WHERE manifest_name = 'adhd_backfill'
ORDER BY loaded_at;
```

#### tbl_canonical_sources - Cross-Period Registry

```sql
-- Canonical source registry for consolidation
CREATE TABLE datawarp.tbl_canonical_sources (
    canonical_code VARCHAR(100) PRIMARY KEY,
    publication_id VARCHAR(50),
    canonical_name TEXT NOT NULL,
    canonical_table VARCHAR(100) NOT NULL,
    fingerprint JSONB NOT NULL,           -- Structural fingerprint
    first_seen_period VARCHAR(20),
    last_seen_period VARCHAR(20),
    total_loads INTEGER DEFAULT 0,
    total_rows_loaded BIGINT DEFAULT 0,
    description TEXT,
    domain VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### tbl_column_metadata - Column Semantics

```sql
-- Column-level semantic metadata
CREATE TABLE datawarp.tbl_column_metadata (
    canonical_source_code VARCHAR(100),
    column_name VARCHAR(100),
    original_name VARCHAR(500),           -- Original Excel header
    description TEXT,                     -- What this column measures
    data_type VARCHAR(50),                -- integer, varchar, numeric
    is_dimension BOOLEAN DEFAULT FALSE,   -- Grouping column?
    is_measure BOOLEAN DEFAULT FALSE,     -- Numeric metric?
    query_keywords TEXT[],                -- Search terms
    null_rate NUMERIC(5,2),               -- % null values
    distinct_count INTEGER,               -- Unique values
    PRIMARY KEY (canonical_source_code, column_name)
);
```

### Staging Tables (staging schema)

Staging tables are created dynamically when data is loaded. Each table includes:

```sql
-- Example: staging.tbl_adhd
CREATE TABLE staging.tbl_adhd (
    -- Business columns (from Excel file)
    org_code VARCHAR(255),
    org_name VARCHAR(255),
    referrals_received INTEGER,
    patients_waiting INTEGER,
    ...

    -- Provenance columns (added by DataWarp)
    _load_id INTEGER,                     -- Links to tbl_load_history
    _loaded_at TIMESTAMP,                 -- When this row was loaded
    _period VARCHAR(20),                  -- Data period (e.g., "2025-11")
    _source_file VARCHAR(500),            -- Original filename
    _sheet_name VARCHAR(100),             -- Excel sheet name
    _period_start DATE,                   -- Period start date
    _period_end DATE                      -- Period end date
);
```

### Schema Relationships

```
                        ┌──────────────────────────┐
                        │   tbl_canonical_sources  │
                        │   (Cross-period master)  │
                        └────────────┬─────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
┌───────────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐
│  tbl_source_mappings  │  │tbl_drift_events │  │  tbl_column_metadata    │
│  (LLM → Canonical)    │  │(Schema changes) │  │  (Column semantics)     │
└───────────────────────┘  └─────────────────┘  └─────────────────────────┘

                        ┌──────────────────────────┐
                        │    tbl_data_sources      │
                        │   (Source registry)      │
                        └────────────┬─────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
┌───────────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐
│   tbl_load_history    │  │tbl_manifest_files│ │   staging.tbl_*         │
│  (Audit trail)        │  │(Batch tracking) │  │   (Actual data)         │
└───────────────────────┘  └─────────────────┘  └─────────────────────────┘
```

---

## Config Patterns (Copy & Paste)

### Understanding the Config File

DataWarp reads from `config/publications.yaml` (old) or `config/publications_v2.yaml` (new).

### Pattern Decision Tree

```
                      ┌─────────────────────────────┐
                      │  Is the URL predictable?    │
                      └──────────────┬──────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
            ┌───────────────┐                 ┌───────────────┐
            │      YES      │                 │      NO       │
            │ (NHS Digital) │                 │ (NHS England) │
            └───────┬───────┘                 └───────┬───────┘
                    │                                 │
                    ▼                                 ▼
          ┌─────────────────┐               ┌─────────────────┐
          │  periods.mode:  │               │  periods.mode:  │
          │    schedule     │               │     manual      │
          │                 │               │                 │
          │  url.mode:      │               │  url.mode:      │
          │    template     │               │    explicit     │
          └─────────────────┘               └─────────────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
┌───────────────┐       ┌───────────────┐
│   Monthly?    │       │  Quarterly?   │
│               │       │               │
│ No months:    │       │ months:       │
│ filter        │       │ [5, 8, 11]    │
└───────────────┘       └───────────────┘
```

### Pattern A: Monthly Publication (NHS Digital)

```yaml
gp_appointments:
  name: "Appointments in General Practice"
  frequency: monthly
  landing_page: https://digital.nhs.uk/.../appointments-in-general-practice

  periods:
    mode: schedule
    start: "2024-01"
    end: current
    publication_lag_weeks: 6

  url:
    mode: template
    pattern: "{landing_page}/{month_name}-{year}"
```

### Pattern B: Quarterly Publication (Specific Months)

```yaml
adhd:
  name: "ADHD Management Information"
  frequency: quarterly
  landing_page: https://digital.nhs.uk/.../mi-adhd

  periods:
    mode: schedule
    start: "2025-05"
    end: current
    months: [5, 8, 11]           # Only May, Aug, Nov
    publication_lag_weeks: 6

  url:
    mode: template
    pattern: "{landing_page}/{month_name}-{year}"
```

### Pattern C: Publication with URL Exceptions

```yaml
ldhc_scheme:
  name: "Learning Disabilities Health Check"
  frequency: monthly
  landing_page: https://digital.nhs.uk/.../learning-disabilities-health-check-scheme

  periods:
    mode: schedule
    start: "2024-01"
    end: current
    publication_lag_weeks: 6

  url:
    mode: template
    pattern: "{landing_page}/england-{month_name}-{year}"
    exceptions:
      "2024-01": "{landing_page}/january-2024"  # First month was different
```

### Pattern D: Publication with Offset (SHMI)

```yaml
shmi:
  name: "Summary Hospital-level Mortality Indicator"
  frequency: quarterly
  landing_page: https://digital.nhs.uk/.../shmi

  periods:
    mode: schedule
    start: "2024-08"
    end: current
    publication_offset_months: 5  # Data Aug 2025 -> Published Jan 2026

  url:
    mode: template
    pattern: "{landing_page}/{pub_year}-{pub_month}"
```

### Pattern E: Explicit URLs (NHS England with Hash Codes)

```yaml
ae_waiting_times:
  name: "A&E Waiting Times"
  frequency: monthly
  landing_page: https://www.england.nhs.uk/.../ae-waiting-times/

  periods:
    mode: manual

  url:
    mode: explicit

  urls:
    - period: "2025-12"
      url: https://www.england.nhs.uk/.../December-2025-AE-by-provider-Sa9Xc.xls
```

### Pattern F: Fiscal Quarters

```yaml
bed_overnight:
  name: "Bed Availability - Overnight"
  frequency: quarterly
  landing_page: https://www.england.nhs.uk/.../bed-data-overnight/

  periods:
    mode: schedule
    type: fiscal_quarter
    start_fy: 2025               # FY2024-25 starts Apr 2024
    end: current
    publication_lag_weeks: 8

  url:
    mode: explicit

  urls:
    - period: "FY25-Q1"
      url: https://...Q1-2024-25.xlsx
    - period: "FY25-Q2"
      url: https://...Q2-2024-25.xlsx
```

---

## Running Backfill

### Basic Commands

```bash
# Process all publications
python scripts/backfill.py

# Process one publication
python scripts/backfill.py --pub adhd

# Use custom config file
python scripts/backfill.py --config config/publications_v2.yaml

# Dry run (show what would be processed)
python scripts/backfill.py --dry-run

# Show progress status
python scripts/backfill.py --status
```

### Handling Failures

```bash
# Retry failed periods
python scripts/backfill.py --retry-failed

# Force reload (even if already processed)
python scripts/backfill.py --pub adhd --force
```

### Using References

```bash
# Use specific reference manifest (for consistent column naming)
python scripts/backfill.py --pub adhd --reference manifests/production/adhd/adhd_aug25_enriched.yaml

# Fresh LLM enrichment (ignore references)
python scripts/backfill.py --pub adhd --no-reference
```

---

## Verifying Loads

### Quick Health Check

```bash
# Check overall status
python scripts/backfill.py --status
```

### Database Verification Queries

```sql
-- 1. Check total rows loaded per publication
SELECT
    ds.code AS source,
    COUNT(*) AS total_rows,
    COUNT(DISTINCT s._period) AS periods_loaded,
    MIN(s._period) AS first_period,
    MAX(s._period) AS last_period
FROM datawarp.tbl_data_sources ds
JOIN staging.tbl_adhd s ON true  -- Replace with actual table
GROUP BY ds.code;

-- 2. Check load history
SELECT
    source_code,
    period,
    status,
    rows_loaded,
    loaded_at
FROM datawarp.tbl_manifest_files
WHERE manifest_name LIKE 'adhd%'
ORDER BY loaded_at DESC;

-- 3. Find failed loads
SELECT
    manifest_name,
    source_code,
    period,
    status,
    error_details->>'error_type' AS error_type,
    error_details->>'error_message' AS error_message
FROM datawarp.tbl_manifest_files
WHERE status = 'failed'
ORDER BY created_at DESC;

-- 4. Check for schema drift
SELECT
    canonical_code,
    period,
    drift_type,
    severity,
    details->>'columns' AS affected_columns,
    detected_at
FROM datawarp.tbl_drift_events
WHERE severity IN ('warning', 'error')
ORDER BY detected_at DESC;

-- 5. Verify data completeness
SELECT
    _period,
    COUNT(*) AS row_count,
    COUNT(DISTINCT org_code) AS orgs,
    _loaded_at
FROM staging.tbl_adhd
GROUP BY _period, _loaded_at
ORDER BY _period;
```

### Verification Checklist

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         Load Verification Checklist                        │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  [ ] 1. No failed loads in tbl_manifest_files                              │
│      SELECT COUNT(*) FROM tbl_manifest_files WHERE status = 'failed'       │
│                                                                            │
│  [ ] 2. Expected periods are present                                       │
│      SELECT DISTINCT _period FROM staging.tbl_adhd ORDER BY _period        │
│                                                                            │
│  [ ] 3. Row counts are reasonable                                          │
│      Compare with previous periods or NHS documentation                    │
│                                                                            │
│  [ ] 4. No critical drift events                                           │
│      SELECT * FROM tbl_drift_events WHERE severity = 'error'               │
│                                                                            │
│  [ ] 5. Parquet exports exist                                              │
│      ls -la output/*.parquet                                               │
│                                                                            │
│  [ ] 6. State file updated                                                 │
│      cat state/state.json | jq '.processed'                                │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Reporting & Monitoring

### Load Summary Report

```sql
-- Daily load summary
SELECT
    DATE(loaded_at) AS load_date,
    COUNT(*) AS files_loaded,
    SUM(rows_loaded) AS total_rows,
    COUNT(DISTINCT manifest_name) AS manifests,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) AS failures
FROM datawarp.tbl_manifest_files
WHERE loaded_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY DATE(loaded_at)
ORDER BY load_date DESC;
```

### Publication Status Dashboard

```sql
-- Publication health overview
SELECT
    ds.code AS publication,
    ds.name,
    COUNT(DISTINCT mf.period) AS periods_loaded,
    SUM(mf.rows_loaded) AS total_rows,
    MAX(mf.loaded_at) AS last_load,
    CASE
        WHEN MAX(mf.loaded_at) > CURRENT_TIMESTAMP - INTERVAL '30 days' THEN 'Active'
        ELSE 'Stale'
    END AS status
FROM datawarp.tbl_data_sources ds
LEFT JOIN datawarp.tbl_manifest_files mf ON ds.code = mf.source_code
GROUP BY ds.code, ds.name
ORDER BY last_load DESC NULLS LAST;
```

### Error Analysis

```sql
-- Error breakdown by type
SELECT
    error_details->>'error_type' AS error_type,
    COUNT(*) AS occurrences,
    array_agg(DISTINCT source_code) AS affected_sources
FROM datawarp.tbl_manifest_files
WHERE status = 'failed'
GROUP BY error_details->>'error_type'
ORDER BY occurrences DESC;
```

### Pipeline Performance

```sql
-- Performance metrics
SELECT
    source_code,
    event_type,
    AVG(duration_ms) AS avg_duration_ms,
    MAX(duration_ms) AS max_duration_ms,
    COUNT(*) AS occurrences
FROM datawarp.tbl_pipeline_log
WHERE category = 'perf'
  AND created_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY source_code, event_type
ORDER BY avg_duration_ms DESC;
```

### Monitoring Queries for Alerts

```sql
-- Find loads with no rows (potential issue)
SELECT manifest_name, source_code, period, loaded_at
FROM datawarp.tbl_manifest_files
WHERE status = 'loaded' AND rows_loaded = 0;

-- Find unusually large row counts (potential duplication)
WITH stats AS (
    SELECT
        source_code,
        AVG(rows_loaded) AS avg_rows,
        STDDEV(rows_loaded) AS stddev_rows
    FROM datawarp.tbl_manifest_files
    WHERE status = 'loaded'
    GROUP BY source_code
)
SELECT mf.source_code, mf.period, mf.rows_loaded, s.avg_rows
FROM datawarp.tbl_manifest_files mf
JOIN stats s ON mf.source_code = s.source_code
WHERE mf.rows_loaded > s.avg_rows + (3 * s.stddev_rows);

-- Check for missing expected periods
WITH expected AS (
    SELECT generate_series(
        '2025-01-01'::date,
        CURRENT_DATE,
        '1 month'::interval
    )::date AS expected_date
)
SELECT TO_CHAR(expected_date, 'YYYY-MM') AS missing_period
FROM expected e
WHERE TO_CHAR(expected_date, 'YYYY-MM') NOT IN (
    SELECT DISTINCT period FROM datawarp.tbl_manifest_files
    WHERE source_code = 'adhd'
);
```

---

## Troubleshooting

### Common Issues

#### "404 Not Found"

```
ERROR: 404 Client Error: Not Found for url: ...
```

**Cause:** The period doesn't exist yet (or never will).

**Fix:**
- Check the start date in your config
- Increase `publication_lag_weeks`
- Verify the URL pattern is correct

#### "Column mismatch"

```
WARNING: Column drift detected
```

**This is normal!** NHS often changes column names between periods. DataWarp automatically adds new columns.

**Check drift details:**
```sql
SELECT * FROM datawarp.tbl_drift_events
WHERE canonical_code = 'your_source'
ORDER BY detected_at DESC;
```

#### "Already processed"

```
Skipping adhd/2025-11 - already processed
```

**Cause:** This period is in `state/state.json`.

**Fix:** Use `--force` to reload, or delete the entry from state.json.

#### "LLM enrichment failed"

```
ERROR: Enrichment failed
```

**Fix:**
1. Check your `GEMINI_API_KEY` in `.env`
2. Try `--no-reference` for fresh enrichment
3. Check logs in `logs/`

### Diagnostic Commands

```bash
# Check state file
cat state/state.json | python -m json.tool

# Check recent logs
tail -100 logs/backfill_*.log

# Check database connectivity
psql -d databot_dev -c "SELECT 1"

# List loaded tables
psql -d databot_dev -c "SELECT table_name FROM information_schema.tables WHERE table_schema = 'staging'"
```

---

## Reference

### File Locations

| Path | Purpose |
|------|---------|
| `config/publications.yaml` | Publication registry (old format) |
| `config/publications_v2.yaml` | Publication registry (new format) |
| `manifests/backfill/` | Generated manifests |
| `output/` | Parquet exports |
| `state/state.json` | Processing state |
| `logs/` | Detailed logs |
| `.env` | Environment variables |

### Environment Variables

```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=databot_dev
POSTGRES_USER=databot_dev_user
POSTGRES_PASSWORD=your_password

# LLM (for enrichment)
GEMINI_API_KEY=your_gemini_key
LLM_MODEL=gemini-2.0-flash-exp
```

### Period Formats

| Type | Format | Example |
|------|--------|---------|
| Monthly | `YYYY-MM` | `2025-11` |
| Fiscal Quarter | `FYyy-QN` | `FY25-Q1` |
| Fiscal Year | `FYyyyy-yy` | `FY2024-25` |

### NHS Fiscal Year

- Runs April to March
- FY25 = April 2024 to March 2025
- Q1 = Apr-Jun, Q2 = Jul-Sep, Q3 = Oct-Dec, Q4 = Jan-Mar

### Glossary

| Term | Meaning |
|------|---------|
| **Publication** | An NHS data release (e.g., ADHD, A&E Waiting Times) |
| **Period** | A time slice of data (e.g., "2025-11" for November 2025) |
| **Landing Page** | NHS webpage listing all periods for a publication |
| **Manifest** | YAML file describing Excel structure |
| **Enrichment** | LLM adds semantic column names |
| **Canonicalization** | Removes date patterns from codes |
| **Parquet** | Columnar file format for fast queries |
| **Schema Drift** | Column changes between periods |
| **Provenance** | Tracking where each row came from |

---

## Quick Reference Card

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         DATAWARP QUICK REFERENCE                           │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  LOAD DATA                                                                 │
│    python scripts/backfill.py --pub adhd                                   │
│    python scripts/backfill.py --config config/publications_v2.yaml         │
│                                                                            │
│  CHECK STATUS                                                              │
│    python scripts/backfill.py --status                                     │
│    datawarp list                                                           │
│                                                                            │
│  VERIFY LOADS                                                              │
│    SELECT * FROM datawarp.tbl_manifest_files WHERE status = 'failed'       │
│    SELECT _period, COUNT(*) FROM staging.tbl_adhd GROUP BY _period         │
│                                                                            │
│  RETRY / FORCE                                                             │
│    python scripts/backfill.py --retry-failed                               │
│    python scripts/backfill.py --pub adhd --force                           │
│                                                                            │
│  CONFIG FORMAT                                                             │
│    periods.mode: schedule | manual                                         │
│    url.mode: template | explicit                                           │
│                                                                            │
│  PERIOD FORMATS                                                            │
│    Monthly: 2025-11                                                        │
│    Quarter: FY25-Q1                                                        │
│    Year: FY2024-25                                                         │
│                                                                            │
│  KEY TABLES                                                                │
│    datawarp.tbl_manifest_files  - Load tracking                            │
│    datawarp.tbl_pipeline_log    - Events & errors                          │
│    datawarp.tbl_drift_events    - Schema changes                           │
│    staging.tbl_*                - Loaded data                              │
│                                                                            │
│  FILES                                                                     │
│    Config:    config/publications_v2.yaml                                  │
│    State:     state/state.json                                             │
│    Logs:      logs/backfill_*.log                                          │
│    Output:    output/*.parquet                                             │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

*Happy data wrangling!*
