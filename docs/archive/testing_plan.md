# Phase 1 Testing Plan - Real World Validation

**Created:** 2026-01-08
**Purpose:** Comprehensive end-to-end testing with real NHS data before Phase 1 sign-off

---

## Testing Philosophy

**NO unit tests only** - We need evidence from real NHS URLs showing:
1. Data actually loads
2. Schema drift handled correctly
3. Cross-period consolidation works
4. Edge cases don't break the system

**Evidence Required:**
- Database queries showing consolidated data
- Screenshots/logs of drift detection
- Before/After comparisons
- Failure handling demonstrations

---

## Test Scenario 1: Wide Date Column Pivoting

**Test URLs:**
- November 2025: https://digital.nhs.uk/data-and-information/publications/statistical/primary-care-network-workforce/30-november-2025
- October 2025: https://digital.nhs.uk/data-and-information/publications/statistical/primary-care-network-workforce/31-october-2025

**Challenge:**
These files contain wide date format (Apr_2025, May_2025, Jun_2025 as separate columns)

**Expected Behavior:**
1. Extractor detects columns like `Apr_2025`, `May_2025`, etc.
2. Wide date detector identifies pattern (3+ date columns)
3. Pivot transformation converts to long format (period column)
4. Single table `tbl_pcn_workforce_<measure>` contains all periods

**Validation Steps:**
```bash
# 1. Generate manifest
python scripts/url_to_manifest.py \
  "https://digital.nhs.uk/...november-2025" \
  manifests/test_pcn_nov25_raw.yaml

# 2. Check column names for date patterns
cat manifests/test_pcn_nov25_raw.yaml | grep "original_name"

# 3. Load data
datawarp load-batch manifests/test_pcn_nov25_raw.yaml

# 4. Query for wide columns
psql -h localhost -U databot_dev_user -d databot_dev -c "
  SELECT column_name
  FROM information_schema.columns
  WHERE table_schema = 'staging'
    AND table_name LIKE 'tbl_pcn%'
  ORDER BY ordinal_position;
"

# 5. Check if data spans multiple periods
psql -h localhost -U databot_dev_user -d databot_dev -c "
  SELECT period, COUNT(*)
  FROM staging.tbl_pcn_workforce_xxx
  GROUP BY period
  ORDER BY period;
"
```

**Evidence to Collect:**
- [ ] Screenshot of column names showing Apr_2025, May_2025 pattern
- [ ] Database schema showing period column (not wide format)
- [ ] Row count per period (should be consistent)
- [ ] Drift event log entry showing `wide_date_detected`

**Success Criteria:**
- Wide format detected automatically
- Pivoted to long format
- Period column contains 2025-04, 2025-05, etc.
- No data loss (row count × period count = wide row count)

---

## Test Scenario 2: Missing Periods + Schema Drift

**Test URLs:**
- August 2025: https://digital.nhs.uk/data-and-information/publications/statistical/mi-adhd/august-2025
- November 2025: https://digital.nhs.uk/data-and-information/publications/statistical/mi-adhd/november-2025

**Challenge:**
- September 2025 missing (no publication)
- November has new files not present in August (schema drift)

**Expected Behavior:**
1. August loads successfully → canonical codes created
2. Attempt September → URL discovery fails gracefully
3. November loads → fingerprinting matches August sources
4. New files in November → new canonical codes created
5. Drift events logged for new files

