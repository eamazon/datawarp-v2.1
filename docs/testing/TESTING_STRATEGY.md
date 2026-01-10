# DataWarp v2.1 Testing Strategy

**Date:** 2026-01-10
**Status:** Proposed (Awaiting Implementation)
**Problem:** No systematic testing, manifest chaos, inconsistent canonical workflow usage

---

## Current State Assessment

### ❌ Problems Identified

1. **Minimal Test Coverage**
   - Only 10 test functions across 4 test files
   - No integration tests for full pipeline
   - No validation tests for enrichment quality
   - No regression tests for schema stability

2. **Manifest Chaos**
   - 16 YAML files in root manifests/ directory
   - Mixed raw, enriched, canonical in same folder
   - Archive folders with unclear purpose (`archive_test_20260108_231700`)
   - No clear "test" vs "production" manifests
   - No naming convention enforcement

3. **Inconsistent Canonical Workflow**
   - `apply_enrichment.py` exists but not consistently used
   - Some sources use raw → enriched → load
   - Others use raw → enriched → canonical → load
   - No enforcement of which workflow to use when

4. **No Systematic Validation**
   - No automated checks after enrichment
   - No validation after loading
   - No regression detection
   - Manual ad-hoc testing only

5. **Scale & Variety Not Tested**
   - Different NHS publication types not systematically covered
   - URL variations (direct Excel, ZIP, CSV) not tested comprehensively
   - Edge cases (missing sheets, malformed data) not captured

---

## Testing Philosophy

### Generic System, Niche Solution Principle

**Generic System Components** (must be stable):
- File extraction (Excel, CSV, ZIP)
- Schema detection (headers, types, boundaries)
- DDL generation (CREATE/ALTER TABLE)
- Data insertion (type casting, batch inserts)
- Drift detection (column comparison)

**Niche Solution Components** (can evolve):
- NHS-specific patterns (multi-tier headers, suppressions)
- LLM enrichment prompts
- Reference-based enrichment
- Publication-specific transformations (unpivot)

**Testing Approach:**
- **Heavy testing on generic components** - These MUST be stable
- **Smoke testing on niche components** - These can evolve based on new patterns
- **Golden dataset regression** - Core publications must always work

---

## Test Pyramid

```
                    /\
                   /  \
                  / E2E \ (10 tests)
                 /      \
                /────────\
               /          \
              / Integration\ (30 tests)
             /             \
            /───────────────\
           /                 \
          /   Unit Tests      \ (100+ tests)
         /                     \
        /───────────────────────\
```

### Layer 1: Unit Tests (~100 tests)
**Focus:** Individual functions, deterministic behavior

**Coverage:**
- `core/extractor.py`:
  - Header detection (single-tier, multi-tier, merged cells)
  - Type inference (keywords, data sampling)
  - Footer detection
  - Sheet classification
  - Date pattern detection

- `utils/schema.py`:
  - `to_schema_name()` determinism
  - Collision detection
  - Reserved word handling
  - Wide date pattern matching

- `loader/ddl.py`:
  - Type mapping (VARCHAR, INTEGER, NUMERIC, DATE)
  - CREATE TABLE generation
  - ALTER TABLE generation

- `loader/insert.py`:
  - Type casting (integers, decimals, dates)
  - NULL handling
  - Suppression symbol conversion (* → NULL)

- `transform/unpivot.py`:
  - Wide→Long transformation
  - Date column parsing
  - Column ordering

**Test Data:** Small, synthetic datasets (10-50 rows)

**Run Frequency:** Every commit (fast, <10 seconds total)

---

### Layer 2: Integration Tests (~30 tests)
**Focus:** End-to-end workflow stages, real NHS data patterns

**Coverage:**

**A. Extraction Integration (10 tests)**
- Real NHS Excel files with various patterns
- Multi-sheet workbooks
- ZIP archives with multiple CSVs
- Merged cell handling
- NHS-specific suppressions

**B. Enrichment Integration (5 tests)**
- LLM enrichment (Gemini, Qwen)
- Reference-based enrichment
- Enrichment validation (codes, columns)
- Error handling (malformed LLM responses)
- Fallback to deterministic naming

