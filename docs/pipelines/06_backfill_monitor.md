# Backfill & Monitor Pipeline

**Created:** 2026-01-11 UTC
**Purpose:** Automated processing of historical NHS data + monitoring for new releases

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Backfill & Monitor System                                │
└─────────────────────────────────────────────────────────────────────────────┘

YOU (One Time Setup)                      SYSTEM (Automated)
────────────────────                      ──────────────────

┌──────────────────────┐
│ Add publication URLs │
│ to publications.yaml │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ python backfill.py   │
└──────────┬───────────┘
           │
           │                    ┌─────────────────────────────────────────┐
           └───────────────────▶│ For each URL in publications.yaml:     │
                                │                                         │
                                │   if already_processed(pub, period):    │
                                │     skip ✓                              │
                                │   else:                                 │
                                │     1. url_to_manifest.py               │
                                │     2. enrich_manifest.py               │
                                │        (LLM first, reference after)     │
                                │     3. datawarp load-batch              │
                                │     4. export_to_parquet.py             │
                                │     5. Update state.json                │
                                │                                         │
                                └─────────────────────────────────────────┘
                                                  │
                                                  ▼
                                ┌─────────────────────────────────────────┐
                                │ state/state.json                        │
                                │ {                                       │
                                │   "adhd/aug25": {"completed": "..."},   │
                                │   "adhd/nov25": {"completed": "..."},   │
                                │   ...                                   │
                                │ }                                       │
                                └─────────────────────────────────────────┘
```

---

## File Structure

```
config/
└── publications.yaml       ← You maintain this (add new URLs)

state/
└── state.json              ← System maintains this (tracks progress)

scripts/
├── backfill.py             ← Main processing script
└── init_state.py           ← Initialize state from existing manifests

manifests/
└── backfill/               ← Generated manifests stored here
    ├── adhd/
    │   ├── adhd_aug25.yaml
    │   └── adhd_aug25_enriched.yaml
    └── pcn_workforce/
        └── ...
```

---

## Publications Config

```yaml
# config/publications.yaml

publications:
  adhd:
    name: "ADHD Management Information"
    frequency: monthly
    reference_manifest: manifests/production/adhd/adhd_aug25_enriched.yaml
    urls:
      - period: aug25
        url: https://digital.nhs.uk/.../august-2025
      - period: nov25
        url: https://digital.nhs.uk/.../november-2025
      # Add new periods here as they're published
      # - period: dec25
      #   url: https://digital.nhs.uk/.../december-2025
```

---

## State File Design (CRITICAL)

**Updated:** 2026-01-17 (Code Trace Audit - Issue #4 Root Cause)

**File:** `state/state.json`
**Purpose:** Track which publication/period combinations have been processed

### Design Intent (Code-Traced from scripts/backfill.py)

**State file tracks INCREMENTAL processing, NOT cumulative totals:**

| Field | Meaning | Example |
|-------|---------|---------|
| `rows_loaded` | Rows loaded in the MOST RECENT execution | `1304` (first load), `0` (re-run) |
| `completed_at` | Timestamp of last processing | `2026-01-17T12:00:00` |

**Source of Truth for Cumulative Totals:** `datawarp.tbl_manifest_files`, NOT `state.json`

### Structure

```json
{
  "processed": {
    "adhd/2025-05": {
      "completed_at": "2026-01-17T12:00:00",
      "rows_loaded": 1304  // Rows loaded in THIS execution
    },
    "gp_appointments/2024-01": {
      "completed_at": "2026-01-17T11:00:00",
      "rows_loaded": 15595054
    }
  },
  "failed": {
    "some_pub/2025-01": {
      "failed_at": "2026-01-17T11:00:00",
      "error": "404 Not Found"
    }
  }
}
```

### Behavior on Re-Run

```json
// BEFORE: First load of ADHD May 2025
"adhd/2025-05": {
  "completed_at": "2026-01-17T12:00:00",
  "rows_loaded": 1304  // 1,304 rows loaded
}

// AFTER: Re-run backfill (all files skipped, nothing new)
"adhd/2025-05": {
  "completed_at": "2026-01-17T14:00:00",  // Timestamp updated
  "rows_loaded": 0  // NO new rows loaded (all files already in database)
}
```

**Key Point:** `rows_loaded` shows what THIS execution did, not cumulative database total.

### Getting Cumulative Totals

**Use database, not state file:**

```sql
-- Total rows in database for ADHD
SELECT COALESCE(SUM(rows_loaded), 0) as total_rows
FROM datawarp.tbl_manifest_files
WHERE source_code LIKE '%adhd%' AND status = 'loaded';

-- Per-period totals for ADHD
SELECT
    period,
    COUNT(*) as sources,
    SUM(rows_loaded) as total_rows
