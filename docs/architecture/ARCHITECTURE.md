# DataWarp v2.1 Architecture

**Status:** Production
**Version:** 2.1.0
**Last Updated:** 2026-01-07

---

## System Overview

DataWarp is a deterministic NHS data ingestion engine that:
1. Automatically detects structure in NHS Excel/CSV files
2. Handles schema changes (drift) gracefully
3. Loads data into PostgreSQL with proper types
4. Consolidates sources across time periods (Phase 1)

**Key Principle:** Zero configuration required. Point at NHS URL, get structured data.

---

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                       NHS Publication                        │
│  https://digital.nhs.uk/.../mi-adhd/november-2025          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ url_to_manifest.py   │  Scrape page, download files
              │ (590 lines)          │  Detect sheets automatically
              └──────────┬───────────┘
                         │ Produces: raw.yaml
                         ▼
              ┌──────────────────────┐
              │ enrich.py            │  Route to Gemini or Qwen
              │ (100 lines)          │  Generate semantic codes
              └──────────┬───────────┘
                         │ Produces: enriched.yaml + llm_response.json
                         ▼
              ┌──────────────────────┐
              │ apply_enrichment.py  │  Merge LLM codes → YAML ← NEW!
              │ (50 lines)           │  Canonicalize source codes
              └──────────┬───────────┘
                         │ Produces: canonical.yaml
                         ▼
              ┌──────────────────────┐
              │ datawarp load-batch  │  Extract → Match → Load
              │ (pipeline.py)        │  PostgreSQL insert
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  PostgreSQL Database │
              │  staging.tbl_*       │  One table per canonical source
              └──────────────────────┘
```

---

## Core Modules

### Extraction Layer (Deterministic)

**extractor.py (871 lines)**
- Detects hierarchical headers (multi-tier: Year → Month → Metric)
- Handles merged cells in NHS Excel files
- Classifies sheets (TABULAR, METADATA, EMPTY)
- Infers column types from keywords + data sampling
- Finds data boundaries (footer detection)
- **Performance:** ~50ms per sheet with row caching

**drift.py (30 lines)**
- Compares old vs new column lists
- Detects: new columns, missing columns, type changes
- Simple set difference operations

### Registry Layer (Phase 1 - NEW)

**fingerprint.py (80 lines)**
- Generates structural fingerprints (MD5 hash of sorted column names)
- Jaccard similarity matching (intersection/union of column sets)
- Finds best canonical match across periods
- **Pure deterministic** - no LLM calls, no network requests

**Key Concept:**
```
November ADHD: columns = [Date, Provider, Count]
December ADHD: columns = [Count, Date, Provider]  # Reordered!

Fingerprint: MD5(sorted([Count, Date, Provider])) = "abc123..."
→ Same hash! These are the same source.
```

### Storage Layer

**connection.py**
- PostgreSQL connection pooling
- Environment-based configuration
- Retry logic for transient failures

**models.py**
- SQLAlchemy models (not ORM, just schema definitions)
- `tbl_data_sources`, `tbl_load_events`
- `tbl_canonical_sources`, `tbl_source_mappings` (Phase 1)

**repository.py**
- CRUD operations for registry tables
- Source registration
- Load event logging
- Fingerprint storage/retrieval

### Loader Layer

**pipeline.py (50 lines) - THE ORCHESTRATOR**
```python
def load_file(url: str, source_config: dict) -> LoadResult:
    # Download file
    # Extract structure
    # Generate fingerprint ← NEW
    # Match to canonical  ← NEW
    # Compare for drift
    # Evolve schema if needed
    # Insert data
    # Log event
    return LoadResult(...)
```

**ddl.py (150 lines)**
- `CREATE TABLE` generation from column metadata
- `ALTER TABLE ADD COLUMN` for drift handling
- Type mapping: ColumnInfo → PostgreSQL types
- Index creation

**insert.py (200 lines)**
- Batch INSERT with executemany (1000 rows/batch)
- Type casting (str/int/float/date/null)
- Handles replace/append modes
- Suppressed value handling (NHS uses *, -, ..)

---

## Database Schema

### Registry Schema (datawarp)

```sql
-- Source metadata
tbl_data_sources (
  source_code VARCHAR(100) PRIMARY KEY,
  source_name TEXT,
  table_name VARCHAR(100),
  created_at TIMESTAMP
)

-- Load history
tbl_load_events (
  id SERIAL PRIMARY KEY,
  source_code VARCHAR(100),
  load_timestamp TIMESTAMP,
  rows_loaded INTEGER,
  status VARCHAR(20)  -- 'success', 'failed'
)

-- Phase 1: Canonical sources
tbl_canonical_sources (
  canonical_code VARCHAR(100) PRIMARY KEY,
  fingerprint JSONB NOT NULL,
  first_seen_period VARCHAR(20),
  last_seen_period VARCHAR(20),
  total_loads INTEGER DEFAULT 0
)

