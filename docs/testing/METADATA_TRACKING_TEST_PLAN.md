# Metadata Tracking Test Plan

**Status:** ❌ FAILING - Column metadata not being generated during enrichment
**Date:** 2026-01-18
**Tested By:** Automated test suite

## Executive Summary

Metadata tracking is **currently broken**. The root cause is that the enrichment process generates manifest files with **empty `columns: []` sections**, so no column-level metadata is stored in `datawarp.tbl_column_metadata`.

## Current State

### What's Working ✅
- Load history tracking (`tbl_load_history`) - Records all loads, rows, columns added
- Manifest file tracking (`tbl_manifest_files`) - Tracks what files were loaded
- Schema drift detection - New columns are detected and tracked in `columns_added` array
- Data source registration - All sources properly registered in `tbl_data_sources`

### What's Broken ❌
- **Column metadata generation** - Enrichment creates `columns: []` (empty list)
- **Metadata storage** - `tbl_column_metadata` table is empty
- **Semantic discovery** - Can't query columns by description/keywords
- **Data catalog** - No column descriptions for Parquet exports

## Root Cause Analysis

### The Problem

```yaml
# Current enriched manifest (BROKEN)
sources:
  - code: adhd_summary
    table: tbl_adhd_summary
    columns: []  # ❌ EMPTY!
```

**Expected:**
```yaml
sources:
  - code: adhd_summary
    table: tbl_adhd_summary
    columns:
      - name: reporting_period
        original_name: "Reporting period"
        description: "The month and year the data refers to"
        data_type: varchar
        is_dimension: true
        query_keywords: ["period", "month", "date"]
      - name: total_referrals
        original_name: "Total referrals"
        description: "Number of new ADHD referrals in the reporting period"
        data_type: integer
        is_measure: true
        query_keywords: ["count", "referrals", "total"]
```

### Why It's Broken

The enrichment code in `src/datawarp/pipeline/enricher.py` is:
1. Calling the LLM to generate column metadata
2. **But NOT adding it to the manifest** before saving

## Test Plan: Metadata Edge Cases

### Test Case 1: Initial Load (First Period)
**Scenario:** Load ADHD May 2025 (first time ever)
**Expected:**
- ✅ Manifest generated with columns
- ✅ LLM enrichment creates column metadata (name, description, type, keywords)
- ✅ Load stores metadata in `tbl_column_metadata`
- ✅ All columns have `metadata_source='llm'` and `created_at=NOW()`

**Current:** ❌ FAILS - No column metadata generated

---

### Test Case 2: Subsequent Load (Same Schema)
**Scenario:** Load ADHD August 2025 using May as reference
**Expected:**
- ✅ Reference matching reuses May's column metadata
- ✅ No LLM call needed (metadata copied from reference)
- ✅ Metadata in database has `metadata_source='reference'`
- ✅ No `updated_at` changes (metadata unchanged)

**Current:** ❌ FAILS - No metadata exists to reference

---

### Test Case 3: Schema Drift - New Columns Added
**Scenario:** Load ADHD November 2025, schema adds `new_metric` column
**Expected:**
- ✅ Reference matches existing columns (reuse metadata)
- ✅ LLM called ONLY for new column (`new_metric`)
- ✅ New column has `metadata_source='llm'`, existing have `'reference'`
- ✅ `columns_added` array in `tbl_load_history` tracks `['new_metric']`
- ✅ Metadata stored for new column with `created_at=NOW()`

**Current:** ❌ FAILS - No metadata infrastructure

---

### Test Case 4: Schema Drift - Columns Removed
**Scenario:** Load ADHD Feb 2026, NHS removes `deprecated_metric` column
**Expected:**
- ✅ Existing metadata for `deprecated_metric` remains in database (historical record)
- ✅ Table schema doesn't have the column anymore
- ✅ Metadata query shows "orphaned" metadata (in metadata table but not in actual table)
- ⚠️  Optional: Flag orphaned metadata with `is_active=false` or deletion date

**Current:** N/A - Can't test without metadata

---

### Test Case 5: Column Type Change
**Scenario:** Column `age_group` changes from `varchar` to `integer`
**Expected:**
- ✅ DDL updates table schema (ALTER COLUMN)
- ✅ Metadata `data_type` updated from 'varchar' to 'integer'
- ✅ `updated_at` timestamp updated
- ✅ Maybe log type change in `tbl_drift_events` (if that table exists)

**Current:** N/A - Can't test without metadata

---

### Test Case 6: LLM Description Changes
**Scenario:** Re-enrich May 2025 with updated LLM prompt, descriptions change
**Expected:**
- ✅ Metadata `description` field updated
- ✅ `query_keywords` potentially updated
- ✅ `updated_at` timestamp updated
- ✅ `confidence` score may change
- ⚠️  Optional: Version history of descriptions (probably overkill)

**Current:** N/A - Can't test without initial metadata

---