**C. Loading Integration (10 tests)**
- Schema creation
- Schema evolution (drift)
- Cross-period consolidation
- Metadata storage
- Audit trail completeness

**D. Export Integration (5 tests)**
- Parquet generation
- Companion .md file accuracy
- Metadata propagation
- Catalog building

**Test Data:** Real NHS publications (1-5 sources per test)

**Run Frequency:** Before merge to main (moderate, ~2 minutes total)

---

### Layer 3: E2E Tests (~10 tests)
**Focus:** Full publication workflows, golden datasets

**Coverage:**

**Golden Datasets (Must Always Work):**
1. **ADHD Aug 2025** (11 sources)
   - url_to_manifest → enrich → load → export → validate
   - Expectation: 11/11 sources exported, 6/6 validation tests pass

2. **ADHD Nov 2025** (reference-based)
   - url_to_manifest → enrich (--reference Aug) → load → export → validate
   - Expectation: 93% code consistency, cross-period consolidation works

3. **GP Appointments Nov 2025** (90 sources)
   - url_to_manifest → enrich → load
   - Expectation: 90% success rate, large-scale stability

4. **PCN Workforce** (8 sources)
   - url_to_manifest → enrich → load → export
   - Expectation: Unpivot transformation works, wide dates handled

5. **Minimal Synthetic** (3 sources)
   - Simple CSV, simple Excel, ZIP with 2 CSVs
   - Expectation: 100% success, baseline correctness

**Regression Prevention:**
- These tests MUST pass on every release
- If one fails, it's a blocker
- If adding a new publication to golden set, it must maintain pass rate

**Test Data:** Real NHS publications (full-scale)

**Run Frequency:** Before release (slow, ~10 minutes total)

---

## Test Organization

### Directory Structure

```
datawarp-v2.1/
├── tests/
│   ├── unit/                          # Layer 1: Fast, deterministic
│   │   ├── test_extractor.py
│   │   ├── test_schema.py
│   │   ├── test_ddl.py
│   │   ├── test_insert.py
│   │   ├── test_unpivot.py
│   │   └── test_drift.py
│   │
│   ├── integration/                   # Layer 2: Real data patterns
│   │   ├── test_extraction.py         # Real NHS Excel/CSV/ZIP
│   │   ├── test_enrichment.py         # LLM + reference-based
│   │   ├── test_loading.py            # Schema evolution, cross-period
│   │   └── test_export.py             # Parquet + metadata
│   │
│   ├── e2e/                           # Layer 3: Full workflows
│   │   ├── test_golden_adhd_aug25.py
│   │   ├── test_golden_adhd_nov25.py
│   │   ├── test_golden_gp_appts.py
│   │   ├── test_golden_pcn_workforce.py
│   │   └── test_regression.py         # All golden datasets together
│   │
│   └── fixtures/                      # Test data
│       ├── synthetic/                 # Small, controlled datasets
│       │   ├── simple.csv
│       │   ├── multi_header.xlsx
│       │   └── merged_cells.xlsx
│       │
│       ├── nhs_samples/               # Real NHS data (small excerpts)
│       │   ├── adhd_table_1.xlsx
│       │   ├── gp_appointments.csv
│       │   └── pcn_workforce.xlsx
│       │
│       └── expectations/              # Expected outputs
│           ├── adhd_table_1_expected.json
│           └── gp_appointments_expected.json
│
├── manifests/
│   ├── production/                    # Actual NHS publications
│   │   ├── adhd/
│   │   │   ├── adhd_aug25_enriched.yaml
│   │   │   └── adhd_nov25_canonical.yaml
│   │   ├── gp_appointments/
│   │   │   └── gp_appointments_nov25_enriched.yaml
│   │   └── pcn_workforce/
│   │       └── pcn_workforce_nov25_enriched.yaml
│   │
│   ├── test/                          # Test manifests
│   │   ├── synthetic_simple.yaml
│   │   └── nhs_sample_adhd.yaml
│   │
│   └── archive/                       # Old manifests (timestamped)
│       └── 2026-01-08/
│           └── adhd_aug25_v1.yaml
│
└── scripts/
    └── validate_manifest.py           # NEW: Validation script
```

---

## Validation Framework