**Validation Steps:**
```bash
# 1. Load August
python scripts/url_to_manifest.py \
  "https://digital.nhs.uk/.../august-2025" \
  manifests/test_adhd_aug25_raw.yaml

python scripts/enrich.py \
  manifests/test_adhd_aug25_raw.yaml \
  manifests/test_adhd_aug25_enriched.yaml

python scripts/apply_enrichment.py \
  manifests/test_adhd_aug25_enriched.yaml \
  manifests/test_adhd_aug25_enriched_llm_response.json \
  manifests/test_adhd_aug25_canonical.yaml

datawarp load-batch manifests/test_adhd_aug25_canonical.yaml

# 2. Check canonical sources created
psql -h localhost -U databot_dev_user -d databot_dev -c "
  SELECT canonical_code, canonical_name, first_seen_period
  FROM datawarp.tbl_canonical_sources
  WHERE canonical_code LIKE 'adhd%';
"

# 3. Attempt September (should fail gracefully)
python scripts/url_to_manifest.py \
  "https://digital.nhs.uk/.../september-2025" \
  manifests/test_adhd_sep25_raw.yaml
# Expected: HTTP 404 or no files found

# 4. Load November
python scripts/url_to_manifest.py \
  "https://digital.nhs.uk/.../november-2025" \
  manifests/test_adhd_nov25_raw.yaml

python scripts/enrich.py \
  manifests/test_adhd_nov25_raw.yaml \
  manifests/test_adhd_nov25_enriched.yaml

python scripts/apply_enrichment.py \
  manifests/test_adhd_nov25_enriched.yaml \
  manifests/test_adhd_nov25_enriched_llm_response.json \
  manifests/test_adhd_nov25_canonical.yaml

datawarp load-batch manifests/test_adhd_nov25_canonical.yaml

# 5. Check fingerprint matching
psql -h localhost -U databot_dev_user -d databot_dev -c "
  SELECT
    canonical_code,
    COUNT(DISTINCT period) as period_count,
    STRING_AGG(DISTINCT period, ', ' ORDER BY period) as periods
  FROM datawarp.tbl_source_mappings
  WHERE canonical_code LIKE 'adhd%'
  GROUP BY canonical_code;
"

# 6. Check for new files in November
psql -h localhost -U databot_dev_user -d databot_dev -c "
  SELECT canonical_code, first_seen_period
  FROM datawarp.tbl_canonical_sources
  WHERE canonical_code LIKE 'adhd%'
    AND first_seen_period = '2025-11';
"

# 7. Check drift events
psql -h localhost -U databot_dev_user -d databot_dev -c "
  SELECT
    canonical_code,
    drift_type,
    severity,
    details
  FROM datawarp.tbl_drift_events
  WHERE canonical_code LIKE 'adhd%'
  ORDER BY detected_at DESC;
"
```

**Evidence to Collect:**
- [ ] List of canonical codes from August (baseline)
- [ ] Fingerprint match confidence scores (should be >0.80)
- [ ] Period count per canonical code (2 for matched sources)
- [ ] New canonical codes from November (first_seen_period = '2025-11')
- [ ] Drift event logs showing new_columns or new_source events
- [ ] Error handling for September (graceful failure, not crash)

**Success Criteria:**
- August sources get canonical codes
- September failure doesn't break system
- November sources match August fingerprints (same canonical code)
- New November files get new canonical codes
- No duplicate tables (adhd_summary_aug vs adhd_summary_nov)

---

## Test Scenario 3: Historical Backfill Discovery

**Test URL:**
- https://www.england.nhs.uk/statistics/statistical-work-areas/mixed-sex-accommodation/msa-data/

**Challenge:**
- Landing page has 2010-2011 through October 2026 data
- Need to discover next available period (November 2026)
- URL patterns may vary (msa-data-october-2026 vs oct-2026 vs 10-2026)

**Expected Behavior:**
1. Scrape landing page for all available periods
2. Identify missing periods (gaps in timeline)
3. Predict next expected period (November 2026)
4. Generate URL pattern variations
5. Test each variation until success or exhaustion

**Validation Steps:**
```bash
# 1. Discover available periods (manual for now)
curl -s "https://www.england.nhs.uk/.../msa-data/" | grep -oE "msa-data-[a-z]+-[0-9]{4}"

# 2. Generate manifest for latest (October 2026)
python scripts/url_to_manifest.py \
  "https://www.england.nhs.uk/.../msa-data-october-2026" \
  manifests/test_msa_oct26_raw.yaml

# 3. Check for period gaps
psql -h localhost -U databot_dev_user -d databot_dev -c "
  WITH periods AS (
    SELECT DISTINCT period
    FROM datawarp.tbl_source_mappings
    WHERE canonical_code LIKE 'msa%'
    ORDER BY period
  )
  SELECT
    period,
    LEAD(period) OVER (ORDER BY period) as next_period,
    (LEAD(period::date) OVER (ORDER BY period::date) - period::date) as days_gap
  FROM periods;
"

# 4. Test URL discovery (Phase 2 functionality)
# This will be implemented in Phase 2, but document expected behavior

# Expected: List of all available periods
# Expected: Identification of gaps (missing months)
# Expected: Prediction of next period
```

**Evidence to Collect:**
- [ ] List of all available periods on landing page
- [ ] Period gaps identified (e.g., missing June 2022)
- [ ] Canonical sources created for MSA
- [ ] Fingerprint matching across years (2010 vs 2026 same structure?)

