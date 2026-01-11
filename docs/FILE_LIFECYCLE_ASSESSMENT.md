# File Lifecycle & Data Management Assessment

**Created:** 2026-01-11 UTC
**Purpose:** Deep dive into file organization, versioning, and lifecycle management gaps

---

## Executive Summary

Your DataWarp system has grown organically to **486 files** across manifests and output, with **no clear lifecycle management**. Key problems:

1. **No versioning** - Re-running URL extraction overwrites without backup
2. **No cleanup workflow** - Can't easily "refresh" a source (delete old data, reload new)
3. **Orphaned data accumulates** - Database tables and audit records aren't cleaned up
4. **No external storage strategy** - All data on local laptop
5. **Manifest sprawl** - 121 manifest files with unclear state (draft? enriched? archived?)

---

## 1. Current State Analysis

### File Inventory

| Location | File Count | Size | Purpose |
|----------|------------|------|---------|
| `manifests/` | 121 files | ~5 MB | YAML configurations |
| `output/` | 365 files | ~30 MB | Parquet + metadata |
| `/tmp/` | Ephemeral | Variable | Downloaded NHS files |
| PostgreSQL | 161 tables | 10.2 GB | Loaded data |

### Manifest Organization (Current)

```
manifests/
├── production/           # 3 subdirs, ~15 files
│   ├── adhd/
│   ├── gp_appointments/
│   └── pcn_workforce/
├── e2e_test/            # 3 subdirs, ~20 files
│   ├── gp_practice/
│   ├── adhd/
│   └── online_consultation/
├── test/                # 10+ subdirs, ~50 files
│   ├── fiscal/
│   ├── adhd_temporal/
│   └── examples/
└── archive/             # 1 subdir, ~36 files
    └── 2026-01-08/      # Only one archive date
```

**Problem:** No clear lifecycle states. Is `test/adhd_aug25.yaml` a test or deprecated production?

### Output Organization (Current)

```
output/
├── catalog.parquet      # Master index (rebuilt on demand)
├── *.parquet            # 182 data files (no versioning)
└── *.md                 # 182 metadata files (no versioning)
```

**Problem:** Parquet files overwritten on re-export. No way to compare versions.

---

## 2. Critical Gaps

### Gap 1: No Re-extraction Workflow

**Current Behavior:**
```bash
# If you re-run extraction for an existing source:
python scripts/url_to_manifest.py <same_url> manifests/production/adhd/adhd_aug25.yaml

# What happens:
# 1. Old YAML overwritten (no backup)
# 2. Old database data remains (not deleted)
# 3. Old parquet files remain (not updated)
# 4. No audit trail of the change
```

**What Should Happen:**
```bash
datawarp refresh adhd_aug25 --url <url>
# 1. Backup existing manifest to archive/
# 2. Delete existing database rows (with audit log)
# 3. Re-extract from URL
# 4. Re-enrich if needed
# 5. Re-load to database
# 6. Re-export to parquet
# 7. Log the refresh event
```

### Gap 2: No Cascade Delete

**Current Schema:** No `ON DELETE CASCADE` on any foreign keys

```sql
-- Deleting a source leaves orphans:
DELETE FROM datawarp.tbl_data_sources WHERE code = 'adhd_aug25';
-- tbl_load_history still has records for this source
-- staging.tbl_adhd_aug25 still exists
-- output/adhd_aug25.parquet still exists
-- tbl_column_metadata still has records
```

**What Should Happen:**
```sql
DELETE FROM datawarp.tbl_data_sources WHERE code = 'adhd_aug25' CASCADE;
-- Auto-deletes: load_history, manifest_files, column_metadata
-- Auto-drops: staging.tbl_adhd_aug25
-- Auto-removes: output/adhd_aug25.parquet
```

### Gap 3: No File State Management

**Current:** Files have no state marker. Can't distinguish:
- Draft (just extracted, not enriched)
- Enriched (LLM processed, not loaded)
- Loaded (in database, not exported)
- Exported (parquet exists)
- Archived (no longer active)
- Deprecated (should be deleted)

