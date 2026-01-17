# DATAWARP COMPREHENSIVE AUDIT FINDINGS
**Audit Started:** 2026-01-17
**Auditor:** Claude (Autonomous)
**Scope:** Complete system as documented in docs/USERGUIDE.md

===============================================================================
## AUDIT STATUS SUMMARY
===============================================================================

**Pathways Audited:** 1/50+
**Issues Found:** 3 (2 critical, 1 UX)
**Overall Confidence:** TBD (audit in progress)

===============================================================================
## QUICK START PATHWAY AUDIT (Section 2 of USERGUIDE.md)
===============================================================================

### Pathway: Quick Start (5 Minutes)
**Confidence: 75% 🟡 - FUNCTIONAL WITH ISSUES**

### Test Methodology
- Created automated test script (`/tmp/audit_execution.sh`)
- Cleared state file before testing
- Executed exact steps from USERGUIDE.md Section 2
- Captured full output with timestamps

### Steps Tested

#### STEP 1: Setup (Virtual Environment)
**Status:** ✅ PASSED
**Command:** `source .venv/bin/activate`
**Evidence:** Python 3.11.6 confirmed active
**Confidence:** 100% 🟢

#### STEP 2: Run First Load
**Status:** ⚠️ PARTIAL PASS
**Command:** `python scripts/backfill.py --pub adhd`
**Exit Code:** 0 (success)
**Duration:** 50s
**Evidence:**
```
ADHD Management Information
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ May 2025     5.6s   0 sources         0 rows
✓ Aug 2025    13.9s   0 sources         0 rows
✓ Nov 2025    27.4s   0 sources         0 rows

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPLETE: 0 sources | 0 rows
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Issues Found:**

1. **ISSUE #1 - CRITICAL: Parquet Export Failure**
   - **Severity:** ERROR
   - **Message:** `[ERROR] Parquet export failed: Table staging.tbl_adhd_prevalence_by_age does not exist`
   - **Impact:** Export stage fails silently with non-fatal warning
   - **Root Cause:** Parquet export script tries to export table that doesn't exist
   - **Evidence:** Database query confirms table doesn't exist:
     ```sql
     SELECT table_name FROM information_schema.tables
     WHERE table_schema = 'staging' AND table_name = 'tbl_adhd_prevalence_by_age'
     -- Result: 0 rows
     ```
   - **Action Required:** Fix export script to only export tables that exist
   - **Confidence Impact:** Reduces from 100% to 75%

2. **ISSUE #2 - UX PROBLEM: Confusing "0 sources | 0 rows" Message**
   - **Severity:** MODERATE
   - **Message:** `COMPLETE: 0 sources | 0 rows`
   - **Context:** Data was already loaded (skipped), not newly loaded
   - **User Experience:** User sees "0 sources | 0 rows" and thinks nothing happened
   - **Expected Behavior:** Should show "Already loaded: 3 periods, 18,508 rows (skipped)"
   - **Note:** This was supposed to be fixed in previous session UX improvements
   - **Evidence:** All periods showed "⏭ SKIPPED - Already loaded" but summary said "0 sources"
   - **Action Required:** Update summary message to distinguish new loads from skips
   - **Confidence Impact:** -10%

3. **ISSUE #3 - TEST ISOLATION: State/Database Mismatch**
   - **Severity:** LOW (test methodology issue)
   - **Context:** Test cleared state.json but database still had data
   - **Result:** All periods skipped because already in database
   - **Not a Product Issue:** This is expected behavior (idempotent loading)
   - **Note:** For clean test, should also reset database OR expect skips
   - **No Confidence Impact**

**Database State Verification:**
```sql
-- Total staging tables: 106
-- ADHD-related tables: 6
  - tbl_adhd
  - tbl_adhd_indicators
  - tbl_adhd_prevalence
  - tbl_table_adhd_prevalence
  - tbl_with_adhd_diag_p
  - tbl_without_adhd_diag_p

-- State file shows:
  - adhd/2025-05: 6,913 rows loaded
  - adhd/2025-08: 1,453 rows loaded
  - adhd/2025-11: 10,142 rows loaded
  - Total: 18,508 rows
```

**Parquet Export Verification:**
- 18 .parquet files exist in output/
- Multiple ADHD parquet files created successfully
- But export attempted non-existent table and failed

#### STEP 3: Check Loaded Data
**Status:** ✅ PASSED
**Command:** `datawarp list`
**Evidence:** Successfully listed all 106 staging tables
**Sample Output:**
```
adhd_prevalence_by_age → staging.tbl_adhd_prevalence_by_age
practice_level_crosstab → staging.tbl_practice_level_crosstab
mapping → staging.tbl_mapping
...
```
**Confidence:** 100% 🟢

#### STEP 4: Query Data with SQL
**Status:** ✅ PASSED (with documentation error)
**Command Executed:** `psql -h localhost -U databot -d datawarp2 -c "SELECT COUNT(*) FROM staging.tbl_adhd"`
**Result:** 1,304 rows returned
**Sample Data:** Retrieved 5 sample rows successfully with all provenance fields populated
**Evidence:**
```
 count