FROM datawarp.tbl_manifest_files
WHERE source_code LIKE '%adhd%' AND status = 'loaded'
GROUP BY period
ORDER BY period;

-- All publications summary
SELECT
    LEFT(source_code, position('_' in source_code) - 1) as publication,
    COUNT(DISTINCT period) as periods_loaded,
    SUM(rows_loaded) as total_rows
FROM datawarp.tbl_manifest_files
WHERE status = 'loaded'
GROUP BY publication
ORDER BY total_rows DESC;
```

### Why This Matters

**Problem Scenario:**
- Load ADHD May 2025: 1,304 rows loaded → state shows `1304` ✅
- Re-run backfill: Files skipped → state shows `0` ✅
- **Don't sum state file values to get totals!** Use `tbl_manifest_files` instead

**Correct approach:**
```python
# WRONG: Sum state file values
total = sum(state["processed"][key]["rows_loaded"] for key in state["processed"])

# CORRECT: Query database
cursor.execute("SELECT SUM(rows_loaded) FROM datawarp.tbl_manifest_files WHERE status = 'loaded'")
total = cursor.fetchone()[0]
```

---

## Commands

```bash
# Check current status
python scripts/backfill.py --status

# ┌─────────────────────────────────────────────────────────────┐
# │ ADHD Management Information                                  │
# │   ████████████████████ 2/2 ✓                                │
# │                                                              │
# │ Online Consultation Systems                                  │
# │   ████████████████████ 9/9 ✓                                │
# │                                                              │
# │ Total: 12 URLs, 12 processed, 0 pending                     │
# └─────────────────────────────────────────────────────────────┘

# Process all pending URLs
python scripts/backfill.py

# Process one publication only
python scripts/backfill.py --pub adhd

# Dry run (see what would happen)
python scripts/backfill.py --dry-run

# Retry failed items
python scripts/backfill.py --retry-failed

# Re-initialize state from manifests
python scripts/init_state.py
```

---

## Processing Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Per-URL Processing                                   │
└─────────────────────────────────────────────────────────────────────────────┘

URL from publications.yaml
https://digital.nhs.uk/.../august-2025
         │
         │ Check state.json
         ▼
    ┌─────────────┐
    │ Already     │───YES───▶ Skip (print ✓)
    │ processed?  │
    └──────┬──────┘
           │ NO
           ▼
    ┌─────────────┐     url_to_manifest.py
    │  Generate   │     Downloads page, finds Excel
    │  Manifest   │     Extracts structure
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐     Is reference_manifest set?
    │   Enrich    │     YES → enrich --reference (no LLM cost)
    │  Manifest   │     NO  → enrich with LLM (first period)
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐     datawarp load-batch
    │    Load     │     Schema evolution
    │  Database   │     Validation
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐     export_to_parquet.py
    │   Export    │     Parquet + metadata
    │  Parquet    │     Update catalog
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │   Update    │     Mark as completed in state.json
    │   State     │
    └─────────────┘
```

---

## Cron Setup (Monitoring)

```bash
# Add to crontab: crontab -e

# Daily check at 9am - processes any new URLs you've added
0 9 * * * cd /path/to/datawarp-v2.1 && .venv/bin/python scripts/backfill.py >> logs/backfill.log 2>&1

# Weekly status report
0 10 * * 1 cd /path/to/datawarp-v2.1 && .venv/bin/python scripts/backfill.py --status | mail -s "DataWarp Weekly" you@email.com
```

---

## Future Enhancement: Auto URL Detection

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              Future: Automatic URL Discovery (Not Implemented)               │
└─────────────────────────────────────────────────────────────────────────────┘

Current: You manually add URLs to publications.yaml
Future:  System crawls NHS landing pages to find new releases

    ┌──────────────────┐
    │ Landing Page     │  https://digital.nhs.uk/.../mi-adhd
    │ Crawler          │
    └────────┬─────────┘
             │ Scrapes page, finds new periods
             ▼
    ┌──────────────────┐
    │ Auto-add to      │  Detected: December 2025
    │ publications.yaml│  → Add URL automatically
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ Trigger          │  Run backfill.py
    │ Processing       │
    └──────────────────┘

Status: In Ideas backlog (see IMPLEMENTATION_TASKS.md)
Reason: NHS pages are inconsistent, manual curation is more reliable for now
```

---

## Related Files

- `config/publications.yaml` - Publication registry
- `scripts/backfill.py` - Main processing script
- `scripts/init_state.py` - State initialization
- `state/state.json` - Processing state
- `docs/TASKS.md` - Current work tracking

---

*For full pipeline context, see 01_e2e_data_pipeline.md*