### Stage 1: Post-Manifest Generation (url_to_manifest.py)

**File:** `scripts/validate_manifest.py` (NEW)

**Checks:**
1. ✅ YAML is valid (parseable)
2. ✅ All required fields present (code, name, table, files)
3. ✅ No duplicate source codes
4. ✅ File URLs are reachable (HTTP 200)
5. ✅ Sheet names exist in Excel files (if specified)
6. ⚠️ Warn if generic codes (e.g., "table_1a")

**Run:** `python scripts/validate_manifest.py manifests/adhd_aug25.yaml`

---

### Stage 2: Post-Enrichment (enrich_manifest.py)

**Built into enrich_manifest.py** (already partially exists):

**Checks:**
1. ✅ All file URLs preserved (no loss)
2. ✅ Source count reasonable (consolidation acceptable, but not >50% reduction)
3. ✅ All enabled sources have: code, name, table, description
4. ✅ Column metadata present (if LLM enrichment used)
5. ⚠️ Warn if high output/input token ratio (>5×)
6. ⚠️ Warn if codes still generic after enrichment

**Auto-run:** At end of enrich_manifest.py (already implemented)

---

### Stage 3: Post-Loading (load-batch)

**File:** `scripts/validate_loaded_data.py` (NEW)

**Checks:**
1. ✅ Row counts match expectations (within 10%)
2. ✅ No empty tables
3. ✅ All columns have correct types (no all-NULL columns)
4. ✅ Audit columns present (`_load_id`, `_period`, `_loaded_at`)
5. ✅ Metadata stored in `tbl_column_metadata` (if enriched)
6. ✅ Cross-period data coexists (if reference-based)
7. ⚠️ Warn if high NULL rates (>50%)

**Run:** `python scripts/validate_loaded_data.py adhd_summary_open_referrals_age`

---

### Stage 4: Post-Export (export_to_parquet.py)

**File:** `scripts/validate_parquet_export.py` (NEW)

**Checks:**
1. ✅ Parquet file created
2. ✅ Companion .md file created
3. ✅ Row count matches database
4. ✅ Column count matches database
5. ✅ Metadata in .md matches database
6. ✅ Column names in Parquet match database (fuzzy)
7. ⚠️ Warn if file size >50MB (performance concern)

**Run:** `python scripts/validate_parquet_export.py output/adhd_summary_open_referrals_age.parquet`

---

## Regression Test Suite

### Golden Dataset Registry

**File:** `tests/e2e/golden_datasets.yaml`

```yaml
golden_datasets:
  - name: adhd_aug25
    manifest: manifests/production/adhd/adhd_aug25_enriched.yaml
    expectations:
      sources_total: 11
      sources_enabled: 11
      load_success_rate: 1.0  # 100%
      export_success_rate: 1.0
      validation_tests_pass: 6
      total_rows_min: 1000
      total_rows_max: 5000

  - name: adhd_nov25_reference
    manifest: manifests/production/adhd/adhd_nov25_canonical.yaml
    reference: manifests/production/adhd/adhd_aug25_enriched.yaml
    expectations:
      code_consistency: 0.90  # 90%+ match
      cross_period_tables: 11  # Aug + Nov in same tables
      load_success_rate: 0.75  # 75%+ (some new tables expected to fail)

  - name: gp_appointments_nov25
    manifest: manifests/production/gp_appointments/gp_appointments_nov25_enriched.yaml
    expectations:
      sources_total: 90
      load_success_rate: 0.90  # 90%+ (large scale)
      metadata_coverage: 0  # No column metadata yet (just structure)
```

### Regression Test Runner

**File:** `tests/e2e/test_regression.py`

```python
import yaml
import pytest
from pathlib import Path

def load_golden_datasets():
    with open('tests/e2e/golden_datasets.yaml') as f:
        return yaml.safe_load(f)['golden_datasets']

@pytest.mark.parametrize("golden", load_golden_datasets())
def test_golden_dataset(golden):
    """Test each golden dataset against expectations."""

    name = golden['name']
    manifest_path = golden['manifest']
    expectations = golden['expectations']

    # Run full pipeline
    result = run_pipeline(manifest_path, golden.get('reference'))

    # Validate expectations
    assert result.sources_total == expectations['sources_total']
    assert result.load_success_rate >= expectations['load_success_rate']
    # ... more assertions
```