**What Should Happen:** Clear state transitions with file naming or metadata:

```
State Flow:
  DRAFT → ENRICHED → LOADED → EXPORTED → [ARCHIVED | DEPRECATED]

File Naming Convention:
  adhd_aug25.yaml           # Draft
  adhd_aug25.enriched.yaml  # Enriched
  adhd_aug25.canonical.yaml # Loaded (canonical codes applied)

Or Metadata Header:
  manifest:
    state: exported
    last_loaded: 2026-01-10T22:30:00Z
    parquet_path: output/adhd_aug25.parquet
```

### Gap 4: No External Storage Strategy

**Current:** All data on local laptop
- `/tmp/` - Downloads (ephemeral)
- `./manifests/` - YAML (git-tracked, but not the right place for large archives)
- `./output/` - Parquet (30 MB now, will grow to GB)
- PostgreSQL - 10.2 GB (local container)

**What Should Happen:**

```
Local (Hot):
  - manifests/production/   # Active manifests only
  - output/                  # Current parquet exports
  - PostgreSQL               # Active data only (last N periods)

Cloud (Warm - Cloudflare R2 or similar):
  - manifests/archive/       # All archived manifests
  - parquet/historical/      # Old parquet exports
  - backups/                 # Database backups

Cold (Glacier or R2 Infrequent):
  - Raw NHS files (optional)
  - Very old audit logs
```

### Gap 5: No Download Retention

**Current:** Downloaded NHS files go to `/tmp/` and are cleaned by OS

**Problem:** If you need to re-process without re-downloading:
- File is gone
- Must re-download (slow, bandwidth)
- No verification that file is same (NHS might update)

**What Should Happen:**

```
downloads/
├── 2026-01/
│   ├── adhd_aug25_summary.xlsx       # Retained download
│   ├── adhd_aug25_summary.xlsx.sha256  # Hash for verification
│   └── adhd_aug25_summary.xlsx.meta    # Download timestamp, URL, size
├── 2026-02/
│   └── ...
```

---

## 3. Proposed File Organization

### 3.1 Directory Structure

```
datawarp-v2.1/
├── manifests/
│   ├── active/              # Currently active manifests (≤50 files)
│   │   ├── adhd_aug25.enriched.yaml
│   │   ├── adhd_nov25.canonical.yaml
│   │   └── pcn_workforce_nov25.enriched.yaml
│   ├── pending/             # Extracted but not enriched
│   │   └── gp_practice_dec25.yaml
│   └── .archive/            # Hidden, local archive (before cloud upload)
│       └── 2026-01-10/
│           └── adhd_aug25.deprecated.yaml
│
├── downloads/               # NEW: Retained downloads
│   ├── .index.json          # Download catalog
│   └── 2026-01/
│       ├── adhd_aug25_summary.xlsx
│       └── adhd_aug25_summary.xlsx.meta
│
├── output/
│   ├── current/             # NEW: Active parquet exports
│   │   ├── catalog.parquet
│   │   ├── adhd_aug25.parquet
│   │   └── adhd_aug25.md
│   └── .versions/           # NEW: Version history (optional)
│       └── adhd_aug25/
│           ├── 2026-01-08.parquet
│           └── 2026-01-10.parquet
│
├── archive/                 # NEW: Centralized archive root
│   ├── manifests/           # Archived manifests
│   ├── parquet/             # Archived parquet files
│   └── downloads/           # Archived raw files
│
└── .sync/                   # NEW: Cloud sync staging
    ├── pending_upload/      # Files waiting for cloud upload
    └── sync_state.json      # Last sync timestamp
```

### 3.2 Manifest Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                     MANIFEST LIFECYCLE                          │
└─────────────────────────────────────────────────────────────────┘

