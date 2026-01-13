# Database Schema

**Created:** 2026-01-11 UTC
**Purpose:** Tables, relationships, and audit trail

---

## Schema Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PostgreSQL Database Layout                           │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌───────────────────────────────────────┐
                    │             databot_dev                │
                    │         (PostgreSQL 15+)              │
                    └───────────────────────────────────────┘
                                      │
              ┌───────────────────────┴───────────────────────┐
              │                                               │
              ▼                                               ▼
    ┌─────────────────────┐                     ┌─────────────────────┐
    │   datawarp schema   │                     │   staging schema    │
    │                     │                     │                     │
    │ Registry & Metadata │                     │    Actual Data      │
    │ (~16 KB overhead)   │                     │    (~15 GB data)    │
    └─────────────────────┘                     └─────────────────────┘
              │                                               │
              ▼                                               ▼
    ┌─────────────────────┐                     ┌─────────────────────┐
    │ • tbl_data_sources  │                     │ • tbl_adhd_*        │
    │ • tbl_load_history  │                     │ • tbl_pcn_*         │
    │ • tbl_manifest_files│                     │ • tbl_gp_*          │
    │ • tbl_load_events   │                     │ • tbl_waiting_*     │
    └─────────────────────┘                     │ • ... (181 tables)  │
                                                └─────────────────────┘
```

---

## Registry Tables

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          datawarp.tbl_data_sources                           │
│                           (Source Registration)                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌───────────────┬─────────────┬───────────────────────────────────────────────┐
│ Column        │ Type        │ Description                                   │
├───────────────┼─────────────┼───────────────────────────────────────────────┤
│ id            │ SERIAL PK   │ Auto-increment identifier                     │
│ code          │ VARCHAR     │ Unique source code (adhd_prevalence_estimate) │
│ table_name    │ VARCHAR     │ Target table (tbl_adhd_prevalence_estimate)   │
│ schema_name   │ VARCHAR     │ Schema (staging)                              │
│ description   │ TEXT        │ LLM-generated description                     │
│ created_at    │ TIMESTAMP   │ Registration time                             │
│ last_load_at  │ TIMESTAMP   │ Most recent load                              │
│ load_count    │ INTEGER     │ Number of loads                               │
│ row_count     │ INTEGER     │ Current row count                             │
│ column_count  │ INTEGER     │ Number of columns                             │
└───────────────┴─────────────┴───────────────────────────────────────────────┘

Example:
┌────┬────────────────────────┬─────────────────────────────┬─────────┐
│ id │ code                   │ table_name                  │ schema  │
├────┼────────────────────────┼─────────────────────────────┼─────────┤
│ 1  │ adhd_prevalence_est    │ tbl_adhd_prevalence_est     │ staging │
│ 2  │ pcn_wf_fte_national    │ tbl_pcn_wf_fte_national     │ staging │
│ 3  │ gp_prac_reg_all        │ tbl_gp_prac_reg_all         │ staging │
└────┴────────────────────────┴─────────────────────────────┴─────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                          datawarp.tbl_load_history                           │
│                             (Load Audit Trail)                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌───────────────┬─────────────┬───────────────────────────────────────────────┐
│ Column        │ Type        │ Description                                   │
├───────────────┼─────────────┼───────────────────────────────────────────────┤
│ id            │ SERIAL PK   │ Auto-increment identifier                     │
│ source_id     │ INTEGER FK  │ References tbl_data_sources(id)               │
│ file_url      │ TEXT        │ Source file URL (NHS link)                    │
│ rows_loaded   │ INTEGER     │ Rows in this load                             │
│ loaded_at     │ TIMESTAMP   │ Load timestamp                                │
│ load_mode     │ VARCHAR     │ APPEND / REPLACE / MERGE                      │
│ status        │ VARCHAR     │ SUCCESS / FAILED / PARTIAL                    │
│ error_message │ TEXT        │ Error details if failed                       │
└───────────────┴─────────────┴───────────────────────────────────────────────┘

Example:
┌────┬───────────┬──────────────────────────────────┬───────┬─────────┐
│ id │ source_id │ file_url                         │ rows  │ status  │
├────┼───────────┼──────────────────────────────────┼───────┼─────────┤
│ 1  │ 1         │ https://files.nhs.uk/adhd/aug25  │ 8149  │ SUCCESS │
│ 2  │ 1         │ https://files.nhs.uk/adhd/nov25  │ 8500  │ SUCCESS │
│ 3  │ 2         │ https://files.nhs.uk/pcn/may25   │ 50000 │ SUCCESS │
└────┴───────────┴──────────────────────────────────┴───────┴─────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                         datawarp.tbl_manifest_files                          │
│                           (Manifest Tracking)                                │
└─────────────────────────────────────────────────────────────────────────────┘

┌───────────────┬─────────────┬───────────────────────────────────────────────┐
│ Column        │ Type        │ Description                                   │
├───────────────┼─────────────┼───────────────────────────────────────────────┤
│ id            │ SERIAL PK   │ Auto-increment identifier                     │
│ manifest_name │ VARCHAR     │ Manifest file name                            │
│ source_code   │ VARCHAR     │ Source code in manifest                       │
│ file_url      │ TEXT        │ NHS file URL                                  │
│ status        │ VARCHAR     │ PENDING / LOADED / FAILED                     │
│ created_at    │ TIMESTAMP   │ Record creation                               │
│ loaded_at     │ TIMESTAMP   │ When loaded (if status = LOADED)              │
└───────────────┴─────────────┴───────────────────────────────────────────────┘
```