**Run:** `pytest tests/e2e/test_regression.py -v`

---

## Canonical Workflow Governance

### When to Use Which Workflow

**Decision Tree:**

```
Is this the FIRST period of a publication?
│
├─ YES → Use: url_to_manifest → enrich → load
│   (No reference needed, LLM creates semantic names)
│
└─ NO → Use: url_to_manifest → enrich --reference → load
    (Reference-based enrichment for consistency)
```

**Enforcement:**

1. **Naming Convention:**
   - First period: `{publication}_{period}_enriched.yaml`
   - Subsequent periods: `{publication}_{period}_canonical.yaml`

2. **Pre-commit Hook:**
   ```bash
   # Check if canonical.yaml exists without reference
   if [[ $file == *"_canonical.yaml" ]]; then
       if ! grep -q "reference:" enrich_log.txt; then
           echo "ERROR: Canonical manifest must use --reference flag"
           exit 1
       fi
   fi
   ```

3. **Documentation:**
   - Update CLAUDE.md with clear workflow decision tree
   - Add example commands for each scenario

---

## Scale & Variety Testing Matrix

### Real-World NHS Test URLs (Production Test Suite)

**Updated: 2026-01-10**

These URLs represent the core test suite for rigorous validation. They cover various challenges (schema drift, missing months, mixed formats, date pivoting).

#### 1. NHS Workforce Statistics (Baseline - Complex Scale)
- **Aug 2025:** `https://digital.nhs.uk/data-and-information/publications/statistical/nhs-workforce-statistics/august-2025`
  - 76 sources, 106 files (XLSX + ZIP + CSV)
  - Status: ✅ Manifest generated, 100% URL reachability validated
  - Complexity: Multiple Excel files, ZIPs with CSVs, wide variety of sheet structures

#### 2. Primary Care Network Workforce (Schema Drift + Date Pivoting)
- **Nov 2025:** `https://digital.nhs.uk/data-and-information/publications/statistical/primary-care-network-workforce/30-november-2025`
- **Oct 2025:** `https://digital.nhs.uk/data-and-information/publications/statistical/primary-care-network-workforce/31-october-2025`
  - Challenge: Schema drift across periods, wide date columns requiring unpivot
  - Status: ⏳ Pending test

#### 3. ADHD (Missing Months + New Files + Schema Drift)
- **Aug 2025:** `https://digital.nhs.uk/data-and-information/publications/statistical/mi-adhd/august-2025`
- **Nov 2025:** `https://digital.nhs.uk/data-and-information/publications/statistical/mi-adhd/november-2025`
  - Challenge: September 2025 publication missing, new files appear in November, schema drift
  - Status: ✅ Golden (from previous sessions)

#### 4. Mixed Sex Accommodation (Historical Data)
- **URL:** `https://www.england.nhs.uk/statistics/statistical-work-areas/mixed-sex-accommodation/msa-data/`
  - Challenge: Historical data from 2010-2011 to October 2026, monthly updates
  - Status: ⏳ Pending test

#### 5. A&E Waiting Times (Multiple File Types)
- **URL:** `https://www.england.nhs.uk/statistics/statistical-work-areas/ae-waiting-times-and-activity/`
  - Challenge: Monthly data files + 3 supplementary files (time series, quarterly, ECDS analysis)
  - Status: ⏳ Pending test

#### 6. GP Practice Registrations (Mixed Formats)
- **Nov 2025:** `https://digital.nhs.uk/data-and-information/publications/statistical/patients-registered-at-a-gp-practice/november-2025`
- **Oct 2025:** `https://digital.nhs.uk/data-and-information/publications/statistical/patients-registered-at-a-gp-practice/october-2025`
  - Challenge: Mixture of ZIP files, XLSX files, CSV files requiring careful iteration
  - Dynamic file links (cannot genericize URLs within parent)
  - Status: ⏳ Pending test