┌──────────┐    url_to_manifest    ┌──────────┐
│   URL    │ ──────────────────────▶│  DRAFT   │
└──────────┘                        └────┬─────┘
                                         │ enrich_manifest.py
                                         ▼
                                    ┌──────────┐
                                    │ ENRICHED │
                                    └────┬─────┘
                                         │ load-batch
                                         ▼
                                    ┌──────────┐
                                    │  LOADED  │
                                    └────┬─────┘
                                         │ export_to_parquet.py
                                         ▼
                                    ┌──────────┐
                                    │ EXPORTED │
                                    └────┬─────┘
                                         │
              ┌──────────────────────────┼──────────────────────────┐
              ▼                          ▼                          ▼
         ┌─────────┐              ┌────────────┐              ┌──────────┐
         │ REFRESH │              │  ARCHIVED  │              │DEPRECATED│
         └─────────┘              └────────────┘              └──────────┘
              │                          │                          │
              │ Re-extract               │ Move to cloud            │ Delete
              └──────────────────────────┴──────────────────────────┘
```

### 3.3 File Naming Convention

```
{publication}_{period}[.{state}].yaml

Examples:
  adhd_aug25.yaml              # Draft (just extracted)
  adhd_aug25.enriched.yaml     # LLM enriched
  adhd_aug25.canonical.yaml    # Canonical codes (via --reference)
  adhd_aug25.deprecated.yaml   # Marked for deletion

State suffixes:
  (none)      = draft
  .enriched   = LLM processed
  .canonical  = reference-matched
  .deprecated = scheduled for cleanup
```

---

## 4. Proposed Cleanup Workflows

### 4.1 Refresh Source Command

```bash
# Refresh a source (re-extract, re-enrich, re-load)
datawarp refresh adhd_aug25 \
  --url https://digital.nhs.uk/... \
  --archive   # Move old files to archive (default: delete)

# What happens:
# 1. Archive existing manifest: manifests/active/adhd_aug25.* → archive/manifests/2026-01-11/
# 2. Archive existing parquet: output/current/adhd_aug25.* → archive/parquet/2026-01-11/
# 3. Delete database rows: DELETE FROM staging.tbl_adhd_aug25 WHERE _period = '2025-08'
# 4. Log refresh event: INSERT INTO tbl_refresh_events (...)
# 5. Re-extract: python scripts/url_to_manifest.py
# 6. Re-enrich: python scripts/enrich_manifest.py (if --enrich flag)
# 7. Re-load: datawarp load-batch
# 8. Re-export: python scripts/export_to_parquet.py
```

### 4.2 Cleanup Orphans Command

```bash
# Find and optionally clean orphaned records
datawarp cleanup --dry-run

# Output:
# Orphaned load_history records: 15 (sources deleted)
# Orphaned manifest_files records: 8 (manifests deleted)
# Orphaned staging tables: 3 (sources unregistered)
# Orphaned parquet files: 5 (sources deleted)

datawarp cleanup --execute
# Actually performs cleanup
```

### 4.3 Archive Old Data Command

```bash
# Archive data older than N days
datawarp archive --older-than 90d

# What happens:
# 1. Find manifests not loaded in 90 days
# 2. Move to archive/manifests/
# 3. Find parquet files for those sources
# 4. Move to archive/parquet/
# 5. Optionally delete database rows (--purge-db)
# 6. Update catalog.parquet
```

### 4.4 Sync to Cloud Command

```bash
# Sync archive to Cloudflare R2
datawarp sync --to r2://nhs-data-archive

# What happens:
# 1. Upload archive/* to R2
# 2. Verify checksums
# 3. Optionally delete local copies (--delete-local)
# 4. Update .sync/sync_state.json
```

---

## 5. Database Cleanup Schema

### 5.1 Add Cascade Deletes

```sql
-- Add CASCADE to existing foreign keys
ALTER TABLE datawarp.tbl_load_history
  DROP CONSTRAINT IF EXISTS fk_load_history_source,
  ADD CONSTRAINT fk_load_history_source
    FOREIGN KEY (source_id) REFERENCES datawarp.tbl_data_sources(id)
    ON DELETE CASCADE;

ALTER TABLE datawarp.tbl_source_mappings
  DROP CONSTRAINT IF EXISTS fk_source_mappings_canonical,
  ADD CONSTRAINT fk_source_mappings_canonical
    FOREIGN KEY (canonical_code) REFERENCES datawarp.tbl_canonical_sources(canonical_code)
    ON DELETE CASCADE;

