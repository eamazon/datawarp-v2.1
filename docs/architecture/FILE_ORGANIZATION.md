# Production File Organization Strategy

**Created:** 2026-01-13
**Status:** PROPOSAL - Review before implementing

---

## The Problem

Current approach creates file explosion:
- 10 publications × 12 months × 4 manifest files = **480 files/year** (manifests alone)
- Plus parquet exports, logs, LLM responses
- No retention policy
- No clear "source of truth"

---

## Proposed Solution: Database-Centric with Minimal Files

### Core Principle

> **The database is the source of truth. Files are either inputs or regenerable outputs.**

### What to Keep vs Delete

| File Type | Keep? | Reason |
|-----------|-------|--------|
| Canonical manifests | ✅ YES | Audit trail - what was loaded |
| Draft manifests | ❌ NO | Regenerable from URL |
| Enriched manifests | ❌ NO | Regenerable (but costs LLM $) |
| LLM response JSON | ❌ NO | Debug only, delete after success |
| Parquet exports | ⚠️ OPTIONAL | Regenerable from DB |
| catalog.parquet | ✅ YES | MCP server needs it |
| Event logs (JSONL) | ✅ 7 days | Operational observability |
| state.json | ✅ YES | Idempotency tracking |

---

## Proposed Directory Structure

```
datawarp-v2.1/
├── config/
│   └── publications.yaml          # Publication definitions (checked in)
│
├── manifests/
│   └── canonical/                  # ONLY canonical manifests (checked in)
│       ├── adhd/
│       │   └── adhd_canonical.yaml # Single file per publication!
│       ├── online_consultation/
│       │   └── oc_canonical.yaml
│       └── pcn_workforce/
│           └── pcn_canonical.yaml
│
├── data/                           # ALL generated data (NOT in git)
│   ├── exports/                    # Parquet files
│   │   ├── catalog.parquet        # MCP catalog
│   │   └── [source].parquet       # Source exports (regenerable)
│   ├── logs/                       # Event logs
│   │   └── events/
│   │       └── 2026-01-13/        # Daily folders
│   │           └── *.jsonl
│   └── state/
│       └── state.json             # Processing state
│
└── tmp/                            # Temporary/working files (NOT in git)
    └── manifests/                  # Draft/enriched manifests
        └── [run_id]/              # Per-run working directory
            ├── draft.yaml
            ├── enriched.yaml
            └── llm_response.json
```

---

## Key Changes from Current

### 1. Single Canonical Manifest per Publication

**Current:** `adhd_aug25_canonical.yaml`, `adhd_sep25_canonical.yaml`, ...
**Proposed:** `adhd_canonical.yaml` (single file, updated each period)

Why? The canonical manifest defines the **schema**, not the data. Schema rarely changes. When it does, we update the single file.

### 2. Working Files in tmp/

All intermediate files go to `tmp/manifests/[run_id]/` and are deleted after successful load.

### 3. data/ Directory for Generated Content

Everything regenerable goes in `data/` which is gitignored:
- Parquet exports
- Event logs
- State tracking

### 4. Retention Policies

| Content | Retention | Archive Strategy |
|---------|-----------|------------------|
| Event logs | 7 days active | Monthly archive to `data/archive/logs/` |
| Parquet exports | Latest only | Regenerate from DB if needed |
| tmp/ files | Delete on success | None |
| Canonical manifests | Forever | Git history |

---

## Migration Plan

### Step 1: Create New Structure
```bash
mkdir -p manifests/canonical/{adhd,online_consultation,pcn_workforce}
mkdir -p data/{exports,logs,state}
mkdir -p tmp/manifests
```

### Step 2: Consolidate Canonical Manifests
For each publication, merge period-specific canonicals into single file:
```bash
# Example: Take latest canonical as the template
cp manifests/backfill/adhd/adhd_nov25_canonical.yaml manifests/canonical/adhd/adhd_canonical.yaml
```

### Step 3: Update .gitignore
```gitignore
# Generated data
data/
tmp/

# Keep canonical manifests
!manifests/canonical/
```

### Step 4: Update Scripts
- backfill.py: Use tmp/ for working files
- Export canonical to manifests/canonical/ after success
- Clean tmp/ after successful load

### Step 5: Update config/publications.yaml
```yaml
publications:
  adhd:
    name: "ADHD Management Information"
    canonical_manifest: manifests/canonical/adhd/adhd_canonical.yaml
    urls:
      - period: nov25
        url: https://...
```

---

## Cleanup Script

```bash
#!/bin/bash
# scripts/cleanup_data.sh

# Delete logs older than 7 days
find data/logs -type f -mtime +7 -delete

# Delete empty directories
find data/logs -type d -empty -delete

# Delete tmp working files
rm -rf tmp/manifests/*

# Report
echo "Cleanup complete"
du -sh data/
```

---

## Benefits

1. **Predictable growth:** ~10-20 canonical manifests total (not hundreds)
2. **Clear source of truth:** Database + canonical manifests
3. **Easy backup:** Just backup PostgreSQL + manifests/canonical/
4. **Clean git:** Only config and canonical manifests tracked
5. **Simple recovery:** Regenerate parquet from DB, regenerate catalog

---

## Questions to Resolve

1. **Do we need parquet exports at all?**
   - If MCP queries database directly, maybe not
   - Current: MCP uses parquet for speed

2. **Should canonical manifest be per-publication or per-source?**
   - Per-publication: Fewer files, but large YAMLs
   - Per-source: More files, but focused

3. **Log retention: 7 days enough?**
   - For debugging: Yes
   - For compliance/audit: May need longer

---

## Implementation Priority

1. **HIGH:** Create data/ structure, move generated files
2. **HIGH:** Update .gitignore
3. **MEDIUM:** Consolidate canonical manifests
4. **LOW:** Update scripts to use tmp/
5. **LOW:** Add cleanup cron job

---

**This is a PROPOSAL. Review and adjust before implementing.**