#### 7. Primary Care Dementia Data (Rich Metadata)
- **Jul 2025:** `https://digital.nhs.uk/data-and-information/publications/statistical/primary-care-dementia-data/july-2025`
- **Jun 2025:** `https://digital.nhs.uk/data-and-information/publications/statistical/primary-care-dementia-data/june-2025`
  - Challenge: Publication summary has rich metadata, multiple file varieties
  - Currently ignoring page metadata - need to determine if useful for extraction
  - Status: ⏳ Pending test

#### 8. Patients Registered at GP (Additional Metadata Test)
- **Aug 2025:** `https://digital.nhs.uk/data-and-information/publications/statistical/patients-registered-at-a-gp-practice/august-2025`
- **Jul 2025:** `https://digital.nhs.uk/data-and-information/publications/statistical/patients-registered-at-a-gp-practice/july-2025`
  - Challenge: Similar to #6, publication summary has rich contextual information
  - Status: ⏳ Pending test

### Legacy Publication Types to Test

| Publication | Type | URL Pattern | Scale | Complexity | Status |
|-------------|------|-------------|-------|------------|--------|
| ADHD Aug 25 | Excel | Direct | 11 sources | Multi-tier headers | ✅ Golden |
| ADHD Nov 25 | Excel | Direct | 28 sources | Multi-tier + new tables | ✅ Golden |
| GP Appointments | ZIP | Multi-CSV | 90 sources | Regional breakdowns | ✅ Golden |
| PCN Workforce | Excel | Direct | 8 sources | Wide dates (unpivot) | ✅ Golden |
| NHS Workforce | XLSX+ZIP | Multi-format | 76 sources | Complex scale | ✅ Tested (2026-01-10) |

### Edge Cases to Test

| Edge Case | Description | Test File | Status |
|-----------|-------------|-----------|--------|
| Empty sheet | Sheet with headers but no data | synthetic/empty_sheet.xlsx | ⏳ TODO |
| All suppressed | All values are * or - | synthetic/all_suppressed.xlsx | ⏳ TODO |
| No headers | Data starts at row 1 | synthetic/no_headers.csv | ⏳ TODO |
| Unicode | Column names with £, %, etc. | nhs_samples/unicode_cols.xlsx | ⏳ TODO |
| Very wide | 100+ columns | synthetic/very_wide.csv | ⏳ TODO |
| Very long | 100K+ rows | synthetic/very_long.csv | ⏳ TODO |
| Missing values | 90%+ NULL rate | synthetic/mostly_null.csv | ⏳ TODO |
| Type confusion | "123" vs 123 in same column | synthetic/mixed_types.xlsx | ⏳ TODO |

---

## Implementation Plan

### Phase 1: Foundation (Week 1)
1. ✅ Create test directory structure
2. ✅ Move existing tests to unit/
3. ✅ Organize manifests into production/test/archive
4. ✅ Create validation scripts (validate_manifest.py, validate_loaded_data.py, validate_parquet_export.py)
5. ✅ Document canonical workflow in CLAUDE.md

### Phase 2: Core Tests (Week 2)
6. ✅ Write unit tests for schema.py (to_schema_name, collision detection)
7. ✅ Write unit tests for extractor.py (header detection, type inference)
8. ✅ Write integration test for extraction (real NHS samples)
9. ✅ Write integration test for enrichment (LLM + reference)
10. ✅ Create golden_datasets.yaml registry

### Phase 3: Regression Suite (Week 3)
11. ✅ Implement test_regression.py (parametrized golden datasets)
12. ✅ Add pre-commit hook for manifest validation
13. ✅ Create CI/CD workflow (GitHub Actions)
14. ✅ Document testing workflow in TESTING_STRATEGY.md

### Phase 4: Scale & Edge Cases (Ongoing)
15. ⏳ Add edge case test files
16. ⏳ Test new publications (Dementia, Maternity)
17. ⏳ Performance benchmarking
18. ⏳ Load testing (1M+ rows)

---

## Success Metrics

**Weekly:**
- All unit tests pass (<10s runtime)
- All integration tests pass (<2min runtime)

**Before Release:**
- All E2E tests pass (<10min runtime)
- Golden datasets maintain expected success rates
- No regression in core publications (ADHD, GP Appointments)

**Monthly:**
- Add 1 new golden dataset
- Improve test coverage by 10%
- Reduce flaky tests to 0