### Test Case 7: Reference vs LLM Metadata Source
**Scenario:** Mix of reference-matched and LLM-enriched columns in same load
**Expected:**
- ✅ Metadata has mixed `metadata_source` values ('reference' and 'llm')
- ✅ Reference columns have `confidence=1.0` (exact match)
- ✅ LLM columns have `confidence=0.70-0.90` (model confidence)
- ✅ Query can filter by metadata source

**Current:** N/A - Can't test without metadata

---

### Test Case 8: Force Reload
**Scenario:** `--force` reload of already-loaded period
**Expected:**
- ✅ Data reloaded (TRUNCATE + INSERT or DELETE + INSERT)
- ✅ Metadata NOT duplicated (UPSERT on primary key)
- ✅ `updated_at` timestamp updated ONLY if metadata changed
- ✅ Load history gets new entry

**Current:** ❌ Load history works, but no metadata to test

---

### Test Case 9: Metadata Consistency Check
**Scenario:** Compare `tbl_column_metadata` with actual table schema
**Expected:**
- ✅ All non-system columns in table have metadata
- ✅ No "orphaned" metadata (metadata exists but column doesn't)
- ✅ Data types match between metadata and actual schema
- ✅ System columns (`period`, `loaded_at`, `data_date`) excluded from metadata

**Current:** ❌ FAILS - Metadata table empty, but tables have columns

---

### Test Case 10: Timestamp Tracking
**Scenario:** Check metadata timestamp behavior
**Expected:**
- ✅ `created_at` set on first insert
- ✅ `updated_at` = `created_at` initially
- ✅ `updated_at` changes when metadata updates
- ✅ `updated_at` does NOT change on force reload if metadata identical

**Current:** N/A - No metadata to test timestamps

---

## How to Fix

### Step 1: Fix Enrichment (Critical)

File: `src/datawarp/pipeline/enricher.py`

The enricher needs to:
1. Call LLM to generate column metadata (probably already doing this)
2. **Parse the LLM response into column metadata structure**
3. **Add parsed metadata to `source['columns']` in the manifest**
4. Save manifest with column metadata

### Step 2: Test with One Source

```bash
# Re-enrich ADHD May 2025
python scripts/enrich_manifest.py \
  manifests/backfill/adhd/adhd_2025-05_raw.yaml \
  manifests/backfill/adhd/adhd_2025-05_enriched_TEST.yaml

# Verify columns populated
python -c "
import yaml
with open('manifests/backfill/adhd/adhd_2025-05_enriched_TEST.yaml') as f:
    m = yaml.safe_load(f)
    for s in m['sources']:
        print(f'{s[\"code\"]}: {len(s.get(\"columns\", []))} columns')
"

# If columns exist, load it
python scripts/backfill.py --config config/test.yaml --pub adhd --period 2025-05 --force

# Check metadata stored
python scripts/test_metadata_tracking.py
```

### Step 3: Re-enrich All ADHD

Once fixed:
```bash
# Re-enrich all ADHD periods
for period in 2025-05 2025-08 2025-11; do
    python scripts/enrich_manifest.py \
      manifests/backfill/adhd/adhd_${period}_raw.yaml \
      manifests/backfill/adhd/adhd_${period}_enriched.yaml
done

# Reload to populate metadata
python scripts/backfill.py --config config/publications_with_all_urls.yaml --pub adhd --force
```

### Step 4: Run Full Test Suite

```bash
python scripts/test_metadata_tracking.py
```

Expected: All tests pass ✅

---

## Test Automation

### Quick Check Script

```bash
# Check if metadata exists for a publication
python -c "
from datawarp.storage.connection import get_connection

pub = 'adhd'
with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute('''
            SELECT canonical_source_code, COUNT(*)
            FROM datawarp.tbl_column_metadata
            WHERE canonical_source_code LIKE %s
            GROUP BY canonical_source_code
        ''', (f'{pub}%',))

        results = cur.fetchall()
        if results:
            print(f'✅ Metadata exists for {pub}:')
            for code, count in results:
                print(f'  {code}: {count} columns')
        else:
            print(f'❌ NO metadata for {pub}')
"
```

### Comprehensive Test

```bash
python scripts/test_metadata_tracking.py
```

---

## Success Criteria

All tests passing means:
- ✅ Column metadata generated during enrichment
- ✅ Metadata stored in database during loading
- ✅ Reference matching preserves metadata across periods
- ✅ Schema drift tracked (new/removed columns)
- ✅ Timestamps track creation and updates
- ✅ Metadata source tracked (llm vs reference)
- ✅ Metadata consistent with actual table schemas

---

## Current Test Results

**Run:** 2026-01-18 20:23:42
**Pass Rate:** 11.1% (1/9 tests)

```
TEST 1: ADHD Metadata Tracking                 ❌ FAILED (0/6)
TEST 2: Schema Drift Tracking                  ❌ FAILED (0/2)
TEST 3: Metadata vs Schema Consistency         ⚠️  PARTIAL (1/2)
TEST 4: Reference vs LLM Metadata              ❌ FAILED (0/1)
TEST 5: Timestamp Tracking                     ⏭️  SKIPPED (no metadata)
```

**BLOCKER:** Enrichment not generating column metadata
**Next Step:** Fix enricher.py to populate `source['columns']`
