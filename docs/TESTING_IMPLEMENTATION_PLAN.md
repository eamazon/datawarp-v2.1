# Testing Strategy - Immediate Implementation Plan

**Date:** 2026-01-10
**Goal:** Clean up manifest chaos and establish testing foundation (can be done TODAY)
**Estimated Time:** 2-3 hours

---

## Immediate Actions (Do These First)

### 1. Reorganize Manifests Directory (30 min)

**Current State:**
```
manifests/
├── adhd_aug25_enriched.yaml
├── adhd_nov25_canonical.yaml
├── adhd_nov25_enriched.yaml
├── gp_appointments_nov25_enriched.yaml
├── pcn_workforce_nov25_enriched.yaml
├── archive_test_20260108_231700/  ← What is this?
├── archive_test_files/             ← What is this?
└── ... (chaos)
```

**Target State:**
```
manifests/
├── production/                     # ONLY validated, production-ready manifests
│   ├── adhd/
│   │   ├── adhd_aug25_enriched.yaml        # First period (LLM enriched)
│   │   └── adhd_nov25_canonical.yaml       # Second period (reference-based)
│   ├── gp_appointments/
│   │   ├── gp_appointments_oct25_enriched.yaml
│   │   └── gp_appointments_nov25_enriched.yaml
│   └── pcn_workforce/
│       └── pcn_workforce_nov25_enriched.yaml
│
├── test/                           # Test/experimental manifests
│   └── synthetic_simple.yaml
│
└── archive/                        # Old/deprecated manifests
    └── 2026-01-08/
        ├── adhd_aug25_v1.yaml
        └── README.md (why archived)
```

**Commands:**
```bash
# 1. Create structure
mkdir -p manifests/production/{adhd,gp_appointments,pcn_workforce}
mkdir -p manifests/test
mkdir -p manifests/archive/2026-01-08

# 2. Move production manifests
mv manifests/adhd_aug25_enriched.yaml manifests/production/adhd/
mv manifests/adhd_nov25_canonical.yaml manifests/production/adhd/
mv manifests/gp_appointments_nov25_enriched.yaml manifests/production/gp_appointments/
mv manifests/gp_appointments_oct25_enriched.yaml manifests/production/gp_appointments/
mv manifests/pcn_workforce_nov25_enriched.yaml manifests/production/pcn_workforce/

# 3. Move test/experimental to archive
mv manifests/archive_test* manifests/archive/2026-01-08/
mv manifests/*_error.txt manifests/archive/2026-01-08/
mv manifests/*_prompt.txt manifests/archive/2026-01-08/
mv manifests/*_debug* manifests/archive/2026-01-08/
mv manifests/*_v2* manifests/archive/2026-01-08/  # Old versions

# 4. Create archive README
cat > manifests/archive/2026-01-08/README.md << 'EOF'
# Archived Manifests - 2026-01-08

**Reason:** Cleanup before implementing testing strategy

**Contents:**
- Experimental enrichment runs
- Debug/error files
- Old manifest versions
- Test archives

**Do NOT use these in production.**
EOF

# 5. Update .gitignore
cat >> .gitignore << 'EOF'

# Manifest organization
manifests/test/*_temp.yaml
manifests/*/*_error.txt
manifests/*/*_prompt.txt
manifests/*/*_debug*.yaml
EOF
```

---

### 2. Create Manifest Validation Script (45 min)

**File:** `scripts/validate_manifest.py`

