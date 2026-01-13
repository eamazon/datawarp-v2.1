# Backfill Workflow - LLM-Driven NHS Data Loading

**Updated: 2026-01-13 11:30 UTC**

Quick reference for processing historical NHS data with LLM monitoring.

---

## 🔍 Operational Commands (NEW v2.2)

### Check Run Status
```bash
# Analyze latest run - did it succeed?
python scripts/analyze_logs.py

# Summary of all runs today
python scripts/analyze_logs.py --all

# Show only errors
python scripts/analyze_logs.py --errors

# Get restart commands for failed runs
python scripts/analyze_logs.py --restart
```

### Force Reload Data
```bash
# Force reload a specific publication (bypasses "already processed" check)
python scripts/backfill.py --pub adhd --force

# Retry all previously failed items
python scripts/backfill.py --retry-failed
```

### Idempotency Model

DataWarp uses **two levels** of duplicate prevention, making reloads always safe:

1. **State tracking** (`state/state.json`):
   - Records which publication/period combinations have been processed
   - Skipped by default; override with `--force` flag

2. **Replace mode in database**:
   - Data loading DELETEs existing rows for the same period before INSERT
   - This makes reloads safe - no duplicate rows

**Restart workflow for failed loads:**
```bash
# 1. Find what failed and get restart commands
python scripts/analyze_logs.py --restart
# Output: python scripts/backfill.py --pub online_consultation --force

# 2. Run the restart command
python scripts/backfill.py --pub online_consultation --force
# Re-processes the publication, replacing any partial data
```

---

## 🚀 Quick Start

### 1. Add URLs to Config

Edit `config/publications.yaml`:

```yaml
publications:
  adhd:
    name: "ADHD Management Information"
    frequency: monthly
    landing_page: https://digital.nhs.uk/data-and-information/publications/statistical/mi-adhd
    reference_manifest: manifests/production/adhd/adhd_aug25_enriched.yaml
    urls:
      - period: dec25
        url: https://digital.nhs.uk/data-and-information/publications/statistical/mi-adhd/december-2025
      - period: jan26
        url: https://digital.nhs.uk/data-and-information/publications/statistical/mi-adhd/january-2026
```

### 2. Preview What Will Process

```bash
python scripts/backfill.py --dry-run
```

Shows which URLs are pending, already processed, or previously failed.

### 3. Execute Processing

```bash
python scripts/backfill.py
```

Processes all pending URLs:
- ✅ Downloads Excel file
- ✅ Generates manifest (extracts structure)
- ✅ Enriches manifest (LLM adds semantic names OR uses reference matching)
- ✅ Loads to PostgreSQL
- ✅ Exports to Parquet
- ✅ Updates state tracking

### 4. Check Status

```bash
python scripts/backfill.py --status
```

Shows progress bars for each publication.

---

## 📊 LLM Monitoring (Optional)

**Cost:** $0.09/month with Gemini (50 events/day)

The backfill system logs events to `state/state.json`. You can monitor these with LLM:

```bash
python scripts/test_monitor_gemini.py
```

**What LLM monitors:**
- Zero-row loads (extraction failures)
- Timeout errors (network issues)
- Unusually low row counts (data quality issues)
- Schema drift (unexpected columns)

**Accuracy:** Gemini 60%, Claude 40%, Qwen (local/free) 33%

**Recommendation:** Use Gemini for production monitoring.

---

## 🔄 Workflow Details

### First Period of a Publication

**Example:** Loading ADHD December 2025 for the first time

```bash
# 1. Generate manifest
python scripts/url_to_manifest.py <url> manifests/production/adhd/adhd_dec25.yaml

# 2. Enrich with LLM (NO --reference flag for first period)
python scripts/enrich_manifest.py \
  manifests/production/adhd/adhd_dec25.yaml \
  manifests/production/adhd/adhd_dec25_enriched.yaml

# 3. Load to database
datawarp load-batch manifests/production/adhd/adhd_dec25_enriched.yaml

# 4. Export to Parquet
python scripts/export_to_parquet.py --publication adhd
```

**Result:** LLM creates semantic names, establishes schema baseline.

---

### Subsequent Periods

