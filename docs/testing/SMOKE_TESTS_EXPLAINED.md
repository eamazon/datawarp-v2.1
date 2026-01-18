# Smoke Tests Explained

**Created: 2026-01-18**
**Purpose: Answer "How do smoke tests work and why do we need them forever?"**

---

## TL;DR

**YES, you MUST keep running tests after features are complete.**

This is called **regression testing** - it prevents future changes from breaking old features.

---

## How Smoke Tests Work

### Two Test Suites (12 tests total, < 30 seconds)

#### 1. E2E Smoke Tests (`test_e2e_smoke.py`) - 6 tests

**What they test:** Integrated system state

| Test | What It Checks | Can Skip? |
|------|----------------|-----------|
| test_stage1_manifest_structure | ADHD manifest file exists and valid | ✅ Yes (if file missing) |
| test_stage2_enrichment_preserves_columns | Enriched manifest has column metadata | ✅ Yes (if file missing) |
| test_stage3_database_sources | ADHD sources in database | ✅ Yes (if DB not available) |
| test_stage4_metadata_storage | Metadata in tbl_column_metadata | ⚠️ Partial (FAILS if sources exist without metadata) |
| test_critical_field_mapping | Field mapping logic correct | ❌ Never (unit test) |
| test_imports_not_broken | Core imports work | ❌ Never (unit test) |

**Limitation:** Most tests check that old data is valid, not that pipeline can RUN.

#### 2. Unit Smoke Tests (`test_smoke_unit.py`) - 6 tests

**What they test:** Core logic (no dependencies)

| Test | What It Validates | Dependencies | Speed |
|------|-------------------|--------------|-------|
| test_field_mapping_all_variants | New + legacy field name handling | None | 0.001s |
| test_enrichment_required_fields | All 7 metadata fields required | None | 0.001s |
| test_manifest_structure_validation | YAML manifest structure | None | 0.001s |
| test_source_code_validation | Source code naming conventions | None | 0.001s |
| test_column_type_inference_keywords | Type inference logic | None | 0.001s |
| test_drift_detection_logic | Schema drift detection | None | 0.001s |

**Benefit:** ALWAYS run (no database, files, network). Catch code-level breakage instantly.

---

## What Pre-Commit Hook Does

```bash
# You run:
git commit -m "refactor: improve enrichment logic"

# Hook automatically runs:
📋 E2E Smoke Tests: (6 tests)
  ✅ test_stage1_manifest_structure (skipped - manifest missing)
  ✅ test_stage2_enrichment_preserves_columns (skipped)
  ✅ test_stage3_database_sources (skipped)
  ✅ test_stage4_metadata_storage (skipped)
  ✅ test_critical_field_mapping (PASSED)
  ✅ test_imports_not_broken (PASSED)

🧪 Unit Smoke Tests: (6 tests)
  ✅ test_field_mapping_all_variants (PASSED)
  ✅ test_enrichment_required_fields (PASSED)
  ✅ test_manifest_structure_validation (PASSED)
  ✅ test_source_code_validation (PASSED)
  ✅ test_column_type_inference_keywords (PASSED)
  ✅ test_drift_detection_logic (PASSED)

✅ All smoke tests passed - commit allowed

# Commit succeeds
```

**If any test FAILS:**
```
❌ COMMIT BLOCKED: Unit smoke tests failed

Core logic is broken. Please fix the issues above before committing.
```

---

## Why Tests Must Run FOREVER

### Real-World Examples

#### Example 1: The Metadata Disaster (That Actually Happened)

**Timeline:**
```
✅ Jan 10: Metadata tracking working perfectly
           - enricher.py correctly preserves columns
           - 48 columns stored for ADHD

📝 Jan 12: Developer refactors enricher.py for performance
           - Accidentally moves column copy AFTER preview strip
           - Creates bug: columns: [] (empty)

❌ Jan 15: User loads new data
           - NO metadata stored
           - tbl_column_metadata empty
           - CORE FEATURE BROKEN

🔧 Jan 18: Discover bug, spend 3 hours debugging
           - Three separate bugs found and fixed
           - Lost 6 days with broken metadata
```

**With smoke tests:**
```
✅ Jan 10: Metadata tracking working

📝 Jan 12: Developer refactors enricher.py
           git commit -m "refactor: improve performance"

❌ HOOK BLOCKS COMMIT:
   test_stage2_enrichment_preserves_columns FAILED
   ❌ CRITICAL: enricher.py not preserving columns!

🔧 Jan 12: Developer fixes immediately (5 minutes)
           Bug never enters codebase
           Zero downtime
```

**Impact:**
- Without tests: 6 days of broken metadata, 3 hours debugging
- With tests: 5 minutes to fix, zero downtime

#### Example 2: Library Update

**Scenario:**
```
✅ Today: Everything works with pandas 2.0.0

📝 Next month: Developer runs `pip install --upgrade pandas`
               pandas updates to 2.1.0
               New version changes CSV parsing behavior

❌ Result: extractor.py breaks
           Can't parse hierarchical headers
           Pipeline fails
```

**Without tests:**
```
Developer doesn't notice immediately
Discovers when trying to load data
Spends hours debugging "why did it stop working?"
Finally realizes pandas update broke it
```

