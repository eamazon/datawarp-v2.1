# DataWarp User Guide

**The Simple Guide to NHS Data Ingestion**

*Last Updated: 2026-01-17*

---

## What is DataWarp?

DataWarp automatically downloads NHS statistics, extracts the data from Excel/CSV files, and loads it into a PostgreSQL database. It then exports to Parquet files for fast querying.

```
NHS Website → Excel Files → PostgreSQL → Parquet → Your Queries
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

## Understanding the Config File

DataWarp reads from `config/publications.yaml` (or `config/publications_v2.yaml` for the new format).

### Old Format (Explicit URLs)

```yaml
publications:
  adhd:
    name: "ADHD Management Information"
    frequency: quarterly
    landing_page: https://digital.nhs.uk/.../mi-adhd
    urls:
      - period: "2025-05"
        url: https://digital.nhs.uk/.../mi-adhd/may-2025
      - period: "2025-08"
        url: https://digital.nhs.uk/.../mi-adhd/august-2025
```

**Problem:** You must manually add each new period.

### New Format (Schedule-Based) ✨

```yaml
publications:
  adhd:
    name: "ADHD Management Information"
    frequency: quarterly
    landing_page: https://digital.nhs.uk/.../mi-adhd

    periods:
      mode: schedule
      start: "2025-05"           # First available period
      end: current               # Keep checking until today
      months: [5, 8, 11]         # Only May, Aug, Nov (quarterly)
      publication_lag_weeks: 6   # Don't try periods < 6 weeks old

    url:
      mode: template
      pattern: "{landing_page}/{month_name}-{year}"
```

**Benefit:** DataWarp automatically discovers new periods!

---

## Config Patterns (Copy & Paste)

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

SHMI publishes data 5 months after the data period ends.

```yaml
shmi:
  name: "Summary Hospital-level Mortality Indicator"
  frequency: quarterly
  landing_page: https://digital.nhs.uk/.../shmi

  periods:
    mode: schedule
    start: "2024-08"
    end: current
    publication_offset_months: 5  # Data Aug 2025 → Published Jan 2026

  url:
    mode: template
    pattern: "{landing_page}/{pub_year}-{pub_month}"
```

### Pattern E: Explicit URLs (NHS England with Hash Codes)

Some NHS England URLs have unpredictable hash codes. Use explicit mode:

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

## Understanding the Output

### What Gets Created

```
manifests/backfill/adhd/
├── adhd_2025-05.yaml           # Raw manifest (file structure)
├── adhd_2025-05_enriched.yaml  # LLM-enriched (semantic names)
└── adhd_2025-05_canonical.yaml # Final (date patterns removed)

output/
├── adhd.parquet                # Exported data
├── adhd_indicators.parquet
└── adhd_prevalence.parquet

state/
└── state.json                  # Tracks what's been processed
```

### Database Tables

All data goes into the `staging` schema:

```sql
-- List all tables
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'staging';

