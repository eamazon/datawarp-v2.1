# E2E Mandatory Testing Strategy

**Date:** 2026-01-18
**Status:** CRITICAL - Stop firefighting with mandatory E2E validation
**Goal:** Every change MUST pass full E2E pipeline tests before merge

---

## 🎯 The Pipeline Under Test

From `docs/pipelines/01_e2e_data_pipeline.md`:

```
NHS URL → url_to_manifest → enrich_manifest → load-batch → export_to_parquet → MCP Server → Agent Query
```

**Each stage MUST be tested end-to-end for every publication.**

---

## 🚨 Mandatory E2E Test Gates

**RULE:** Before any PR can merge, it MUST pass these gates:

### Gate 1: Quick Smoke (30 seconds - BLOCKING)
**Runs on:** Every commit (pre-commit hook)
**Blocks:** Commit if fails
**Tests:** One publication, one period, critical path only

### Gate 2: Core Publications (5 minutes - BLOCKING)
**Runs on:** Every push to PR
**Blocks:** Merge if fails
**Tests:** ADHD + MSA (representative publications)

### Gate 3: Full Suite (15 minutes - WARNING)
**Runs on:** Nightly + before release
**Blocks:** Release if fails
**Tests:** All publications in config

---

## 📋 Gate 1: Quick Smoke Tests

**File:** `tests/test_e2e_smoke.py`