---

## Table Relationships

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Foreign Key Relationships                           │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌───────────────────────────────────┐
                    │     datawarp.tbl_data_sources     │
                    │                                   │
                    │  id ◀─────────────────────────────┼─────────────────────┐
                    │  code                             │                     │
                    │  table_name ─────────────────────▶│ staging.tbl_*       │
                    │  schema_name                      │ (1:1 relationship)  │
                    └───────────────┬───────────────────┘                     │
                                    │                                         │
              ┌─────────────────────┴─────────────────────┐                   │
              │ (FK: source_id)                           │                   │
              ▼                                           ▼                   │
    ┌─────────────────────┐                 ┌─────────────────────┐           │
    │ tbl_load_history    │                 │ tbl_manifest_files  │           │
    │                     │                 │                     │           │
    │ source_id ──────────┼─────────────────┼──▶ source_code      │           │
    │ file_url            │                 │ manifest_name       │           │
    │ rows_loaded         │                 │ status              │           │
    │ loaded_at           │                 │                     │           │
    └─────────────────────┘                 └─────────────────────┘           │
              │                                                               │
              │                                                               │
              ▼                                                               │
    ┌─────────────────────────────────────────────────────────────────────────┘
    │
    │     Future: CASCADE DELETE
    │     ┌─────────────────────────────────────────────────────────────────┐
    │     │ DELETE FROM tbl_data_sources WHERE code = 'adhd_summary'       │
    │     │                                                                 │
    │     │ Automatically:                                                  │
    │     │   → DELETE FROM tbl_load_history WHERE source_id = ...         │
    │     │   → DELETE FROM tbl_manifest_files WHERE source_code = ...     │
    │     │   → DROP TABLE staging.tbl_adhd_summary (via trigger)          │
    │     └─────────────────────────────────────────────────────────────────┘