**Example:** Loading ADHD January 2026 (use December as reference)

```bash
# 1. Generate manifest
python scripts/url_to_manifest.py <url> manifests/production/adhd/adhd_jan26.yaml

# 2. Enrich with reference (USE --reference flag)
python scripts/enrich_manifest.py \
  manifests/production/adhd/adhd_jan26.yaml \
  manifests/production/adhd/adhd_jan26_canonical.yaml \
  --reference manifests/production/adhd/adhd_dec25_enriched.yaml

# 3. Load to database
datawarp load-batch manifests/production/adhd/adhd_jan26_canonical.yaml

# 4. Export to Parquet
python scripts/export_to_parquet.py --publication adhd
```

**Result:** Reference matching is deterministic (no LLM calls), cross-period consolidation works.

---

## 📁 File Organization

```
manifests/
  production/
    adhd/
      adhd_aug25_enriched.yaml    # First period (LLM enriched)
      adhd_nov25_canonical.yaml   # Subsequent (reference-based)
      adhd_dec25_canonical.yaml
    pcn_workforce/
    gp_practice/

state/
  state.json                      # Tracks processed/failed URLs

output/
  adhd_*.parquet                  # Exported datasets
  catalog.parquet                 # MCP registry (184 datasets)
```

---

## 🛡️ Error Handling

### CloudFlare 403 Blocks

Some NHS URLs block automated requests:

**Solution:** Script already includes browser headers, but advanced protection may still block.

**Workaround:** Download manually and process local file:
```bash
python scripts/url_to_manifest.py /path/to/downloaded.xlsx manifests/...
```

### Failed Enrichment

If LLM enrichment fails, retry with:
```bash
python scripts/backfill.py --retry-failed
```

### Partial Failures

If some sheets fail to load:
- Check `state/state.json` → "failed" section
- Review error messages
- Fix that specific URL/period
- Re-run backfill (skips successful ones)

---

## 📈 Current State

**As of 2026-01-11:**
- **35 periods processed** successfully
- **50+ periods failed** (mostly CloudFlare blocks)
- **184 datasets** in catalog
- **77M rows** across all datasets

**Publications loaded:**
- ADHD: Aug 2025, Nov 2025, May 2025
- Online Consultation: Mar-Nov 2025 (9 periods)
- PCN Workforce: Mar-May 2025
- GP Practice: Mar-Dec 2025
- GP Appointments: Oct-Nov 2025

---

## 🎯 Next Steps

### Option 1: Expand Coverage
Add more URLs to `publications.yaml` for:
- Additional ADHD months (Dec 2025, Jan 2026, etc.)
- New publications (Dementia, Mental Health, Waiting Times)
- Historical data (go back to 2020)

### Option 2: Improve Monitoring
Implement automated monitoring:
- Daily digest emails
- Slack notifications for failures
- Dashboard showing processing health

### Option 3: Optimize Performance
- Add download caching (avoid re-downloading)
- Parallel processing (multiple URLs at once)
- Incremental updates (only process new data)

---

## 💡 Tips

**1. Test with small config first**
Use `config/publications_test.yaml` with 2-3 URLs to validate workflow.

**2. Use --dry-run liberally**
Always preview before executing large batches.

**3. Set reference manifests**
After first period, update `publications.yaml` with `reference_manifest` path for faster processing.

**4. Monitor state.json**
Check for growing "failed" section - indicates systematic issues.

**5. Rebuild catalog after bulk loads**
```bash
python scripts/rebuild_catalog.py
```

---

## 📞 Troubleshooting

**Issue:** "Dataset not found" error
**Fix:** Check source_code in catalog.parquet matches what you're querying

**Issue:** "Column not found" error
**Fix:** Enrichment may have renamed columns - check manifest YAML

**Issue:** Long processing times
**Fix:** Export is slow - use `--publication` flag to export only what you loaded

**Issue:** Out of disk space
**Fix:** PostgreSQL is 15 GB - run cleanup script or archive old data

---

**See also:**
- `TASKS.md` - What to work on next
- `IMPLEMENTATION_TASKS.md` - Task prioritization
- `docs/pipelines/06_backfill_monitor.md` - Architecture diagram
