# File Lifecycle Pipeline

**Created:** 2026-01-11 UTC
**Purpose:** Visualize file states, transitions, and cleanup workflows

---

## File State Machine

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         File Lifecycle States                                │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌──────────────┐
                              │   EXTERNAL   │
                              │  (NHS URL)   │
                              └──────┬───────┘
                                     │ download
                                     ▼
                              ┌──────────────┐
                              │  DOWNLOADED  │ ← Currently lost to /tmp/
                              │  (Excel/ODS) │   Future: downloads/{hash}/
                              └──────┬───────┘
                                     │ url_to_manifest.py
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   ┌──────────────┐        ┌──────────────┐        ┌──────────────┐          │
│   │    DRAFT     │───────▶│   ENRICHED   │───────▶│  CANONICAL   │          │
│   │  (manifest)  │ enrich │  (manifest)  │ apply  │  (manifest)  │          │
│   └──────────────┘        └──────────────┘        └──────┬───────┘          │
│                                                          │                   │
│                           manifests/                     │                   │
│                                                          │ load-batch        │
└──────────────────────────────────────────────────────────┼───────────────────┘
                                                           │
                                                           ▼
                              ┌──────────────┐
                              │    LOADED    │
                              │ (PostgreSQL) │ staging.tbl_*
                              └──────┬───────┘
                                     │ export_to_parquet.py
                                     ▼
                              ┌──────────────┐
                              │   EXPORTED   │
                              │  (Parquet)   │ output/*.parquet
                              └──────┬───────┘
                                     │ (future: cloud sync)
                                     ▼
                              ┌──────────────┐
                              │   ARCHIVED   │
                              │  (Cloud R2)  │ ← Future state
                              └──────────────┘
```

---

## Directory Structure (Current vs Proposed)

```
CURRENT (Flat, No Versioning)          PROPOSED (Organized, Versioned)
================================       ================================

manifests/                             manifests/
├── adhd_aug25.yaml                    ├── active/           ← Ready to load
├── adhd_aug25_enriched.yaml           │   └── adhd/
├── adhd_nov25.yaml                    │       └── adhd_nov25_canonical.yaml
├── pcn_workforce_may25.yaml           │
├── ...                                ├── pending/          ← Being enriched
│                                      │   └── adhd/
│ (100+ files, mixed states)           │       └── adhd_feb26_enriched.yaml
│                                      │
                                       ├── archive/          ← Already loaded
                                       │   └── adhd/
                                       │       ├── adhd_aug25_canonical.yaml
                                       │       └── adhd_nov25_canonical.yaml
                                       │
                                       └── reference/        ← First-period templates
                                           └── adhd_aug25_enriched.yaml


output/                                output/
├── adhd_diagnosis_to_medication.md    ├── parquet/          ← Data files
├── adhd_diagnosis_to_medication.parquet│   ├── adhd_*.parquet
├── catalog.parquet                    │   └── ...
├── ...                                │
│ (350+ files)                         ├── metadata/         ← .md files
                                       │   ├── adhd_*.md
                                       │   └── ...
                                       │
                                       └── catalog.parquet   ← Discovery index
```

---

## Cleanup Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Orphan Detection & Cleanup                           │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────┐
                    │   python cleanup_orphans.py │
                    └──────────────┬──────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
    ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
    │   Database      │  │   File System   │  │   Registry      │
    │   Orphans       │  │   Orphans       │  │   Orphans       │
    └────────┬────────┘  └────────┬────────┘  └────────┬────────┘
             │                    │                    │
             ▼                    ▼                    ▼
    ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
    │ • Sources with  │  │ • Parquet with  │  │ • Load history  │
    │   no tables     │  │   no source     │  │   for deleted   │
    │ • Staging with  │  │ • .md with no   │  │   sources       │
    │   no registry   │  │   parquet       │  │ • Manifest_files│
    └────────┬────────┘  └────────┬────────┘  │   for deleted   │
             │                    │           └────────┬────────┘
             │                    │                    │
             ▼                    ▼                    ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                      DRY RUN REPORT                          │
    │  Sources without tables: 2                                   │
    │  Parquet file orphans: 3                                     │
    │  Load history orphans: 9                                     │
    │  Total: 14 orphans                                           │
    └─────────────────────────────────────────────────────────────┘
                                   │
                                   │ --execute
                                   ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                      CLEANUP ACTIONS                         │
    │  DELETE FROM tbl_data_sources WHERE id IN (...)              │
    │  DELETE FROM tbl_load_history WHERE source_id NOT IN (...)   │
    │  rm output/orphan_*.parquet                                  │
    └─────────────────────────────────────────────────────────────┘
```

---

## Cascade Delete Flow (Future)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CASCADE DELETE Foreign Keys                               │
└─────────────────────────────────────────────────────────────────────────────┘

When: DELETE FROM tbl_data_sources WHERE code = 'adhd_summary'

Before CASCADE (Manual Cleanup Required):
─────────────────────────────────────────
    tbl_data_sources          tbl_load_history         staging.tbl_*
    ┌───────────────┐         ┌───────────────┐        ┌──────────────┐
    │ id: 42        │◄────────│ source_id: 42 │        │ (orphaned)   │
    │ code: adhd_*  │         │ rows: 50000   │        │              │
    └───────────────┘         └───────────────┘        └──────────────┘
          │ DELETE                  ❌ FK violation!
          ▼
    Error: violates foreign key constraint

After CASCADE (Automatic Cleanup):
──────────────────────────────────
    tbl_data_sources          tbl_load_history         staging.tbl_*
    ┌───────────────┐         ┌───────────────┐        ┌──────────────┐
    │ id: 42        │◄────────│ source_id: 42 │        │ DROP TABLE   │
    │ code: adhd_*  │  CASCADE│ rows: 50000   │        │ (trigger)    │
    └───────────────┘  DELETE └───────────────┘        └──────────────┘
          │ DELETE                  ✓ Auto-deleted
          ▼
    Success: source and all related records removed
```

---

## Cloud Archive Flow (Future)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Cloudflare R2 Archive Pipeline                           │
└─────────────────────────────────────────────────────────────────────────────┘

                    Local                          Cloud (R2)
    ┌───────────────────────────────┐    ┌───────────────────────────────┐
    │                               │    │                               │
    │  output/                      │    │  datawarp-archive/            │
    │  ├── adhd_*.parquet (10MB)    │───▶│  ├── 2026-01/                 │
    │  └── catalog.parquet          │    │  │   ├── adhd_*.parquet       │
    │                               │sync│  │   └── manifest.json        │
    │  manifests/archive/           │───▶│  ├── 2026-02/                 │
    │  └── adhd_aug25_canonical.yaml│    │  │   └── ...                  │
    │                               │    │  └── catalog/                 │
    │                               │    │      └── catalog_20260111.parquet
    └───────────────────────────────┘    └───────────────────────────────┘
                    │                                    │
                    │ Retention Policy                   │
                    ▼                                    ▼
    ┌───────────────────────────────┐    ┌───────────────────────────────┐
    │ Local: Keep last 3 months    │    │ Cloud: Keep forever           │
    │ Delete older parquet files   │    │ Lifecycle: Move to IA after   │
    │ Keep manifests indefinitely  │    │ 90 days for cost savings      │
    └───────────────────────────────┘    └───────────────────────────────┘

    Commands:
    $ python scripts/archive_to_r2.py --older-than 90d
    $ python scripts/restore_from_r2.py --source adhd_summary --period aug25
```

---

## Download Cache Flow (Future)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Download Caching Pipeline                            │
└─────────────────────────────────────────────────────────────────────────────┘

    NHS URL
    https://files.digital.nhs.uk/.../adhd-data-nov25.xlsx
         │
         │ First download
         ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │ downloads/                                                               │
    │ ├── index.json                    ← URL → hash mapping                   │
    │ │   {                                                                    │
    │ │     "https://...adhd-nov25.xlsx": {                                    │
    │ │       "hash": "abc123",                                                │
    │ │       "downloaded_at": "2026-01-11T10:30:00Z",                         │
    │ │       "size_bytes": 1048576,                                           │
    │ │       "etag": "W/\"abc123\""                                           │
    │ │     }                                                                  │
    │ │   }                                                                    │
    │ │                                                                        │
    │ └── abc123/                       ← Content-addressed storage            │
    │     ├── original.xlsx             ← Original file                        │
    │     └── metadata.json             ← Download metadata                    │
    └─────────────────────────────────────────────────────────────────────────┘
         │
         │ url_to_manifest.py (re-run)
         ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │ Check: Is URL in index.json?                                             │
    │   YES → Check ETag with HEAD request                                     │
    │         ETag matches? → Use cached file (0 download time)                │
    │         ETag differs? → Re-download, update cache                        │
    │   NO  → Download, add to cache                                           │
    └─────────────────────────────────────────────────────────────────────────┘
```

---

## Related Commands

```bash
# Check for orphans (dry run)
python scripts/cleanup_orphans.py

# Execute cleanup
python scripts/cleanup_orphans.py --execute

# Verbose output
python scripts/cleanup_orphans.py --verbose

# Skip certain cleanup types
python scripts/cleanup_orphans.py --skip-parquet --skip-tables
```

---

*See FILE_LIFECYCLE_ASSESSMENT.md for detailed gap analysis and implementation priorities.*