**Success Criteria:**
- Can identify all available periods from landing page
- Detect missing periods (gaps in timeline)
- Predict next expected period correctly
- Handle URL pattern variations

**Note:** Full implementation in Phase 2, but test manual workflow now

---

## Test Scenario 4: Multiple File Types (Different Granularities)

**Test URL:**
- https://www.england.nhs.uk/statistics/statistical-work-areas/ae-waiting-times-and-activity/

**Challenge:**
- Monthly A&E Time Series November 2025
- Quarterly Annual Time Series (revised)
- Different update frequencies
- How to register and track separately?

**Expected Behavior:**
1. Monthly files → monthly canonical codes
2. Quarterly files → quarterly canonical codes
3. Annual files → annual canonical codes
4. Different tables for different granularities
5. Clear metadata distinction

**Validation Steps:**
```bash
# 1. Generate manifest for monthly file
python scripts/url_to_manifest.py \
  "https://www.england.nhs.uk/.../monthly-november-2025.xls" \
  manifests/test_ae_monthly_nov25_raw.yaml

# 2. Generate manifest for quarterly file
python scripts/url_to_manifest.py \
  "https://www.england.nhs.uk/.../quarterly-q3-2025.xls" \
  manifests/test_ae_quarterly_q325_raw.yaml

# 3. Load both
datawarp load-batch manifests/test_ae_monthly_nov25_raw.yaml
datawarp load-batch manifests/test_ae_quarterly_q325_raw.yaml

# 4. Check separate canonical codes
psql -h localhost -U databot_dev_user -d databot_dev -c "
  SELECT
    canonical_code,
    canonical_name,
    canonical_table,
    COUNT(*) OVER (PARTITION BY canonical_code) as load_count
  FROM datawarp.tbl_canonical_sources
  WHERE canonical_code LIKE 'ae%'
  ORDER BY canonical_code;
"

# 5. Check metadata distinguishes granularity
psql -h localhost -U databot_dev_user -d databot_dev -c "
  SELECT
    canonical_code,
    metadata->>'frequency' as frequency,
    metadata->>'granularity' as granularity
  FROM datawarp.tbl_data_sources
  WHERE code LIKE 'ae%';
"
```

**Evidence to Collect:**
- [ ] Separate canonical codes for monthly vs quarterly
- [ ] Metadata shows frequency (monthly, quarterly, annual)
- [ ] No accidental merging of different granularities
- [ ] Clear table naming convention (ae_monthly_xxx vs ae_quarterly_xxx)

**Success Criteria:**
- Monthly and quarterly files tracked separately
- Metadata clearly distinguishes granularity
- No accidental consolidation across granularities
- Can query monthly vs quarterly data independently

---

## Test Scenario 5: Mixed File Types + Dynamic Content

**Test URLs:**
- November 2025: https://digital.nhs.uk/data-and-information/publications/statistical/patients-registered-at-a-gp-practice/november-2025
- October 2025: https://digital.nhs.uk/data-and-information/publications/statistical/patients-registered-at-a-gp-practice/october-2025

