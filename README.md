# DataWarp v2.1

**Deterministic NHS Data Ingestion Engine**

Transform NHS Excel publications into queryable data - automatically.

```
NHS Website → Excel/CSV → PostgreSQL → Parquet → Your Queries
     ↓            ↓            ↓           ↓
  Landing     Download     Schema      Fast
   Pages      & Parse     Evolution   Analytics
```

---

## What It Does

DataWarp monitors NHS statistical publications, downloads new releases, extracts data from messy Excel files, and loads it into PostgreSQL with automatic schema evolution. Data is then exported to Parquet for fast querying.

**Key Features:**
- 📅 **Schedule-based discovery** - Automatically finds new periods
- 🔄 **Schema evolution** - Handles column changes across periods
- 🏷️ **Semantic enrichment** - LLM adds meaningful column names
- 📊 **Parquet export** - Fast analytical queries
- 🔍 **Provenance tracking** - Every row traced to source

---

## Quick Start

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e .
python scripts/reset_db.py

# Load ADHD data
python scripts/backfill.py --pub adhd

# Check what loaded
datawarp list
```

**Result:** 3 periods, 41 sources, 18,508 rows loaded.

---

## Configuration

### Schedule-Based (Recommended)

```yaml
# config/publications_v2.yaml
publications:
  adhd:
    name: "ADHD Management Information"
    frequency: quarterly
    landing_page: https://digital.nhs.uk/.../mi-adhd

    periods:
      mode: schedule
      start: "2025-05"
      end: current              # Auto-discover new periods
      months: [5, 8, 11]        # Quarterly: May, Aug, Nov
      publication_lag_weeks: 6

    url:
      mode: template
      pattern: "{landing_page}/{month_name}-{year}"
```

### Explicit URLs (For Hash Codes)

```yaml
  ae_waiting_times:
    name: "A&E Waiting Times"
    periods:
      mode: manual
    urls:
      - period: "2025-12"
        url: https://...December-2025-AE-by-provider-Sa9Xc.xls
```

---

## Documentation

| Document | Description |
|----------|-------------|
| **[User Guide](docs/USERGUIDE.md)** | Complete usage guide with examples |
| **[CLAUDE.md](CLAUDE.md)** | Technical reference for AI agents |
| **[docs/README.md](docs/README.md)** | Documentation navigation |

---

## Commands

```bash
# Load all publications
python scripts/backfill.py

# Load one publication
python scripts/backfill.py --pub adhd

# Use new config format
python scripts/backfill.py --config config/publications_v2.yaml

# Check status
python scripts/backfill.py --status

# Retry failures
python scripts/backfill.py --retry-failed
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         DataWarp                             │
├──────────────┬──────────────┬───────────────┬───────────────┤
│   Discovery  │   Extract    │     Load      │    Export     │
├──────────────┼──────────────┼───────────────┼───────────────┤
│ publications │ url_to_      │ loader/       │ export_to_    │
│ .yaml        │ manifest.py  │ pipeline.py   │ parquet.py    │
│              │              │               │               │
│ URL resolver │ Extractor    │ DDL generator │ Parquet       │
│ Period gen   │ Sheet detect │ Insert batch  │ writer        │
└──────────────┴──────────────┴───────────────┴───────────────┘
        ↓              ↓              ↓              ↓
   Auto-generate   Parse Excel   PostgreSQL    output/*.parquet
   periods         multi-sheet   staging.*
```

---

## Project Structure

```
datawarp-v2.1/
├── config/
│   ├── publications.yaml      # Old format (explicit URLs)
│   └── publications_v2.yaml   # New format (schedule-based)
├── src/datawarp/
│   ├── core/extractor.py      # Excel parsing
│   ├── loader/pipeline.py     # Database loading
│   └── utils/url_resolver.py  # Period & URL generation
├── scripts/
│   ├── backfill.py            # Main entry point
│   └── reset_db.py            # Database reset
├── output/                    # Parquet exports
├── state/                     # Processing state
├── logs/                      # Detailed logs
└── docs/
    ├── USERGUIDE.md           # User guide
    └── README.md              # Doc navigation
```

---

## Requirements

- Python 3.10+
- PostgreSQL 14+
- Google Gemini API key (for LLM enrichment)

---

## License

MIT

---

*Built for NHS data. Zero LLM in core pipeline.*
