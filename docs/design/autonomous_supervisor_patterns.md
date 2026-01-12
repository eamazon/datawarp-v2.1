# Autonomous Supervisor - Error Patterns

**Created:** 2026-01-12 11:00 UTC
**Purpose:** Document error patterns discovered through E2E testing to inform supervisor design

---

## Error Patterns Discovered

### Pattern 1: Invalid URL (404 Not Found)

**Stage:** Manifest Generation (url_to_manifest.py)

**Detection:**
```
HTTPError: 404 Client Error: Not Found for url: https://...
```

**Root Cause:** URL doesn't exist - NHS hasn't published that period

**Investigation Steps:**
1. Parse URL from error message
2. Fetch the publication landing page
3. Extract available periods from HTML
4. Compare config vs actual available periods

**Manifest Fix:**
- Remove non-existent URLs from publications.yaml
- Update frequency (e.g., monthly → quarterly)
- Add notes explaining availability

**State Fix:**
- Clear failed entry from state.json
- (URL removed from config means it won't be retried)

**Resume:** Re-run backfill (will skip removed URLs)

---

### Pattern 2: No Files Found (Upcoming Publication)

**Stage:** Manifest Generation (url_to_manifest.py)

**Detection:**
```
Found 0 files
No files found!
```

**Root Cause:** Page exists but publication is "Upcoming, not yet published"

**Investigation Steps:**
1. Fetch the URL directly
2. Check page content for:
   - "(Upcoming, not yet published)" text
   - Publication date
   - "Official statistics in development" badge

**Manifest Fix:**
- Add `pending_until: YYYY-MM-DD` to state
- Or remove from config until published

**State Fix:**
- Mark as `pending` not `failed`
- Store expected publication date

**Resume:** Skip until publication date passes

---

### Pattern 3: Type Mismatch (Load Failure)

**Stage:** Database Load (datawarp load-batch)

**Detection:**
```
Type mismatch: INTEGER column received unexpected value
```

**Root Cause:**
- Manifest defines column as INTEGER
- Actual Excel has mixed values (numbers + text like '*' for suppressed)

**Investigation Steps:**
1. Check manifest column definitions (data_type field)
2. Look at DEBUG TYPE INFERENCE output
3. Identify columns with mixed types: `types: {'n', 's'}`
4. Find the specific value causing the issue

**Manifest Fix:**
- Change `data_type: integer` → `data_type: varchar` for affected columns
- Or set `enabled: false` to skip problematic source
- Or add `--unpivot` transformation for wide date columns

**State Fix:**
- Clear failed entry to allow retry

**Resume:** Re-run load (will use updated manifest types)

---

### Pattern 4: Partial Success (NEW - Critical Discovery)

**Stage:** Database Load (datawarp load-batch)

**Detection:**
- Overall status: FAILED
- But some sources DID load successfully
- Look for: `⚠️ Low row count: N rows loaded`

**Root Cause:**
- Some sources in manifest load successfully
- One or more sources fail (type mismatch, empty data, etc.)
- Backfill marks entire URL as FAILED

**Investigation Steps:**
1. Query tbl_load_history for recent loads
2. Compare loaded sources vs manifest enabled sources
3. Identify which specific sources failed
4. Check error messages for failed sources

**Example from E2E Test:**
```
Manifest: 6 enabled sources
Loaded:   4 sources (201,094 rows total)
Failed:   2 sources (gp_data_quality, practice_oc_submissions)
Status:   Marked as FAILED (should be PARTIAL)
```

**Manifest Fix:**
- Disable only the failed sources: `enabled: false`
- Or fix the specific type issues in failed sources

**State Fix:**
- Current: state.json only tracks URL-level success/failure
- Needed: Track per-source status within each URL

**Resume:**
- Current: Re-runs all sources (wasteful)
- Needed: Only retry failed sources

---

### Pattern 5: Low Row Count Warning

**Stage:** Database Load (datawarp load-batch)

**Detection:**
```
⚠️ Low row count: 7 rows loaded to staging.tbl_X (expected >100)
```

**Root Cause:**
- Source loaded successfully but has very few rows
- Could be: small lookup table, truncated data, wrong sheet

**Investigation Steps:**
1. Check if this is expected (lookup table)
2. Compare with reference manifest row counts
3. Verify source file extraction

**Action:** Usually informational, not an error. Supervisor should log but not fail.

---

## Pipeline Stages & Possible Errors

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Stage 1: URL → Manifest (url_to_manifest.py)                                │
├─────────────────────────────────────────────────────────────────────────────┤
│ ✅ Pattern 1: 404 Not Found (URL doesn't exist)                             │
│ ✅ Pattern 2: No files found (upcoming publication)                         │
│ ⏳ 403 Forbidden (CloudFlare block) - not tested                            │
│ ⏳ Timeout (network issues) - not tested                                    │
│ ⏳ Corrupt/password-protected Excel - not tested                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ Stage 2: Manifest → Enriched (enrich_manifest.py)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│ ⏳ LLM timeout - not tested                                                 │
│ ⏳ LLM rate limit - not tested                                              │
│ ⏳ Invalid JSON response - not tested                                       │
│ ⏳ Reference manifest not found - not tested                                │
├─────────────────────────────────────────────────────────────────────────────┤
│ Stage 3: Enriched → Database (datawarp load-batch)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ ✅ Pattern 3: Type mismatch (INTEGER vs mixed values)                       │
│ ✅ Pattern 4: Partial success (some sources load, some fail)                │
│ ✅ Pattern 5: Low row count warning                                         │
│ ⏳ DB connection failed - not tested                                        │
│ ⏳ Disk full - not tested                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ Stage 4: Database → Parquet (export_to_parquet.py)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ ⏳ Table not found - not tested                                             │
│ ⏳ Permission denied - not tested                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Supervisor Capabilities Needed

Based on patterns discovered:

### 1. Error Detection
- Parse stdout/stderr for error patterns
- Classify error type (404, no files, type mismatch, partial success)
- Extract relevant context (URL, source code, column name)

### 2. Context Gathering
- Web fetch (check landing pages, page status)
- Database query (check what actually loaded)
- File read (check manifests, state.json)
- Compare manifest vs actual loaded sources

### 3. Investigation (Human-like)
- Generate troubleshooting report
- Show: what worked, what failed, why
- Recommend: specific fix actions

### 4. Manifest Fixes (Allowed)
- Edit publications.yaml (remove/update URLs)
- Edit manifest YAML (change types, disable sources)
- Edit state.json (clear failed, add pending_until)

### 5. Resume Logic
- Track per-source status, not just per-URL
- Skip already-loaded sources
- Retry only failed sources
- Handle partial success properly

---

## State Tracking Gap

**Current state.json:**
```json
{
  "processed": {
    "adhd/nov25": {"completed_at": "..."}
  },
  "failed": {
    "online_consultation_test/nov25": {"error": "See output above"}
  }
}
```

**Needed for autonomous operation:**
```json
{
  "processed": {
    "adhd/nov25": {
      "completed_at": "...",
      "sources": {
        "adhd_summary": {"status": "loaded", "rows": 450},
        "adhd_by_age": {"status": "loaded", "rows": 1200}
      }
    }
  },
  "partial": {
    "online_consultation_test/nov25": {
      "started_at": "...",
      "sources": {
        "gp_submissions_by_practice": {"status": "loaded", "rows": 6170},
        "gp_data_quality": {"status": "failed", "error": "type mismatch"}
      }
    }
  },
  "pending": {
    "online_consultation/dec25": {
      "pending_until": "2026-01-29",
      "reason": "upcoming publication"
    }
  }
}
```

---

## Next Steps

1. Design supervisor architecture based on these patterns
2. Implement granular state tracking
3. Build error classification logic
4. Create investigation report generator
5. Implement manifest fix actions
6. Build resume logic with per-source tracking