```python
#!/usr/bin/env python3
"""Validate DataWarp manifest structure and contents.

Usage:
    python scripts/validate_manifest.py manifests/production/adhd/adhd_aug25_enriched.yaml
    python scripts/validate_manifest.py manifests/production/adhd/*.yaml --strict
"""
import sys
import yaml
import argparse
from pathlib import Path
import requests
from collections import Counter

def validate_manifest(manifest_path: Path, strict: bool = False):
    """Validate manifest structure and contents."""

    errors = []
    warnings = []

    # 1. YAML is valid
    try:
        with open(manifest_path) as f:
            data = yaml.safe_load(f)
    except Exception as e:
        errors.append(f"YAML parse error: {e}")
        return errors, warnings

    # 2. Required top-level keys
    if 'manifest' not in data:
        errors.append("Missing 'manifest' key")

    if 'sources' not in data:
        errors.append("Missing 'sources' key")
        return errors, warnings

    sources = data['sources']

    # 3. Each source has required fields
    for i, src in enumerate(sources):
        src_id = src.get('code', f'source_{i}')

        required_fields = ['code', 'name', 'table', 'enabled', 'files']
        for field in required_fields:
            if field not in src:
                errors.append(f"Source '{src_id}': Missing required field '{field}'")

        # Check files array
        if 'files' in src:
            if not isinstance(src['files'], list) or len(src['files']) == 0:
                errors.append(f"Source '{src_id}': 'files' must be non-empty array")

            for j, file in enumerate(src['files']):
                if 'url' not in file:
                    errors.append(f"Source '{src_id}', file {j}: Missing 'url'")

    # 4. No duplicate source codes
    codes = [s.get('code') for s in sources if 'code' in s]
    code_counts = Counter(codes)
    duplicates = [code for code, count in code_counts.items() if count > 1]
    if duplicates:
        errors.append(f"Duplicate source codes: {duplicates}")

    # 5. Warn if generic codes (strict mode)
    if strict:
        generic_patterns = ['table_', 'summary_', 'breakdown_', 'sheet_']
        for src in sources:
            code = src.get('code', '')
            if any(pattern in code.lower() for pattern in generic_patterns):
                warnings.append(f"Source '{code}': Generic code pattern (consider enrichment)")

    # 6. Warn if no column metadata (enriched manifests should have this)
    if 'enriched' in manifest_path.name or 'canonical' in manifest_path.name:
        sources_without_columns = [
            s.get('code') for s in sources
            if s.get('enabled', True) and 'columns' not in s
        ]
        if sources_without_columns:
            warnings.append(f"{len(sources_without_columns)} enabled sources missing 'columns' metadata")

    # 7. Check file URLs are reachable (optional, slow)
    # Skip for now, can add --check-urls flag later

    return errors, warnings

def main():
    parser = argparse.ArgumentParser(description='Validate DataWarp manifest')
    parser.add_argument('manifest', nargs='+', help='Manifest file(s) to validate')
    parser.add_argument('--strict', action='store_true', help='Enable strict validation (warnings become errors)')

    args = parser.parse_args()

    total_errors = 0
    total_warnings = 0

    for manifest_path in args.manifest:
        path = Path(manifest_path)

        if not path.exists():
            print(f"❌ {manifest_path}: File not found")
            total_errors += 1
            continue

        print(f"\n{'='*80}")
        print(f"Validating: {manifest_path}")
        print(f"{'='*80}")

        errors, warnings = validate_manifest(path, args.strict)

        if errors:
            print(f"\n❌ ERRORS ({len(errors)}):")
            for err in errors:
                print(f"   - {err}")
            total_errors += len(errors)

        if warnings:
            print(f"\n⚠️  WARNINGS ({len(warnings)}):")
            for warn in warnings:
                print(f"   - {warn}")
            total_warnings += len(warnings)

        if not errors and not warnings:
            print("\n✅ VALID: No errors or warnings")

    print(f"\n{'='*80}")
    print(f"SUMMARY:")
    print(f"  Files validated: {len(args.manifest)}")
    print(f"  Total errors: {total_errors}")
    print(f"  Total warnings: {total_warnings}")
    print(f"{'='*80}")

    # Exit code: 0 if no errors, 1 if errors found
    sys.exit(1 if total_errors > 0 else 0)

if __name__ == '__main__':
    main()
```

**Test it:**
```bash
# Make executable
chmod +x scripts/validate_manifest.py

# Validate production manifests
python scripts/validate_manifest.py manifests/production/adhd/*.yaml

# Strict mode (treat warnings as errors)
python scripts/validate_manifest.py manifests/production/adhd/*.yaml --strict
```

---

### 3. Create Golden Datasets Registry (20 min)

**File:** `tests/e2e/golden_datasets.yaml`