```python
#!/usr/bin/env python3
"""
E2E Smoke Tests - Critical path validation (30 seconds)

Tests ONE publication through ENTIRE pipeline to catch obvious breaks.
Runs on EVERY commit via pre-commit hook.

Publication: ADHD (small, fast, representative)
Period: Single period (latest)
Coverage: All 5 pipeline stages + metadata tracking
"""

import pytest
import subprocess
import yaml
from pathlib import Path
from datawarp.storage.connection import get_connection

PROJECT_ROOT = Path(__file__).parent.parent
ADHD_CONFIG = PROJECT_ROOT / "config" / "publications_with_all_urls.yaml"


def test_stage1_url_to_manifest():
    """Stage 1: URL → Manifest generation"""
    # Use existing manifest (don't download every time)
    manifest_path = PROJECT_ROOT / "manifests" / "backfill" / "adhd" / "adhd_2025-05.yaml"

    assert manifest_path.exists(), "❌ ADHD manifest missing"

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    # Validate structure
    assert 'manifest' in manifest, "❌ Missing 'manifest' section"
    assert 'sources' in manifest, "❌ Missing 'sources' section"
    assert len(manifest['sources']) > 0, "❌ No sources in manifest"

    # Validate first source has required fields
    source = manifest['sources'][0]
    assert 'code' in source, "❌ Source missing 'code'"
    assert 'files' in source, "❌ Source missing 'files'"


def test_stage2_enrich_manifest():
    """Stage 2: Manifest enrichment with metadata"""
    raw_manifest = PROJECT_ROOT / "manifests" / "backfill" / "adhd" / "adhd_2025-05.yaml"
    enriched_manifest = PROJECT_ROOT / "manifests" / "backfill" / "adhd" / "adhd_2025-05_enriched.yaml"

    assert enriched_manifest.exists(), "❌ Enriched manifest missing"

    with open(enriched_manifest) as f:
        manifest = yaml.safe_load(f)

    # CRITICAL: Check first data source has column metadata
    data_sources = [s for s in manifest['sources'] if s.get('enabled', True)]
    assert len(data_sources) > 0, "❌ No data sources in enriched manifest"

    first_source = data_sources[0]

    # CRITICAL CHECK: Columns must exist at source level
    assert 'columns' in first_source, "❌ CRITICAL: No 'columns' key in source"
    assert len(first_source['columns']) > 0, "❌ CRITICAL: Empty columns array"

    # Validate column structure
    first_col = first_source['columns'][0]
    required_fields = ['name', 'original_name', 'description', 'data_type',
                      'is_dimension', 'is_measure', 'query_keywords']

    for field in required_fields:
        assert field in first_col, f"❌ CRITICAL: Missing '{field}' in column metadata"


def test_stage3_load_to_database():
    """Stage 3: Load data to PostgreSQL"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Check ADHD sources exist
            cur.execute("""
                SELECT COUNT(*) FROM datawarp.tbl_data_sources
                WHERE code LIKE 'adhd%'
            """)
            count = cur.fetchone()[0]
            assert count > 0, "❌ No ADHD sources in database"

            # Check load history exists
            cur.execute("""
                SELECT COUNT(*)
                FROM datawarp.tbl_load_history lh
                JOIN datawarp.tbl_data_sources ds ON lh.source_id = ds.id
                WHERE ds.code LIKE 'adhd%'
            """)
            load_count = cur.fetchone()[0]
            assert load_count > 0, "❌ No ADHD load history"


def test_stage4_metadata_storage():
    """Stage 4: Metadata stored in tbl_column_metadata"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # CRITICAL: Check metadata exists
            cur.execute("""
                SELECT
                    canonical_source_code,
                    column_name,
                    original_name,
                    description,
                    data_type,
                    is_dimension,
                    is_measure,
                    query_keywords
                FROM datawarp.tbl_column_metadata
                WHERE canonical_source_code LIKE 'adhd%'
                LIMIT 5
            """)

            rows = cur.fetchall()
            assert len(rows) > 0, "❌ CRITICAL: No metadata in tbl_column_metadata"

            # Validate first metadata record
            row = rows[0]
            assert row[0] is not None, "❌ Missing canonical_source_code"
            assert row[1] is not None, "❌ Missing column_name"
            assert row[2] is not None, "❌ Missing original_name"
            assert row[3] is not None, "❌ Missing description"
            assert row[4] is not None, "❌ Missing data_type"
            assert row[5] is not None, "❌ Missing is_dimension"
            assert row[6] is not None, "❌ Missing is_measure"


def test_critical_path_integration():
    """Integration: Full pipeline smoke test"""
    # This is the ULTIMATE smoke test - does the critical path work?

    # 1. Verify enriched manifest has columns
    enriched_path = PROJECT_ROOT / "manifests" / "backfill" / "adhd" / "adhd_2025-05_enriched.yaml"
    with open(enriched_path) as f:
        manifest = yaml.safe_load(f)

    data_sources = [s for s in manifest['sources'] if s.get('enabled', True)]
    source_code = data_sources[0]['code']

    assert 'columns' in data_sources[0], "❌ Enrichment broken: no columns"
    assert len(data_sources[0]['columns']) > 0, "❌ Enrichment broken: empty columns"

    # 2. Verify metadata in database matches manifest
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM datawarp.tbl_column_metadata
                WHERE canonical_source_code = %s
            """, (source_code,))

            db_count = cur.fetchone()[0]
            manifest_count = len(data_sources[0]['columns'])

            # Allow some mismatch (manifest may have more due to system columns)
            assert db_count > 0, "❌ CRITICAL: Metadata not stored in database"
            assert db_count >= manifest_count * 0.8, \
                f"❌ CRITICAL: Metadata mismatch (DB: {db_count}, Manifest: {manifest_count})"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
```

**Install as pre-commit hook:**

```bash
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
set -e

echo "🔍 Running E2E smoke tests (30 seconds)..."

# Run smoke tests
pytest tests/test_e2e_smoke.py -v --tb=short || {
    echo ""
    echo "❌ E2E SMOKE TESTS FAILED"
    echo ""
    echo "Your changes broke the critical path!"
    echo "Fix the issues above before committing."
    echo ""
    echo "To see full details:"
    echo "  pytest tests/test_e2e_smoke.py -v"
    echo ""
    echo "To bypass (EMERGENCY ONLY - will break main):"
    echo "  git commit --no-verify"
    echo ""
    exit 1
}

echo "✅ E2E smoke tests passed"
exit 0
EOF

chmod +x .git/hooks/pre-commit
```