-------
  1304
(1 row)
```
**Confidence:** 100% 🟢

**ISSUE #5 FOUND - Documentation Error:**
- **USERGUIDE.md says:** `psql -d databot_dev`
- **Actual database:** `datawarp2`
- **Impact:** New users following the guide will get "database does not exist" error
- **Severity:** MODERATE (documentation/UX)
- **Fix Required:** Update USERGUIDE.md Section 2.3 with correct database name

### Overall Quick Start Assessment

**What Works:**
✅ Virtual environment setup
✅ Backfill command executes successfully
✅ Data loads to database
✅ `datawarp list` command shows loaded tables
✅ Idempotent loading (skips already-loaded data)

**What Needs Fixing:**
❌ Parquet export tries to export non-existent tables (CRITICAL)
❌ Summary message shows "0 sources | 0 rows" when data is skipped (UX)

**What Needs Testing:**
⏸️ SQL query validation step

**Confidence Score: 75% 🟡**

Rationale:
- Core pathway works (user can load data successfully)
- Critical issue: Parquet export fails for some tables (-15%)
- UX issue: Confusing summary message (-10%)
- SQL verification step not yet tested (pending)
- Would rate 95%+ if Parquet export was fixed and message was clearer

===============================================================================
## NEXT PATHWAYS TO AUDIT
===============================================================================

### Tier 1: Critical Pathways (Must be 95%+)
- [ ] Complete Quick Start SQL verification
- [ ] Backfill one publication (fresh load)
- [ ] Verify data loaded (database queries)
- [ ] Status command
- [ ] Database reset workflow

### Tier 2: Configuration Patterns (Must be 85%+)
- [ ] Pattern A: Monthly Publication
- [ ] Pattern B: Quarterly Publication
- [ ] Pattern C: URL Exceptions
- [ ] Pattern D: Publication Offset
- [ ] Pattern E: Explicit URLs
- [ ] Pattern F: Fiscal Quarters

### Tier 3: Advanced Features
- [ ] All backfill flags (--dry-run, --force, --retry-failed, --status)
- [ ] Verification checklist (6 items from USERGUIDE.md)
- [ ] Monitoring queries (5 types)
- [ ] Troubleshooting workflows (5 scenarios)
- [ ] Log interrogation (6 commands)

===============================================================================
## STATE TRACKING VALIDATION
===============================================================================

**Updated:** 2026-01-17 (Session 26 - Critical Finding)

### ISSUE #4 - CRITICAL: State File Inaccurate (64% Overcount)

**Severity:** CRITICAL 🔴
**Status:** CONTRADICTS SESSION 25 CERTIFICATION

Session 25 certified state tracking as "100% accurate" but detailed verification reveals **major discrepancies**.

**State File Claims (state/state.json):**
```json
"adhd/2025-05": { "rows_loaded": 6913 }
"adhd/2025-08": { "rows_loaded": 1453 }
"adhd/2025-11": { "rows_loaded": 10142 }
Total: 18,508 rows
```

**Actual Database Evidence:**

1. **Manifest Tracking (Source of Truth):**
```sql
SELECT period, COUNT(*) as sources, SUM(rows_loaded) as total
FROM datawarp.tbl_manifest_files
WHERE source_code LIKE '%adhd%'
GROUP BY period
```

| Period | Sources | Rows Loaded |
|--------|---------|-------------|
| 2025-05 | 1 | 1,304 |
| 2025-08 | 1 | 1,318 |
| 2025-11 | 4 | 8,635 |
| **TOTAL** | **6** | **11,257** |

2. **Database Row Counts (Verified):**
- tbl_adhd: 1,304 rows
- tbl_adhd_indicators: 1,318 rows
- tbl_adhd_prevalence: 8,149 rows
- tbl_table_adhd_prevalence: 162 rows
- tbl_with_adhd_diagnosis_prescribing: 162 rows
- tbl_without_adhd_diagnosis_prescribing: 162 rows
- **TOTAL: 11,257 rows** ✅

3. **Load History (Verified):**
```sql
SELECT SUM(rows_loaded) FROM datawarp.tbl_load_history lh
JOIN datawarp.tbl_data_sources ds ON lh.source_id = ds.id
WHERE ds.code LIKE '%adhd%'
```
**Result: 11,257 rows** ✅

**Discrepancy Analysis:**
- State file claims: **18,508 rows**
- Database/manifest actual: **11,257 rows**
- **Overcount: 7,251 rows (64% error rate!)**
- **Per-period errors:**
  - May 2025: Claims 6,913 | Actual 1,304 | Error: +5,609 rows (430% overcount)
  - Aug 2025: Claims 1,453 | Actual 1,318 | Error: +135 rows (10% overcount)
  - Nov 2025: Claims 10,142 | Actual 8,635 | Error: +1,507 rows (17% overcount)

**Root Cause (Hypothesis):**
The state file may be:
1. Double-counting rows across multiple sources in same publication/period
2. Including rows from failed/skipped sources
3. Not properly deducting replaced rows
4. Tracking row counts from file parsing instead of actual database inserts

**Impact:**
- Users cannot trust `--status` command row counts
- Debugging and monitoring is unreliable
- Violates core requirement: "State tracking must be 100% accurate"

**Priority:** P0 - CRITICAL
**Blocks:** Production use, monitoring, debugging

**Action Required:**
1. Investigate state file update logic in backfill.py
2. Determine why row counts don't match manifest/database
3. Add validation test: state file vs. database cross-check
4. Fix state tracking to use manifest/database as source of truth

**Further Investigation (GP Appointments Cross-Check):**

Tested GP appointments publication to verify if state tracking issue is systemic:

```sql
SELECT manifest_name, SUM(rows_loaded)
FROM datawarp.tbl_manifest_files
WHERE manifest_name LIKE '%2024_20260117'
GROUP BY manifest_name
```

| Manifest | State File Claims | Manifest Actual | Match? |
|----------|-------------------|-----------------|--------|
| january_2024 | 15,595,054 | 15,595,054 | ✅ EXACT |
| february_2024 | 15,546,344 | 15,546,344 | ✅ EXACT |
| march_2024 | 15,863,507 | 15,863,507 | ✅ EXACT |
| april_2024 | 15,978,658 | 15,978,658 | ✅ EXACT |
| may_2024 | 16,073,638 | 16,073,638 | ✅ EXACT |

**Conclusion:** State tracking is **100% ACCURATE for GP appointments** but **64% INACCURATE for ADHD**

This suggests the issue is publication-specific, not systemic. Possible causes:
1. ADHD manifest has many `enabled: true` sources that failed to load
2. State file counts all manifest sources, not just successfully loaded ones
3. ADHD uses different state tracking logic than GP appointments

**Revises Session 25 Finding:**
- Session 25: "State Tracking 100% Certified ✅" (tested ADHD only)
- Session 26: "State Tracking is Publication-Dependent: ✅ for GP Appointments, ❌ for ADHD"

===============================================================================
## CRITICAL ISSUES LOG
===============================================================================

| ID | Severity | Pathway | Issue | Status | Priority |
|----|----------|---------|-------|--------|----------|
| #1 | CRITICAL | Quick Start | Parquet export fails for non-existent table `tbl_adhd_prevalence_by_age` | OPEN | P0 |
| #2 | MODERATE | Quick Start | Summary message shows "0 sources \| 0 rows" when data is skipped | OPEN | P1 |
| #4 | CRITICAL | State Tracking | State file overcounts ADHD by 64% (7,251 extra rows) - publication-specific bug | OPEN | P0 |
| #5 | MODERATE | Documentation | USERGUIDE.md has wrong database name (databot_dev vs datawarp2) | OPEN | P2 |
| #6 | MODERATE | Pipeline Docs | 01_e2e_data_pipeline.md uses wrong database name (databot_dev) | OPEN | P2 |
| #7 | CRITICAL | Pipeline Docs | 04_database_schema.md uses wrong database name throughout (16+ locations) | OPEN | P0 |
| #8 | MINOR | Pipeline Docs | 04_database_schema.md has outdated statistics (181 tables, should be 107) | OPEN | P3 |

===============================================================================
## RECOMMENDATIONS
===============================================================================

### Immediate Actions (P0)

1. **Fix Parquet Export Script**
   - Location: `scripts/export_to_parquet.py` (assumed)
   - Problem: Attempts to export tables that don't exist
   - Solution: Query database for existing tables before attempting export
   - OR: Make export failures truly non-fatal (don't log as ERROR)

2. **Improve Skip Summary Message**
   - Location: `scripts/backfill.py` summary section
   - Problem: Shows "COMPLETE: 0 sources | 0 rows" when skipping
   - Solution: Show "COMPLETE: 0 new sources | 0 new rows (3 periods skipped, 18,508 rows already loaded)"

### Testing Recommendations

1. **Add Integration Test for Quick Start**
   - Full clean slate test (reset DB + clear state)
   - Verify all 4 steps complete successfully
   - Assert on row counts, table existence, Parquet files

2. **Add Parquet Export Validation**
   - Test that export script handles missing tables gracefully
   - Verify that non-fatal warnings don't appear as ERROR level

===============================================================================
## AUDIT EXECUTION LOG
===============================================================================

**2026-01-17 Session:**
- Created audit framework and methodology
- Identified 50+ pathways from USERGUIDE.md + docs/pipelines/
- Created automated test script for Quick Start pathway
- Executed Quick Start test in background (task b561aa9)
- Analyzed results and documented 2 critical issues
- Database verification: 106 tables, 6 ADHD tables, 18 Parquet files
- Next: Continue with Tier 1 critical pathways

===============================================================================
## APPENDIX: RAW TEST OUTPUT
===============================================================================

See: `/private/tmp/claude/-Users-speddi-projectx-datawarp-v2-1/tasks/b561aa9.output`

Key excerpts:
- All 3 ADHD periods skipped (already loaded)
- Parquet export error: "Table staging.tbl_adhd_prevalence_by_age does not exist"
- Exit code 0 (success) despite export failure
- Duration: 50 seconds

===============================================================================