ALTER TABLE datawarp.tbl_column_metadata
  DROP CONSTRAINT IF EXISTS fk_column_metadata_source,
  ADD CONSTRAINT fk_column_metadata_source
    FOREIGN KEY (canonical_source_code) REFERENCES datawarp.tbl_canonical_sources(canonical_code)
    ON DELETE CASCADE;
```

### 5.2 Add Refresh Events Table

```sql
CREATE TABLE datawarp.tbl_refresh_events (
  id SERIAL PRIMARY KEY,
  source_code VARCHAR(100) NOT NULL,
  refresh_type VARCHAR(20) NOT NULL,  -- full, partial, metadata_only
  old_row_count INTEGER,
  new_row_count INTEGER,
  rows_deleted INTEGER,
  rows_added INTEGER,
  old_manifest_path TEXT,
  new_manifest_path TEXT,
  archived_to TEXT,                     -- Archive path (local or cloud)
  initiated_by VARCHAR(50),             -- user or automation
  initiated_at TIMESTAMP DEFAULT NOW(),
  completed_at TIMESTAMP,
  status VARCHAR(20) DEFAULT 'in_progress',  -- in_progress, success, failed
  error_message TEXT
);
```

### 5.3 Add Retention Policy Table

```sql
CREATE TABLE datawarp.tbl_retention_policy (
  id SERIAL PRIMARY KEY,
  source_pattern VARCHAR(100),          -- regex pattern (e.g., 'adhd_*')
  retain_periods INTEGER DEFAULT 12,    -- Keep last N periods
  retain_days INTEGER DEFAULT 365,      -- Or keep for N days
  archive_to TEXT,                      -- Where to archive (local or cloud)
  delete_after_archive BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW(),
  enabled BOOLEAN DEFAULT TRUE
);
```

---

## 6. Download Retention Design

### 6.1 Download Index Schema

```json
// downloads/.index.json
{
  "version": "1.0",
  "downloads": {
    "https://files.digital.nhs.uk/.../adhd_aug25.xlsx": {
      "local_path": "2026-01/adhd_aug25_summary.xlsx",
      "sha256": "abc123...",
      "size_bytes": 1234567,
      "downloaded_at": "2026-01-10T14:30:00Z",
      "source_code": "adhd_aug25",
      "last_used": "2026-01-10T15:00:00Z"
    }
  }
}
```

### 6.2 Download Cache Logic

```python
def download_file(url: str, cache_dir: Path = Path("downloads")) -> Path:
    """Download file with caching and verification."""
    index = load_index(cache_dir / ".index.json")

    if url in index["downloads"]:
        entry = index["downloads"][url]
        local_path = cache_dir / entry["local_path"]

        if local_path.exists():
            # Verify hash
            if verify_hash(local_path, entry["sha256"]):
                entry["last_used"] = datetime.utcnow().isoformat()
                save_index(index)
                return local_path
            else:
                logger.warning(f"Hash mismatch, re-downloading: {url}")

    # Download fresh
    month_dir = cache_dir / datetime.now().strftime("%Y-%m")
    month_dir.mkdir(parents=True, exist_ok=True)

    filename = url.split("/")[-1]
    local_path = month_dir / filename

    # Download
    response = requests.get(url)
    local_path.write_bytes(response.content)

    # Compute hash
    sha256 = compute_sha256(local_path)

    # Update index
    index["downloads"][url] = {
        "local_path": str(local_path.relative_to(cache_dir)),
        "sha256": sha256,
        "size_bytes": local_path.stat().st_size,
        "downloaded_at": datetime.utcnow().isoformat(),
        "last_used": datetime.utcnow().isoformat()
    }
    save_index(index)

    return local_path