```

---

## Staging Table Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          staging.tbl_* Pattern                               │
│                        (Auto-generated from manifest)                        │
└─────────────────────────────────────────────────────────────────────────────┘

Example: staging.tbl_adhd_prevalence_estimate

┌──────────────────────────┬─────────────┬────────────────────────────────────┐
│ Column                   │ Type        │ Source                             │
├──────────────────────────┼─────────────┼────────────────────────────────────┤
│                          │             │                                    │
│ -- Business columns --   │             │                                    │
│ reporting_period_start   │ DATE        │ From NHS Excel, LLM-named          │
│ age_band                 │ VARCHAR     │ From NHS Excel, LLM-named          │
│ prevalence_rate          │ NUMERIC     │ From NHS Excel, type inferred      │
│ patient_count            │ INTEGER     │ From NHS Excel, type inferred      │
│ ...                      │ ...         │                                    │
│                          │             │                                    │
│ -- System columns --     │             │                                    │
│ _load_id                 │ INTEGER     │ Batch identifier (auto-added)      │
│ _source_file             │ TEXT        │ Source URL (auto-added)            │
│ _loaded_at               │ TIMESTAMP   │ Load timestamp (auto-added)        │
└──────────────────────────┴─────────────┴────────────────────────────────────┘

System columns enable:
┌─────────────────────────────────────────────────────────────────────────────┐
│ -- Trace data lineage                                                        │
│ SELECT * FROM staging.tbl_adhd_prevalence WHERE _load_id = 42;              │
│                                                                              │
│ -- Find data from specific source file                                       │
│ SELECT * FROM staging.tbl_adhd_prevalence                                    │
│ WHERE _source_file LIKE '%nov25%';                                          │
│                                                                              │
│ -- Analyze load patterns                                                     │
│ SELECT DATE(_loaded_at), COUNT(*) FROM staging.tbl_adhd_prevalence          │
│ GROUP BY 1 ORDER BY 1;                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Schema Evolution

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Schema Evolution Flow                               │
└─────────────────────────────────────────────────────────────────────────────┘

Load 1 (August 2025):                     Load 2 (November 2025):
File has columns:                         File has columns:
┌───────────────────────┐                 ┌───────────────────────┐
│ age_band              │                 │ age_band              │
│ prevalence_rate       │                 │ prevalence_rate       │
│ patient_count         │                 │ patient_count         │
│                       │                 │ regional_breakdown    │  ← NEW!
└───────────────────────┘                 └───────────────────────┘
         │                                         │
         ▼                                         ▼
    CREATE TABLE                              Drift Detection
    staging.tbl_adhd_prev (                   ┌─────────────────────────────┐
      age_band VARCHAR,                       │ Expected: age_band,         │
      prevalence_rate NUMERIC,                │           prevalence_rate,  │
      patient_count INTEGER,                  │           patient_count     │
      _load_id INTEGER,                       │                             │
      ...                                     │ Found: + regional_breakdown │
    )                                         │                             │
                                              │ Action: ALTER TABLE ADD     │
                                              └─────────────────────────────┘
                                                       │
                                                       ▼
                                              ALTER TABLE staging.tbl_adhd_prev
                                              ADD COLUMN regional_breakdown VARCHAR;


Missing Column Handling:
┌─────────────────────────────────────────────────────────────────────────────┐
│ Load 3 (February 2026) - File missing regional_breakdown                     │
│                                                                              │
│ File has: age_band, prevalence_rate, patient_count                          │
│ Table has: age_band, prevalence_rate, patient_count, regional_breakdown     │
│                                                                              │
│ Action: INSERT with NULL for regional_breakdown                              │
│                                                                              │
│ INSERT INTO staging.tbl_adhd_prev (                                          │
│   age_band, prevalence_rate, patient_count, regional_breakdown, _load_id     │
│ ) VALUES (                                                                   │
│   'age_band_val', 4.2, 15000, NULL, 43                                       │
│ )                                                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Storage Statistics

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Current Database Stats                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ Component                  │ Count      │ Size                   │
├────────────────────────────┼────────────┼────────────────────────┤
│ Sources Registered         │ 182        │ ~16 KB (registry)      │
│ Staging Tables             │ 181        │ ~15 GB (data)          │
│ Total Rows                 │ 75.8M      │                        │
│ Load History Records       │ 555        │ ~1 KB                  │
│ Manifest File Records      │ 400+       │ ~1 KB                  │
├────────────────────────────┼────────────┼────────────────────────┤
│ Registry Overhead          │            │ 0.16%                  │
│ Data Storage               │            │ 99.84%                 │
└──────────────────────────────────────────────────────────────────┘

Top 5 Tables by Size:
┌────────────────────────────────────────┬──────────┬───────────────┐
│ Table                                  │ Rows     │ Size          │
├────────────────────────────────────────┼──────────┼───────────────┤
│ staging.tbl_gp_prac_reg_all           │ 8.5M     │ 1.2 GB        │
│ staging.tbl_networks_individual_level │ 6.2M     │ 890 MB        │
│ staging.tbl_pcn_wf_individual_level   │ 5.1M     │ 720 MB        │
│ staging.tbl_waiting_list_assessment   │ 4.8M     │ 680 MB        │
│ staging.tbl_gp_submissions_practice   │ 3.9M     │ 540 MB        │
└────────────────────────────────────────┴──────────┴───────────────┘
```

---

## Useful Queries

```sql
-- List all sources with their table sizes
SELECT
    s.code,
    s.table_name,
    pg_size_pretty(pg_total_relation_size('staging.' || s.table_name)) as size,
    s.row_count,
    s.last_load_at
FROM datawarp.tbl_data_sources s
ORDER BY pg_total_relation_size('staging.' || s.table_name) DESC;

-- Find orphaned sources (no table)
SELECT s.code, s.table_name
FROM datawarp.tbl_data_sources s
LEFT JOIN information_schema.tables t
  ON t.table_schema = 'staging' AND t.table_name = s.table_name
WHERE t.table_name IS NULL;

-- Recent load activity
SELECT
    s.code,
    h.rows_loaded,
    h.status,
    h.loaded_at
FROM datawarp.tbl_load_history h
JOIN datawarp.tbl_data_sources s ON h.source_id = s.id
ORDER BY h.loaded_at DESC
LIMIT 20;

-- Sources not loaded in 30 days
SELECT code, last_load_at
FROM datawarp.tbl_data_sources
WHERE last_load_at < NOW() - INTERVAL '30 days'
ORDER BY last_load_at;
```

---

*See DB_MANAGEMENT_FRAMEWORK.md for detailed database maintenance procedures.*