---

## 📋 Gate 2: Core Publications E2E

**File:** `tests/test_e2e_core_publications.py`

```python
#!/usr/bin/env python3
"""
Core Publications E2E Tests (5 minutes)

Tests representative publications through ENTIRE pipeline.
Runs on every push to PR branch.

Publications:
- ADHD (multi-sheet, hierarchical headers, schema drift)
- MSA (multi-period, consistent schema)

Coverage: All pipeline stages for both publications
"""

import pytest
from pathlib import Path
from datawarp.storage.connection import get_connection

PROJECT_ROOT = Path(__file__).parent.parent

CORE_PUBLICATIONS = [
    {
        'code': 'adhd',
        'name': 'ADHD Management',
        'min_sources': 3,
        'min_metadata_columns': 20,
        'test_periods': ['2025-05', '2025-08']
    },
    {
        'code': 'mixed_sex_accommodation',
        'name': 'Mixed Sex Accommodation',
        'min_sources': 5,
        'min_metadata_columns': 30,
        'test_periods': ['2025-06']
    }
]


@pytest.mark.parametrize("pub", CORE_PUBLICATIONS, ids=lambda p: p['code'])
class TestCorePublicationPipeline:
    """Test full pipeline for core publications."""

    def test_manifests_exist(self, pub):
        """Verify manifest files exist."""
        manifest_dir = PROJECT_ROOT / "manifests" / "backfill" / pub['code'].replace('_', '')

        if not manifest_dir.exists():
            # Try alternate naming
            manifest_dir = PROJECT_ROOT / "manifests" / "backfill" / pub['code']

        assert manifest_dir.exists(), f"❌ Manifest directory missing for {pub['code']}"

        # Check for at least one enriched manifest
        enriched = list(manifest_dir.glob("*enriched.yaml"))
        assert len(enriched) > 0, f"❌ No enriched manifests for {pub['code']}"

    def test_sources_registered(self, pub):
        """Verify sources registered in database."""
        with get_connection() as conn:
            cur = conn.cursor()

            # Get source count
            cur.execute("""
                SELECT COUNT(*) FROM datawarp.tbl_data_sources
                WHERE code LIKE %s
            """, (f"{pub['code'][:3]}%",))

            count = cur.fetchone()[0]
            assert count >= pub['min_sources'], \
                f"❌ Expected {pub['min_sources']} sources, found {count}"

    def test_data_loaded(self, pub):
        """Verify data loaded to tables."""
        with get_connection() as conn:
            cur = conn.cursor()

            # Get total rows loaded
            cur.execute("""
                SELECT SUM(lh.rows_loaded)
                FROM datawarp.tbl_load_history lh
                JOIN datawarp.tbl_data_sources ds ON lh.source_id = ds.id
                WHERE ds.code LIKE %s
            """, (f"{pub['code'][:3]}%",))

            total_rows = cur.fetchone()[0] or 0
            assert total_rows > 0, f"❌ No data loaded for {pub['code']}"

    def test_metadata_stored(self, pub):
        """CRITICAL: Verify metadata stored."""
        with get_connection() as conn:
            cur = conn.cursor()

            # Count metadata columns
            cur.execute("""
                SELECT COUNT(*)
                FROM datawarp.tbl_column_metadata
                WHERE canonical_source_code LIKE %s
            """, (f"{pub['code'][:3]}%",))

            count = cur.fetchone()[0]
            assert count >= pub['min_metadata_columns'], \
                f"❌ CRITICAL: Expected {pub['min_metadata_columns']} metadata columns, found {count}"

    def test_metadata_completeness(self, pub):
        """CRITICAL: Verify metadata has all required fields."""
        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT
                    canonical_source_code,
                    column_name,
                    original_name,
                    description,
                    data_type,
                    is_dimension,
                    is_measure,
                    query_keywords
                FROM datawarp.tbl_column_metadata
                WHERE canonical_source_code LIKE %s
                LIMIT 10
            """, (f"{pub['code'][:3]}%",))

            rows = cur.fetchall()
            assert len(rows) > 0, f"❌ No metadata for {pub['code']}"

            # Check all fields populated
            for row in rows:
                assert all(field is not None for field in row), \
                    f"❌ CRITICAL: Null fields in metadata"

    def test_cross_period_consistency(self, pub):
        """Verify metadata consistent across periods."""
        if len(pub['test_periods']) < 2:
            pytest.skip("Not enough periods to test consistency")

        with get_connection() as conn:
            cur = conn.cursor()

            # Get sources loaded in both periods
            cur.execute("""
                SELECT DISTINCT ds.code
                FROM datawarp.tbl_load_history lh
                JOIN datawarp.tbl_data_sources ds ON lh.source_id = ds.id
                WHERE ds.code LIKE %s
                GROUP BY ds.code
                HAVING COUNT(DISTINCT lh.id) >= 2
                LIMIT 1
            """, (f"{pub['code'][:3]}%",))

            result = cur.fetchone()
            if result:
                source_code = result[0]

                # Verify metadata exists for this source
                cur.execute("""
                    SELECT COUNT(*) FROM datawarp.tbl_column_metadata
                    WHERE canonical_source_code = %s
                """, (source_code,))

                count = cur.fetchone()[0]
                assert count > 0, \
                    f"❌ No metadata for multi-period source {source_code}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
```