---

## Fiscal Year-Aware Testing Protocol

**Updated: 2026-01-10**

### NHS Fiscal Year Context

**Fiscal Year:** April 1 - March 31
- **March:** End of FY - Final reporting period (stable baseline)
- **April:** Start of FY - **MAJOR schema changes expected** (new metrics, org changes)
- **May:** Post-transition stabilization
- **October:** Mid-year - incremental changes

### Recommended Test Sequence (Per Publication)

```
October 2024  (Mid-year historical)
    ↓
March 2025    (FY 2024/25 end - BASELINE)
    ↓
April 2025    (FY 2025/26 start - FISCAL TRANSITION - schema breaks expected)
    ↓
May 2025      (Stabilization - schema should lock)
```

### Expected Schema Drift Patterns

| Transition | Expected Changes | Risk Level | Validation Strategy |
|------------|------------------|------------|---------------------|
| March→April (Fiscal) | 20-40% new columns, 10-20% removed, 5-10% new tables | 🔴 HIGH | Manual validation, reference-based enrichment |
| April→May (Stabilization) | 0-5% new columns, data quality fixes | 🟢 LOW | Automated validation |
| May→October (Mid-year) | 5-10% new columns, minor org changes | 🟡 MEDIUM | Reference-based enrichment |

### Fiscal Testing Commands

```bash
# Generate fiscal-aligned manifests
python scripts/url_to_manifest.py <mar25_url> manifests/test/fiscal/baseline/pub_mar25.yaml
python scripts/url_to_manifest.py <apr25_url> manifests/test/fiscal/fy_transition/pub_apr25.yaml
python scripts/url_to_manifest.py <may25_url> manifests/test/fiscal/stabilization/pub_may25.yaml

# Compare fiscal periods (detect schema changes)
python scripts/compare_manifests.py \
  manifests/test/fiscal/baseline/pub_mar25.yaml \
  manifests/test/fiscal/fy_transition/pub_apr25.yaml \
  --fiscal-boundary

# Enrich with fiscal awareness
python scripts/enrich_manifest.py \
  manifests/test/fiscal/fy_transition/pub_apr25.yaml \
  manifests/test/fiscal/fy_transition/pub_apr25_canonical.yaml \
  --reference manifests/test/fiscal/baseline/pub_mar25_enriched.yaml

# Load and validate cross-fiscal consolidation
datawarp load-batch manifests/test/fiscal/fy_transition/pub_apr25_canonical.yaml

# Check for schema drift
psql -h localhost -U databot_dev_user -d databot_dev -c "
SELECT source_code, COUNT(*) as columns_added
FROM datawarp.tbl_drift_events
WHERE detected_at > NOW() - INTERVAL '1 day'
GROUP BY source_code;"
```

### Fiscal Test Results (2026-01-10)

**PCN Workforce (Oct 2024 → Mar 2025 → Apr 2025 → May 2025):**
- ✅ 100% schema stability across all periods (11 sources)
- ✅ No fiscal year boundary changes detected
- ✅ Mature, stable publication
- **Conclusion:** Suitable for regression baseline

---

## Appendix: Test Commands

```bash
# Run all tests
pytest tests/ -v

# Run only unit tests (fast)
pytest tests/unit/ -v

# Run only integration tests
pytest tests/integration/ -v

# Run only golden dataset regression
pytest tests/e2e/test_regression.py -v

# Run specific test
pytest tests/unit/test_schema.py::test_to_schema_name_determinism -v

# Validate manifest
python scripts/validate_manifest.py manifests/adhd_aug25.yaml

# Validate loaded data
python scripts/validate_loaded_data.py adhd_summary_open_referrals_age

# Validate Parquet export
python scripts/validate_parquet_export.py output/adhd_summary_open_referrals_age.parquet

# Compare two manifests (fiscal transitions)
python scripts/compare_manifests.py manifest1.yaml manifest2.yaml --fiscal-boundary

# Run pre-commit checks
pre-commit run --all-files
```

---

**Last Updated:** 2026-01-10
**Status:** In Progress - Fiscal Testing Validated
**Owner:** User + Claude Code
**Estimated Effort:** 3 weeks (phased implementation)