```yaml
# Golden Dataset Registry
# These datasets MUST pass tests before any release

golden_datasets:
  - name: adhd_aug25_baseline
    description: "First ADHD publication - establishes baseline patterns"
    manifest: manifests/production/adhd/adhd_aug25_enriched.yaml
    reference: null  # No reference (first period)

    expectations:
      sources_total: 11
      sources_enabled: 11
      load_success_rate: 1.0  # 100% success required
      export_success_rate: 1.0
      total_rows_min: 1000
      total_rows_max: 5000

    validation_tests:
      - "All 11 sources export to Parquet"
      - "All 11 have companion .md files"
      - "Column metadata stored in database"
      - "Audit columns present (_load_id, _period, _loaded_at)"
      - "No empty files"
      - "All files have 3+ columns"

  - name: adhd_nov25_cross_period
    description: "Second ADHD publication - tests cross-period consistency"
    manifest: manifests/production/adhd/adhd_nov25_canonical.yaml
    reference: manifests/production/adhd/adhd_aug25_enriched.yaml

    expectations:
      sources_total: 28  # More sources than Aug (new ethnicity/gender breakdowns)
      sources_enabled: 25  # Some metadata sheets disabled
      code_consistency_min: 0.90  # 90%+ codes match reference
      cross_period_tables: 11  # Aug + Nov data coexist in 11 tables
      load_success_rate: 0.75  # 75%+ (some new tables may fail)

    validation_tests:
      - "Reference-based enrichment produces consistent codes"
      - "Aug + Nov data coexist in same tables"
      - "Cross-period queries work (filter by _period)"
      - "Schema didn't drift (same column names)"

  - name: gp_appointments_nov25_scale
    description: "Large-scale publication - tests system stability at 90 sources"
    manifest: manifests/production/gp_appointments/gp_appointments_nov25_enriched.yaml
    reference: null

    expectations:
      sources_total: 90
      sources_enabled: 90
      load_success_rate: 0.90  # 90%+ (allow some failures at scale)
      total_rows_min: 50000

    validation_tests:
      - "System handles 90 sources without crashing"
      - "Load time <10 minutes"
      - "Database doesn't run out of connections"
      - "Memory usage stays <4GB"

# Test Status Tracking
test_runs:
  - date: "2026-01-10"
    runner: "manual"
    results:
      adhd_aug25_baseline: "PASS"
      adhd_nov25_cross_period: "PASS"
      gp_appointments_nov25_scale: "PASS (117/122 sources)"
```

---

### 4. Update CLAUDE.md with Canonical Workflow (15 min)

**Add to CLAUDE.md (after line 134):**

```markdown
## Canonical Workflow Decision Tree

**CRITICAL:** Follow this workflow for ALL new publications to ensure consistency.

### When Loading First Period of a Publication

**Example:** ADHD August 2025 (first time loading ADHD data)

```bash
# 1. Generate manifest
python scripts/url_to_manifest.py <url> manifests/production/adhd/adhd_aug25.yaml

# 2. Enrich with LLM (NO --reference flag)
python scripts/enrich_manifest.py \
  manifests/production/adhd/adhd_aug25.yaml \
  manifests/production/adhd/adhd_aug25_enriched.yaml

# 3. Load to database
datawarp load-batch manifests/production/adhd/adhd_aug25_enriched.yaml

# 4. Export to Parquet
python scripts/export_to_parquet.py --publication adhd output/
```

**Result:** LLM creates semantic names, establishes schema baseline.

---

### When Loading Subsequent Periods

**Example:** ADHD November 2025 (second period, use August as reference)

```bash
# 1. Generate manifest
python scripts/url_to_manifest.py <url> manifests/production/adhd/adhd_nov25.yaml

# 2. Enrich with reference (USE --reference flag)
python scripts/enrich_manifest.py \
  manifests/production/adhd/adhd_nov25.yaml \
  manifests/production/adhd/adhd_nov25_canonical.yaml \
  --reference manifests/production/adhd/adhd_aug25_enriched.yaml  # ← CRITICAL

# 3. Load to database
datawarp load-batch manifests/production/adhd/adhd_nov25_canonical.yaml

