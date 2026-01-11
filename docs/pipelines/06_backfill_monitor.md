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