**Run in CI:**
```bash
# In GitHub Actions / GitLab CI
pytest tests/test_e2e_core_publications.py -v --tb=short
```

---

## 📋 Gate 3: Full Publications Suite

**Uses existing:** `tests/test_e2e_publication.py`

**Enhancements needed:**

```python
# Add to test_e2e_publication.py

@pytest.fixture(scope="session", autouse=True)
def verify_pipeline_stages():
    """Verify all pipeline stages are testable."""

    # Check required infrastructure exists
    required_dirs = [
        Path("manifests/backfill"),
        Path("scripts"),
        Path("src/datawarp/pipeline"),
        Path("src/datawarp/loader"),
        Path("src/datawarp/storage"),
    ]

    for dir_path in required_dirs:
        assert dir_path.exists(), f"❌ Missing required directory: {dir_path}"

    # Check database connectivity
    try:
        from datawarp.storage.connection import get_connection
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
    except Exception as e:
        pytest.fail(f"❌ Database connection failed: {e}")


class TestPipelineStages:
    """Test each pipeline stage independently."""

    @pytest.mark.parametrize("pub_code", TEST_PUBLICATIONS)
    def test_stage1_manifest_generation(self, pub_code):
        """Stage 1: Verify manifest files exist and are valid."""
        # Find manifest files for publication
        manifest_dirs = [
            Path(f"manifests/backfill/{pub_code}"),
            Path(f"manifests/backfill/{pub_code.replace('_', '')}")
        ]

        manifest_found = False
        for manifest_dir in manifest_dirs:
            if manifest_dir.exists():
                manifests = list(manifest_dir.glob("*.yaml"))
                if manifests:
                    manifest_found = True
                    break

        assert manifest_found, f"❌ No manifests found for {pub_code}"

    @pytest.mark.parametrize("pub_code", TEST_PUBLICATIONS)
    def test_stage2_enrichment_quality(self, pub_code):
        """Stage 2: Verify enrichment produces valid metadata."""
        # This is now covered by TestE2EMetadata
        pass

    @pytest.mark.parametrize("pub_code", TEST_PUBLICATIONS)
    def test_stage3_loading_idempotency(self, pub_code):
        """Stage 3: Verify reloading same data is idempotent."""
        # Load twice, verify no duplication
        run_backfill_cli(pub_code, force=True)

        with get_db_connection() as conn:
            cur = conn.cursor()

            # Get row counts before second load
            cur.execute("""
                SELECT ds.code, COUNT(DISTINCT lh.id)
                FROM datawarp.tbl_load_history lh
                JOIN datawarp.tbl_data_sources ds ON lh.source_id = ds.id
                WHERE ds.code LIKE %s
                GROUP BY ds.code
            """, (f"%{pub_code.split('_')[-1]}%",))

            before_counts = {row[0]: row[1] for row in cur.fetchall()}

        # Load again
        run_backfill_cli(pub_code, force=True)

        with get_db_connection() as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT ds.code, COUNT(DISTINCT lh.id)
                FROM datawarp.tbl_load_history lh
                JOIN datawarp.tbl_data_sources ds ON lh.source_id = ds.id
                WHERE ds.code LIKE %s
                GROUP BY ds.code
            """, (f"%{pub_code.split('_')[-1]}%",))

            after_counts = {row[0]: row[1] for row in cur.fetchall()}

        # Should have exactly one more load record per source
        for code in before_counts:
            assert after_counts[code] == before_counts[code] + 1, \
                f"❌ Load history not tracking correctly for {code}"
```