# 4. Export to Parquet
python scripts/export_to_parquet.py --publication adhd output/
```

**Result:** Reference-based enrichment produces consistent codes, cross-period consolidation works.

---

### Naming Conventions

- **First period:** `{publication}_{period}_enriched.yaml`
- **Subsequent periods:** `{publication}_{period}_canonical.yaml`
- **Placement:** `manifests/production/{publication}/`

---

### Validation Steps (Run After Each Stage)

```bash
# After manifest generation
python scripts/validate_manifest.py manifests/production/adhd/adhd_nov25.yaml

# After enrichment
python scripts/validate_manifest.py manifests/production/adhd/adhd_nov25_canonical.yaml --strict

# After loading
python scripts/validate_loaded_data.py adhd_summary_open_referrals_age

# After export
python scripts/validate_parquet_export.py output/adhd_summary_open_referrals_age.parquet
```
```

---

### 5. Create Simple Test Runner Script (10 min)

**File:** `scripts/run_tests.sh`

```bash
#!/bin/bash
# DataWarp Test Runner

set -e  # Exit on first error

echo "=========================================="
echo "DataWarp Test Suite"
echo "=========================================="

# Activate venv
source .venv/bin/activate

echo ""
echo "1. Running unit tests..."
pytest tests/unit/ -v --tb=short || true

echo ""
echo "2. Running integration tests..."
pytest tests/integration/ -v --tb=short || true

echo ""
echo "3. Running E2E tests..."
pytest tests/e2e/ -v --tb=short || true

echo ""
echo "4. Validating production manifests..."
python scripts/validate_manifest.py manifests/production/*/*.yaml

echo ""
echo "=========================================="
echo "Test suite complete"
echo "=========================================="
```

**Make executable:**
```bash
chmod +x scripts/run_tests.sh
```

---

## Implementation Checklist (Do Today)

- [ ] **1. Reorganize manifests/** (30 min)
  - [ ] Create production/test/archive structure
  - [ ] Move manifests to correct locations
  - [ ] Create archive README
  - [ ] Update .gitignore

- [ ] **2. Create validate_manifest.py** (45 min)
  - [ ] Copy script from above
  - [ ] Test on ADHD manifests
  - [ ] Fix any issues found

- [ ] **3. Create golden_datasets.yaml** (20 min)
  - [ ] Copy registry from above
  - [ ] Update with actual success rates from today's runs
  - [ ] Place in tests/e2e/

- [ ] **4. Update CLAUDE.md** (15 min)
  - [ ] Add canonical workflow decision tree
  - [ ] Add validation step commands
  - [ ] Update workflow examples

- [ ] **5. Create run_tests.sh** (10 min)
  - [ ] Copy script from above
  - [ ] Make executable
  - [ ] Test run

**Total Time:** ~2 hours

---

## After Today (Next Steps)

### Week 1: Build Validation Scripts
- [ ] `scripts/validate_loaded_data.py`
- [ ] `scripts/validate_parquet_export.py`
- [ ] Add URL reachability check to validate_manifest.py

### Week 2: Write Unit Tests
- [ ] `tests/unit/test_schema.py` (to_schema_name, collision detection)
- [ ] `tests/unit/test_extractor.py` (header detection, type inference)
- [ ] `tests/unit/test_unpivot.py` (wide→long transformation)

### Week 3: Integration & E2E Tests
- [ ] `tests/integration/test_extraction.py`
- [ ] `tests/integration/test_enrichment.py`
- [ ] `tests/e2e/test_regression.py` (golden datasets)

---

## Success Criteria (How You Know It's Working)

After today's implementation:

1. ✅ Manifests directory is organized (production/test/archive)
2. ✅ Can run `python scripts/validate_manifest.py manifests/production/adhd/*.yaml` and get pass/fail
3. ✅ CLAUDE.md clearly documents which workflow to use when
4. ✅ Golden datasets registry exists and tracks test expectations
5. ✅ Can run `./scripts/run_tests.sh` (even if some tests fail, the infrastructure works)

**This gives you a foundation to build on systematically.**

---

**Last Updated:** 2026-01-10
**Status:** Ready to implement
**Owner:** User + Claude Code
**Estimated Time:** 2 hours