```

---

## 7. Cloud Storage Design

### 7.1 Cloudflare R2 Structure

```
r2://nhs-data-archive/
├── manifests/
│   └── YYYY-MM-DD/
│       ├── adhd_aug25.enriched.yaml
│       └── adhd_aug25.enriched.yaml.meta
├── parquet/
│   └── YYYY-MM-DD/
│       ├── adhd_aug25.parquet
│       └── adhd_aug25.parquet.meta
├── downloads/
│   └── YYYY-MM/
│       ├── adhd_aug25_summary.xlsx
│       └── adhd_aug25_summary.xlsx.meta
└── backups/
    └── postgres/
        └── YYYY-MM-DD/
            └── datawarp_backup.sql.gz
```

### 7.2 Sync Configuration

```yaml
# .datawarp/sync.yaml
cloud:
  provider: cloudflare_r2
  bucket: nhs-data-archive
  endpoint: https://xxx.r2.cloudflarestorage.com
  access_key_id: ${R2_ACCESS_KEY_ID}
  secret_access_key: ${R2_SECRET_ACCESS_KEY}

sync:
  # What to sync
  include:
    - archive/manifests/**
    - archive/parquet/**
    - archive/downloads/**

  # When to sync
  auto_sync: false  # Manual only for now

  # After sync
  delete_local_after_sync: false  # Keep local copies

  # Retention in cloud
  cloud_retention_days: 365
```

---

## 8. Implementation Priority

### Phase 1: Foundation (This Week)

1. **Create `datawarp cleanup --dry-run`** - Find orphans
2. **Add download caching** - Stop using /tmp/
3. **Reorganize manifests** - active/pending/archive structure
4. **Add CASCADE DELETE** - Prevent future orphans

### Phase 2: Automation (Next Week)

1. **Create `datawarp refresh`** - Re-extract workflow
2. **Add manifest state tracking** - .enriched, .canonical suffixes
3. **Create `datawarp archive`** - Move old data
4. **Add retention policy table**

### Phase 3: Cloud (When Needed)

1. **Set up R2 bucket**
2. **Create `datawarp sync`** - Upload to cloud
3. **Add sync automation** - Weekly archive sync
4. **Database backup to R2**

---

## 9. Immediate Actions

### Action 1: Audit Current State

```bash
# Run this to see current orphan situation
psql -h localhost -U databot_dev_user -d databot_dev -c "
SELECT
  'Sources without tables' as issue,
  COUNT(*) as count
FROM datawarp.tbl_data_sources s
LEFT JOIN information_schema.tables t
  ON t.table_schema = s.schema_name AND t.table_name = s.table_name
WHERE t.table_name IS NULL

UNION ALL

SELECT
  'Load history without sources' as issue,
  COUNT(*)
FROM datawarp.tbl_load_history lh
LEFT JOIN datawarp.tbl_data_sources s ON lh.source_id = s.id
WHERE s.id IS NULL

UNION ALL

SELECT
  'Parquet files without sources' as issue,
  0  -- Would need filesystem check
"
```

### Action 2: Create Cleanup Script

```python
# scripts/cleanup_orphans.py - Create this
```

### Action 3: Restructure Manifests

```bash
# Move to new structure
mkdir -p manifests/active manifests/pending

# Move production manifests
mv manifests/production/*/*.yaml manifests/active/

# Move test manifests to pending (review needed)
mv manifests/test/*.yaml manifests/pending/

# Archive old ones
mv manifests/archive/* archive/manifests/
```

---

## 10. Summary

| Problem | Solution | Priority |
|---------|----------|----------|
| No versioning | File naming convention + .versions/ dir | HIGH |
| No cleanup workflow | `datawarp cleanup` command | HIGH |
| No cascade delete | Add FK constraints | HIGH |
| Downloads lost | Download caching in downloads/ | MEDIUM |
| Manifest sprawl | active/pending/archive structure | MEDIUM |
| No external storage | Cloudflare R2 integration | LOW |
| No retention policy | tbl_retention_policy table | LOW |

**Recommended Start:** Create cleanup script to find orphans, then add CASCADE DELETE to prevent future ones.

---

**Document Version:** 1.0
**Last Updated:** 2026-01-11 UTC