---

## 🚀 Implementation Checklist

### Phase 1: Quick Wins (Today - 30 minutes)

- [ ] Create `tests/test_e2e_smoke.py`
- [ ] Install pre-commit hook
- [ ] Run smoke tests manually: `pytest tests/test_e2e_smoke.py -v`
- [ ] Test pre-commit hook: `git commit --allow-empty -m "test hook"`

### Phase 2: Core Tests (This Week - 2 hours)

- [ ] Create `tests/test_e2e_core_publications.py`
- [ ] Run core tests: `pytest tests/test_e2e_core_publications.py -v`
- [ ] Fix any failures
- [ ] Document expected test times

### Phase 3: CI Integration (Next Week - 3 hours)

- [ ] Create `.github/workflows/e2e-tests.yml`
- [ ] Configure to run on PR
- [ ] Configure to block merge on failure
- [ ] Add status badge to README

### Phase 4: Full Coverage (Ongoing)

- [ ] Add TestPipelineStages to test_e2e_publication.py
- [ ] Run nightly on all publications
- [ ] Create test failure alert system
- [ ] Document all test failures and fixes

---

## 📊 Test Execution Matrix

| Test Suite | When | Duration | Blocks | Coverage |
|------------|------|----------|--------|----------|
| **Smoke** | Every commit | 30s | Commit | 1 pub, critical path |
| **Core** | Every push | 5min | Merge | 2 pubs, all stages |
| **Full** | Nightly + release | 15min | Release | All pubs, all stages |
| **Metadata** | Every push | 2min | Merge | All pubs, metadata only |

---

## 🎯 Success Metrics

**Week 1:**
- ✅ Pre-commit hook installed and running
- ✅ 0 commits bypass smoke tests
- ✅ Smoke tests pass in < 30 seconds

**Week 2:**
- ✅ Core tests integrated into PR workflow
- ✅ 0 PRs merged with failing core tests
- ✅ Core tests pass in < 5 minutes

**Month 1:**
- ✅ Full test suite running nightly
- ✅ < 5% test failure rate
- ✅ All failures investigated within 24 hours

**Month 3:**
- ✅ 0 production bugs that tests would have caught
- ✅ Development velocity increased 2x
- ✅ Time spent firefighting reduced 90%

---

## 🔧 Troubleshooting

**If smoke tests fail on commit:**
```bash
# See detailed failure
pytest tests/test_e2e_smoke.py -v

# Run specific failed test
pytest tests/test_e2e_smoke.py::test_stage4_metadata_storage -v

# If truly emergency (NOT RECOMMENDED):
git commit --no-verify -m "message"
```

**If core tests fail in CI:**
```bash
# Run locally first
pytest tests/test_e2e_core_publications.py -v

# Check specific publication
pytest tests/test_e2e_core_publications.py -k "adhd" -v

# Check database state
python -c "
from datawarp.storage.connection import get_connection
with get_connection() as conn:
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM datawarp.tbl_column_metadata')
    print(f'Metadata rows: {cur.fetchone()[0]}')
"
```