**Challenge:**
- Mixed file types: ZIP, XLSX, CSV within same publication
- Files change dynamically (can't hardcode URLs)
- Time series files that update cumulatively (e.g., "Supplementary ECDS Analysis Time Series February 2023 Onwards")
- Need to discover what files exist each period

**Expected Behavior:**
1. url_to_manifest scrapes page for all downloadable links
2. Filters for Excel/CSV/ZIP files
3. Extracts file metadata (name, size, format)
4. Handles ZIP files (extract contents, process each file)
5. Time series files detected (span multiple periods in filename)
6. Dynamic discovery each month (don't assume same files exist)

**Validation Steps:**
```bash
# 1. Generate manifest for November
python scripts/url_to_manifest.py \
  "https://digital.nhs.uk/.../patients-registered-at-a-gp-practice/november-2025" \
  manifests/test_gp_reg_nov25_raw.yaml

# 2. Check discovered files
cat manifests/test_gp_reg_nov25_raw.yaml | grep "url:" | wc -l
cat manifests/test_gp_reg_nov25_raw.yaml | grep "url:"

# 3. Generate manifest for October
python scripts/url_to_manifest.py \
  "https://digital.nhs.uk/.../patients-registered-at-a-gp-practice/october-2025" \
  manifests/test_gp_reg_oct25_raw.yaml

# 4. Compare file lists (identify new/missing files)
diff <(cat manifests/test_gp_reg_oct25_raw.yaml | grep "url:" | sort) \
     <(cat manifests/test_gp_reg_nov25_raw.yaml | grep "url:" | sort)

# 5. Load both periods
datawarp load-batch manifests/test_gp_reg_oct25_raw.yaml
datawarp load-batch manifests/test_gp_reg_nov25_raw.yaml

# 6. Check for new files in November
psql -h localhost -U databot_dev_user -d databot_dev -c "
  SELECT
    cs.canonical_code,
    cs.canonical_name,
    cs.first_seen_period,
    COUNT(DISTINCT sm.period) as period_count
  FROM datawarp.tbl_canonical_sources cs
  LEFT JOIN datawarp.tbl_source_mappings sm
    ON cs.canonical_code = sm.canonical_code
  WHERE cs.canonical_code LIKE 'gp_reg%'
  GROUP BY cs.canonical_code, cs.canonical_name, cs.first_seen_period
  ORDER BY cs.first_seen_period DESC;
"

# 7. Check ZIP file handling
cat manifests/test_gp_reg_nov25_raw.yaml | grep "\.zip"
# Expected: ZIP files extracted, contents listed as separate sources

# 8. Check time series file handling
cat manifests/test_gp_reg_nov25_raw.yaml | grep -i "time series"
# Expected: Detected as cumulative (spans multiple periods)
```

**Evidence to Collect:**
- [ ] List of all files discovered in November
- [ ] List of all files discovered in October
- [ ] Diff showing new files in November vs October
- [ ] ZIP files extracted correctly
- [ ] Time series files flagged with metadata
- [ ] Canonical codes created for new files only
- [ ] Drift events logged for new file discoveries

**Success Criteria:**
- Discovers all files dynamically (doesn't hardcode)
- Handles ZIP, XLSX, CSV in same publication
- Detects new files month-to-month
- Time series files identified (metadata flag)
- No crashes on mixed file types
- Clear logging of what was discovered

**Open Questions:**
1. **Time Series Files:** Should we load cumulative time series every month, or only when updated?
2. **ZIP Files:** Assume all files in ZIP are related, or treat independently?
3. **File Disappearance:** What if October file doesn't exist in November (deprecated)?

**Recommended Answers:**
1. Load time series files every month, but fingerprint will match (same canonical code)
2. Treat independently - each file in ZIP gets own canonical code
3. Mark as deprecated in canonical_sources table (add `deprecated_at` column?)

---

## Integration Testing Workflow

**Complete End-to-End Test:**

```bash
#!/bin/bash
# Phase 1 End-to-End Test Suite

# Test 1: Wide Date Pivoting
echo "=== Test 1: Wide Date Pivoting ==="
python scripts/url_to_manifest.py \
  "https://digital.nhs.uk/.../pcn-workforce/30-november-2025" \
  manifests/test1_pcn_nov25.yaml
datawarp load-batch manifests/test1_pcn_nov25.yaml

# Test 2: Missing Periods + Schema Drift
echo "=== Test 2: Missing Periods + Schema Drift ==="
python scripts/url_to_manifest.py \
  "https://digital.nhs.uk/.../mi-adhd/august-2025" \
  manifests/test2_adhd_aug25.yaml
python scripts/enrich.py manifests/test2_adhd_aug25.yaml manifests/test2_adhd_aug25_enriched.yaml
python scripts/apply_enrichment.py \
  manifests/test2_adhd_aug25_enriched.yaml \
  manifests/test2_adhd_aug25_enriched_llm_response.json \
  manifests/test2_adhd_aug25_canonical.yaml
datawarp load-batch manifests/test2_adhd_aug25_canonical.yaml

python scripts/url_to_manifest.py \
  "https://digital.nhs.uk/.../mi-adhd/november-2025" \
  manifests/test2_adhd_nov25.yaml
python scripts/enrich.py manifests/test2_adhd_nov25.yaml manifests/test2_adhd_nov25_enriched.yaml
python scripts/apply_enrichment.py \
  manifests/test2_adhd_nov25_enriched.yaml \
  manifests/test2_adhd_nov25_enriched_llm_response.json \
  manifests/test2_adhd_nov25_canonical.yaml
datawarp load-batch manifests/test2_adhd_nov25_canonical.yaml

# Test 3: Historical Backfill
echo "=== Test 3: Historical Backfill ==="
python scripts/url_to_manifest.py \
  "https://www.england.nhs.uk/.../msa-data-october-2026" \
  manifests/test3_msa_oct26.yaml
datawarp load-batch manifests/test3_msa_oct26.yaml

# Test 4: Multiple File Types
echo "=== Test 4: Multiple File Types ==="
# TODO: Extract specific file URLs from A&E page

# Test 5: Mixed File Types + Dynamic Content
echo "=== Test 5: Mixed File Types + Dynamic Content ==="
python scripts/url_to_manifest.py \
  "https://digital.nhs.uk/.../patients-registered-at-a-gp-practice/november-2025" \
  manifests/test5_gp_reg_nov25.yaml
datawarp load-batch manifests/test5_gp_reg_nov25.yaml

python scripts/url_to_manifest.py \
  "https://digital.nhs.uk/.../patients-registered-at-a-gp-practice/october-2025" \
  manifests/test5_gp_reg_oct25.yaml
datawarp load-batch manifests/test5_gp_reg_oct25.yaml

# Validation Queries
echo "=== Validation Queries ==="
psql -h localhost -U databot_dev_user -d databot_dev << EOF
-- Canonical sources created
SELECT COUNT(*) as total_canonical_sources
FROM datawarp.tbl_canonical_sources;

-- Cross-period consolidation
SELECT
  canonical_code,
  COUNT(DISTINCT period) as period_count
FROM datawarp.tbl_source_mappings
GROUP BY canonical_code
HAVING COUNT(DISTINCT period) > 1;

-- Drift events
SELECT drift_type, COUNT(*)
FROM datawarp.tbl_drift_events
GROUP BY drift_type;

-- Fingerprint match quality
SELECT
  CASE
    WHEN match_confidence >= 0.95 THEN 'Excellent (0.95+)'
    WHEN match_confidence >= 0.80 THEN 'Good (0.80-0.95)'
    WHEN match_confidence >= 0.60 THEN 'Fair (0.60-0.80)'
    ELSE 'Poor (<0.60)'
  END as match_quality,
  COUNT(*)
FROM datawarp.tbl_source_mappings
GROUP BY 1;
EOF
```

---

## Questions to Answer Before Phase 1 Sign-Off

### 1. Missing Period Handling
**Question:** What happens when September ADHD is missing?
**Options:**
- A) System logs warning, continues with next period
- B) System marks period as "expected but missing" in tracking table
- C) System sends alert email