-- Phase 1: Source mappings
tbl_source_mappings (
  llm_generated_code VARCHAR(100),
  canonical_code VARCHAR(100),
  match_confidence FLOAT,      -- 0.0 to 1.0 (Jaccard similarity)
  match_method VARCHAR(50),    -- 'exact', 'fingerprint', 'manual'
  period VARCHAR(20)
)

-- Phase 1: Drift tracking
tbl_drift_events (
  id SERIAL PRIMARY KEY,
  canonical_code VARCHAR(100),
  drift_type VARCHAR(50),      -- 'new_columns', 'missing_columns'
  severity VARCHAR(20),         -- 'info', 'warning', 'error'
  details JSONB,
  detected_at TIMESTAMP DEFAULT NOW()
)
```

### Data Schema (staging)

```sql
-- Dynamically created per canonical source
staging.tbl_{canonical_code} (
  -- Columns from NHS data (auto-detected)
  _datawarp_loaded_at TIMESTAMP DEFAULT NOW(),
  _datawarp_source_period VARCHAR(20)
)
```

**Example:**
```sql
-- Created from ADHD November manifest
CREATE TABLE staging.tbl_adhd_summary_waiting_assessment_age (
  provider_code VARCHAR(255),
  provider_name VARCHAR(255),
  age_group VARCHAR(255),
  patients_waiting INTEGER,
  _datawarp_loaded_at TIMESTAMP,
  _datawarp_source_period VARCHAR(20)
);
```

---

## LLM Enrichment (Optional)

### Gemini (External)

- **Speed:** 30-40 seconds per publication
- **Quality:** Excellent consolidation, semantic naming
- **Cost:** ~$0.05 per enrichment
- **Use case:** Production, fast turnaround

**Example transformation:**
```yaml
# Before (url_to_manifest.py)
code: summary_nov25_table_1

# After (Gemini)
code: adhd_summary_waiting_assessment_age  # ✓ No date! Semantic!
```

### Qwen v3 (Local)

- **Speed:** 3-5 minutes per publication
- **Quality:** Good with 8 generic improvements
- **Cost:** $0 (runs locally)
- **Use case:** Privacy-sensitive, offline deployments

**8 Generic Improvements:**
1. Column name cleaning
2. Type validation
3. Semantic naming
4. Header consolidation
5. Sheet filtering
6. Duplicate detection
7. Dimension/measure tagging
8. Wide date detection

---

## Data Flow Example

**Input:** ADHD November 2025 publication

```
1. url_to_manifest.py
   Input:  https://digital.nhs.uk/.../mi-adhd/november-2025
   Output: adhd_nov25_raw.yaml (30+ sources with codes like "summary_nov25_table_1")

2. enrich.py (Gemini)
   Input:  adhd_nov25_raw.yaml
   Output: adhd_nov25_enriched.yaml + adhd_nov25_llm_response.json
           Consolidated: 30+ → 20 sources
           Codes: "adhd_summary_waiting_assessment_age" (no dates!)

3. apply_enrichment.py ← NEW in v2.1!
   Input:  adhd_nov25_enriched.yaml + adhd_nov25_llm_response.json
   Output: adhd_nov25_canonical.yaml
           Action: Merges LLM codes back into YAML

4. datawarp load-batch
   Input:  adhd_nov25_canonical.yaml
   Action: For each source:
           - Extract (extractor.py) → 50ms
           - Fingerprint (fingerprint.py) → calculate MD5
           - Match (fingerprint.py) → Jaccard similarity > 0.80
           - Create/alter table (ddl.py)
           - Load data (insert.py) → 1000 rows/sec
   Output: 20 tables in staging.tbl_*

Result:
  staging.tbl_adhd_summary_waiting_assessment_age (November data)

When December arrives:
  Same table used! (fingerprint matches)
  Time-series queries work across periods.
```

---

## Performance Characteristics

| Operation | Performance | Notes |
|-----------|-------------|-------|
| Extraction | ~50ms/sheet | With row caching |
| LLM enrichment (Gemini) | 30-40s/publication | Network dependent |
| LLM enrichment (Qwen) | 3-5min/publication | CPU bound |
| Fingerprinting | <1ms/source | Pure computation |
| Loading | ~1000 rows/sec | PostgreSQL batch insert |
| Memory | <500MB | Typical NHS publication |

---

## Error Handling

- **Network errors:** Retry with exponential backoff (3 attempts)
- **Parse errors:** Log and skip problematic sheets
- **Type errors:** Cast to VARCHAR as fallback
- **Drift:** Auto-add columns, log event
- **LLM errors:** Fall back to base manifest without enrichment

---

## Next: Phase 2 (Monitoring)

See `docs/plans/current_phase.md` for:
- Publication registry (10 feeds)
- URL discovery automation
- Backfill workflow (3-5 years historical)
- Alert system (email on failures)

---

**END OF ARCHITECTURE.MD - Keep under 200 lines**