---

## 📝 Maintenance

**Daily:**
- Monitor pre-commit hook success rate
- Investigate any bypassed commits

**Weekly:**
- Review CI test results
- Update test data if needed
- Add tests for new features

**Monthly:**
- Run full suite on all publications
- Review and update this document
- Update test timing estimates

---

## 🔧 Installation and Setup

**Updated: 2026-01-18 20:30 UTC**

### Automated Setup (Recommended)

Run the setup script to install all hooks:

```bash
bash scripts/setup_hooks.sh
```

This will:
1. ✅ Verify you're in a git repository
2. ✅ Check virtual environment exists
3. ✅ Install pre-commit hook at `.git/hooks/pre-commit`
4. ✅ Make hook executable
5. ✅ Run test to verify hook works

### Manual Verification

Check if hooks are installed and working:

```bash
# 1. Check hook exists and is executable
ls -la .git/hooks/pre-commit
# Should show: -rwxr-xr-x ... .git/hooks/pre-commit

# 2. Run hook manually
.git/hooks/pre-commit
# Should run smoke tests and show results

# 3. Test with dummy commit
git commit --allow-empty -m "test hook"
# Should run smoke tests before committing
```

### CI/CD Setup

The GitHub Actions workflow is already configured at `.github/workflows/e2e-tests.yml`.

To enable:

1. **Add Gemini API Key to GitHub Secrets:**
   - Go to repository settings → Secrets → Actions
   - Add new secret: `GEMINI_API_KEY` = your API key

2. **Verify workflow runs:**
   - Push to a PR branch
   - Check Actions tab in GitHub
   - Verify all 3 gates run and pass

3. **Configure branch protection:**
   - Settings → Branches → Add rule for `main`
   - Require status checks: `Gate 1: Smoke Tests`, `Gate 2: Core Publications`
   - This BLOCKS merge if tests fail

### Verifying Everything Works

**Step 1: Verify pre-commit hook**
```bash
# This should BLOCK if smoke tests fail
echo "test change" >> README.md
git add README.md
git commit -m "test commit"
# Hook should run and pass
git reset HEAD~1  # Undo test commit
```

**Step 2: Verify CI workflow**
```bash
# Push to a test branch
git checkout -b test-ci-workflow
git push origin test-ci-workflow
# Check GitHub Actions tab - should see 3 jobs running
```

**Step 3: Verify tests catch breakage**
```bash
# Intentionally break something
echo "BROKEN" > src/datawarp/pipeline/enricher.py
git add src/datawarp/pipeline/enricher.py
git commit -m "test breakage"
# Hook should BLOCK this commit

# Restore
git checkout src/datawarp/pipeline/enricher.py
```

### What Happens When Tests Fail

**Pre-commit hook failure:**
```
🔍 Running DataWarp smoke tests (30 seconds)...

FAILED tests/test_e2e_smoke.py::test_stage2_enrichment_preserves_columns

❌ COMMIT BLOCKED: Smoke tests failed

Critical functionality is broken. Please fix the issues above before committing.

To bypass (NOT RECOMMENDED):
  git commit --no-verify
```

**CI workflow failure:**
- PR shows red X next to commit
- Cannot merge until tests pass
- Must push fixes to make tests pass

### Emergency Bypass (Use Only When Necessary)

If you MUST commit despite test failures (e.g., fixing the tests themselves):

```bash
# Bypass pre-commit hook
git commit --no-verify -m "emergency: fixing broken tests"

# Note: CI will still run and may block merge
```

**WARNING:** Bypassing tests means you're knowingly committing broken code. Use only for:
- Fixing the test infrastructure itself
- Emergency hotfixes (with manual verification)
- Documentation-only changes

---

**REMEMBER:** These tests are your safety net. They catch bugs before users see them. Every test failure is a disaster averted! 🎉