**With tests:**
```
pip install --upgrade pandas
pytest tests/ # Run tests after upgrade

FAILED test_column_type_inference_keywords
  AssertionError: Expected VARCHAR, got object

Developer immediately knows:
- Pandas update broke something
- It's in type inference
- Rollback or fix before committing
```

#### Example 3: Refactoring Side Effects

**Scenario:**
```
You improve field mapping in repository.py:
  # Old code
  column_name = col.get('semantic_name') or col.get('code')

  # New code (trying to support 'name' field)
  column_name = col.get('code') or col.get('semantic_name')
```

**What breaks:**
```
Old code: Checks semantic_name FIRST (correct for legacy)
New code: Checks code FIRST (breaks for columns with both!)

Example column:
  {
    'semantic_name': 'reporting_period',
    'code': 'rp'  # Short code
  }

Old: Uses 'reporting_period' (correct)
New: Uses 'rp' (wrong!)
```

**Without tests:**
```
Code looks fine
Metadata stored with wrong names
Queries break
Data inconsistent across periods
```

**With tests:**
```
git commit -m "refactor: improve field mapping"

FAILED test_field_mapping_all_variants
  AssertionError: Expected 'reporting_period', got 'rp'

Immediately see the problem
Fix before committing
```

---

## The Testing Philosophy

### Tests Are NOT Just For Development

```
❌ WRONG THINKING:
"Feature is complete, tests passed, we're done."
"Don't need tests anymore, code is working."
"Tests are just for finding bugs during development."

✅ CORRECT THINKING:
"Feature is complete, NOW tests protect it forever."
"Tests are insurance against future changes."
"Every commit could break old features - tests catch it."
```

### The Lifecycle

```
Week 1: Write feature
        Write tests
        ✅ Tests pass

Week 5: Refactor for performance
        ✅ Tests pass (feature still works)

Week 10: Add new feature
         ✅ Tests pass (didn't break old features)

Month 6: Update dependencies
         ❌ Tests fail (pandas broke something)
         Fix before deploying

Year 2: Still running tests
        Still catching bugs
        Still preventing regressions
```

### Industry Standard

**Every major software project runs tests:**
- **On every commit** (pre-commit hooks)
- **On every PR** (CI/CD pipelines)
- **Before every release** (full test suites)
- **Forever** (tests never "retire")

**Examples:**
- Linux kernel: 40+ year old codebase, still running tests on every commit
- Django: Tests run for every contribution since 2005
- React: Pre-commit hooks block commits with failing tests

**Why:** Because code changes constantly, and tests are the only way to ensure old features keep working.

---

## Should We Increase Smoke Tests?

### Current Coverage: GOOD

✅ **What we test:**
- Import integrity
- Field mapping logic
- Enrichment required fields
- Manifest structure
- Source code validation
- Type inference
- Drift detection
- Database connectivity (when available)
- Metadata storage (when loaded)

❌ **What we DON'T test:**
- Actually running full pipeline end-to-end
- Downloading files
- Calling LLM API
- Loading new data

### Recommendation: KEEP AS-IS

**Why:**
1. **Speed matters** - 30 seconds is perfect for pre-commit
2. **Core logic covered** - All critical logic paths tested
3. **Full tests exist** - Gate 2 and 3 do comprehensive testing
4. **Adding more risks** - Slower tests = developers bypass hooks

**The balance:**
```
Pre-commit (30s):  Quick sanity - catch obvious breaks
Gate 2 (5min):     Core pubs - comprehensive validation
Gate 3 (15min):    Full suite - everything tested
```

**If you add more:**
- Keep them FAST (< 5 seconds each)
- Keep them PURE LOGIC (no network, no LLM, no large files)
- Focus on critical paths only

**Examples of good additions:**
```python
def test_source_code_uniqueness():
    """Test that source codes don't collide."""
    # Fast, pure logic

def test_period_parsing_logic():
    """Test period string parsing."""
    # Fast, pure logic
```

**Examples of BAD additions:**
```python
def test_download_actual_file():
    """Download real NHS file."""
    # SLOW (network), belongs in Gate 2

def test_llm_enrichment():
    """Call Gemini API."""
    # SLOW (API call), COSTS MONEY, belongs in Gate 2
```

---

## Summary

### Questions Answered

**Q: Do we need to increase smoke tests?**
A: Current coverage is good. Add more ONLY if:
   - Pure logic tests (no dependencies)
   - Very fast (< 5 seconds)
   - Critical path only

**Q: How do smoke tests work?**
A: Two suites:
   - E2E tests: Check integrated system state (may skip)
   - Unit tests: Check core logic (always run)
   - Both run automatically on every commit
   - Commit blocked if tests fail

**Q: Do we need tests after features are complete?**
A: **ABSOLUTELY YES!**
   - This is regression testing
   - Prevents future changes from breaking old features
   - Industry standard: tests run FOREVER
   - Real examples show huge value (6 days saved)

### The Bottom Line

```
Tests are INSURANCE, not DEVELOPMENT TOOLS.

You write feature once.
You change code 100+ times.
Each change could break the feature.
Tests ensure features STAY working.

Keep running tests forever.
```

---

**Last Updated: 2026-01-18**