-- Query data
SELECT * FROM staging.tbl_adhd LIMIT 10;
```

### Provenance Columns

Every row has these tracking columns:

| Column | Description |
|--------|-------------|
| `_source_file` | Original filename |
| `_sheet_name` | Excel sheet name |
| `_loaded_at` | When loaded |
| `_period` | Data period (e.g., "2025-11") |
| `_period_start` | Period start date |
| `_period_end` | Period end date |

---

## Period Formats

DataWarp uses standardized period formats:

| Type | Format | Example |
|------|--------|---------|
| Monthly | `YYYY-MM` | `2025-11` |
| Fiscal Quarter | `FYyy-QN` | `FY25-Q1` |
| Fiscal Year | `FYyyyy-yy` | `FY2024-25` |

### NHS Fiscal Year

- Runs April to March
- FY25 = April 2024 to March 2025
- Q1 = Apr-Jun, Q2 = Jul-Sep, Q3 = Oct-Dec, Q4 = Jan-Mar

---

## Common Issues

### "404 Not Found"

```
ERROR: 404 Client Error: Not Found for url: ...
```

**Cause:** The period doesn't exist yet (or never will).

**Fix:**
- Check the start date in your config
- Increase `publication_lag_weeks`
- Verify the URL pattern is correct

### "Column mismatch"

```
WARNING: Column drift detected
```

**This is normal!** NHS often changes column names between periods. DataWarp automatically adds new columns.

### "Already processed"

```
Skipping adhd/2025-11 - already processed
```

**Cause:** This period is in `state/state.json`.

**Fix:** Use `--force` to reload, or delete the entry from state.json.

### "LLM enrichment failed"

```
ERROR: Enrichment failed
```

**Fix:**
1. Check your `GEMINI_API_KEY` in `.env`
2. Try `--no-reference` for fresh enrichment
3. Check logs in `logs/`

---

## File Locations

| Path | Purpose |
|------|---------|
| `config/publications.yaml` | Publication registry (old format) |
| `config/publications_v2.yaml` | Publication registry (new format) |
| `manifests/backfill/` | Generated manifests |
| `output/` | Parquet exports |
| `state/state.json` | Processing state |
| `logs/` | Detailed logs |
| `.env` | Environment variables |

---

## Environment Variables

Create a `.env` file:

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

---

## Tips & Tricks

### 1. Start Small

Test with one publication first:
```bash
python scripts/backfill.py --pub adhd --dry-run
```

### 2. Check Logs

Detailed logs are in `logs/backfill_YYYYMMDD_HHMMSS.log`

### 3. Use Quiet Mode

For cleaner output:
```bash
python scripts/backfill.py --pub adhd --quiet
```

### 4. Export to Parquet

Data is automatically exported after loading. To re-export:
```bash
python scripts/export_to_parquet.py --publication adhd output/
```

### 5. Query with DuckDB

Parquet files can be queried directly:
```python
import duckdb
duckdb.query("SELECT * FROM 'output/adhd.parquet' LIMIT 10").show()
```

---

## Getting Help

1. **Logs:** Check `logs/backfill_*.log`
2. **Status:** Run `python scripts/backfill.py --status`
3. **Database:** Run `datawarp list`
4. **Docs:** Read `CLAUDE.md` for technical details

---

## Glossary

| Term | Meaning |
|------|---------|
| **Publication** | An NHS data release (e.g., ADHD, A&E Waiting Times) |
| **Period** | A time slice of data (e.g., "2025-11" for November 2025) |
| **Landing Page** | NHS webpage listing all periods for a publication |
| **Manifest** | YAML file describing Excel structure |
| **Enrichment** | LLM adds semantic column names |
| **Canonicalization** | Removes date patterns from codes |
| **Parquet** | Columnar file format for fast queries |

---

## Quick Reference Card

```
┌────────────────────────────────────────────────────────────────┐
│                     DATAWARP QUICK REFERENCE                   │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  LOAD DATA                                                     │
│    python scripts/backfill.py --pub adhd                       │
│    python scripts/backfill.py --config config/publications_v2.yaml │
│                                                                │
│  CHECK STATUS                                                  │
│    python scripts/backfill.py --status                         │
│    datawarp list                                               │
│                                                                │
│  RETRY / FORCE                                                 │
│    python scripts/backfill.py --retry-failed                   │
│    python scripts/backfill.py --pub adhd --force               │
│                                                                │
│  CONFIG FORMAT                                                 │
│    periods.mode: schedule | manual                             │
│    url.mode: template | explicit                               │
│                                                                │
│  PERIOD FORMATS                                                │
│    Monthly: 2025-11                                            │
│    Quarter: FY25-Q1                                            │
│    Year: FY2024-25                                             │
│                                                                │
│  FILES                                                         │
│    Config:    config/publications_v2.yaml                      │
│    State:     state/state.json                                 │
│    Logs:      logs/backfill_*.log                              │
│    Output:    output/*.parquet                                 │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

*Happy data wrangling!*