**Recommendation:** Option B - track expected but missing periods for monitoring

### 2. Schema Drift - New Files
**Question:** November ADHD has new file not in August. How to handle?
**Options:**
- A) Automatically create new canonical code
- B) Alert user for manual review first
- C) Try to match to existing sources via fingerprinting

**Recommendation:** Option A + log drift event for review

### 3. Wide Date Detection Threshold
**Question:** How many date columns needed to trigger pivoting?
**Options:**
- A) 2+ columns
- B) 3+ columns (current)
- C) 5+ columns

**Recommendation:** Option B (3+) - prevents false positives on Age 0-4, Age 5-17

### 4. Fingerprint Match Threshold
**Question:** What confidence score is acceptable?
**Options:**
- A) 0.95+ (exact match only)
- B) 0.80+ (current)
- C) 0.70+ (more permissive)

**Recommendation:** Option B (0.80) with manual review queue for 0.70-0.80

### 5. Multiple File Types
**Question:** How to distinguish monthly vs quarterly A&E data?
**Options:**
- A) Separate canonical codes (ae_monthly_xxx vs ae_quarterly_xxx)
- B) Same canonical code, metadata field distinguishes
- C) Manual user input during registration

**Recommendation:** Option A - cleaner separation, easier to query

---

## Success Metrics

Phase 1 is complete when:

- [ ] All 4 test scenarios pass
- [ ] Evidence collected for each scenario
- [ ] Database queries confirm cross-period consolidation
- [ ] Drift events logged correctly
- [ ] No crashes or data loss
- [ ] Questions above answered and documented
- [ ] User approves approach

---

## Next Steps

1. **Run Test Scenario 2 first** (ADHD Aug/Nov) - simplest, no pivoting
2. **Collect evidence** - screenshots, database dumps, logs
3. **Document findings** - what worked, what broke
4. **Refine approach** - adjust based on real data
5. **Repeat** for other scenarios
6. **User review** - show evidence, get sign-off

---

**Update This File:** After each test run with results and evidence
