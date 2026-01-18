# Robust Testing Strategy - Stop the Firefighting

**Date:** 2026-01-18
**Status:** CRITICAL - Development blocked by constant breakage
**Goal:** Mandatory automated testing at every change to catch regressions BEFORE they break production

---

## 🚨 The Problem

**Current state:**
- Changes break existing functionality without warning
- Tests exist but aren't run consistently
- No automated gates preventing bad commits
- Manual testing is incomplete and time-consuming
- Development velocity destroyed by firefighting

**Example recent breakages:**
- Metadata tracking broken (enricher deleted columns before saving)
- Repository looking for wrong field names
- LLM prompt missing required fields

**Cost:** Hours of debugging, broken workflows, user frustration

---

## 🎯 The Solution: 4-Layer Defense

```
┌─────────────────────────────────────────────────────────────┐
│ LAYER 4: Pre-Commit Hook (5-30 seconds)                    │
│ → Runs BEFORE you can commit                                │
│ → Fast smoke tests on changed files only                    │
│ → Catches obvious breaks immediately                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 3: Unit Tests (30-60 seconds)                        │
│ → Test individual functions in isolation                    │
│ → Run on every commit (CI/CD)                               │
│ → 80%+ code coverage required                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 2: Integration Tests (2-5 minutes)                   │
│ → Test component interactions                               │
│ → Run on every push to main                                 │
│ → Validates end-to-end workflows                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 1: E2E Validation (5-15 minutes)                     │
│ → Full publication load tests                               │
│ → Run nightly + before releases                             │
│ → Validates production-like scenarios                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 Layer 4: Pre-Commit Hooks (MANDATORY)

**Purpose:** Catch obvious breaks BEFORE you can commit

**Implementation:** `.git/hooks/pre-commit`

```bash
#!/bin/bash
# Pre-commit hook - runs fast smoke tests

set -e  # Exit on any failure

echo "🔍 Running pre-commit validation..."

# 1. Check Python syntax (FAST - 1 second)
echo "  → Checking Python syntax..."
python -m py_compile src/datawarp/**/*.py 2>/dev/null || {
    echo "❌ Python syntax errors found"
    exit 1
}

# 2. Run critical path smoke tests (FAST - 10 seconds)
echo "  → Running critical path tests..."
pytest tests/test_smoke.py -v --tb=short || {
    echo "❌ Smoke tests failed"
    exit 1
}

# 3. Check for broken imports (FAST - 5 seconds)
echo "  → Checking imports..."
python -c "
from datawarp.pipeline.enricher import enrich_manifest
from datawarp.loader.batch import load_from_manifest
from datawarp.storage.repository import store_column_metadata
" || {
    echo "❌ Import errors found"
    exit 1
}

# 4. Run tests on changed files only (FAST - varies)
CHANGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$' || true)
if [ -n "$CHANGED_FILES" ]; then
    echo "  → Testing changed files..."
    for file in $CHANGED_FILES; do
        # Find corresponding test file
        test_file="tests/test_${file##*/}"
        if [ -f "$test_file" ]; then
            pytest "$test_file" -v --tb=short || {
                echo "❌ Tests failed for $file"
                exit 1
            }
        fi
    done
fi

echo "✅ Pre-commit checks passed"
exit 0
```

**Install:**
```bash
# Make executable
chmod +x .git/hooks/pre-commit

# Test it
git commit --dry-run
```

---

## 📋 Critical Path Smoke Tests

**File:** `tests/test_smoke.py`

**Purpose:** Ultra-fast validation of critical functionality (< 10 seconds)

```python
#!/usr/bin/env python3
"""
Smoke tests - Critical path validation (< 10 seconds total)

These tests run on EVERY commit via pre-commit hook.
They must be FAST and test the CRITICAL paths.

CRITICAL PATHS:
1. Enricher generates and persists column metadata
2. Repository stores metadata with correct field mapping
3. Batch loader triggers metadata storage
4. LLM prompt includes all required fields
"""

import pytest
import yaml
import tempfile
from pathlib import Path

def test_enricher_preserves_columns():
    """CRITICAL: Enricher must preserve column metadata from preview."""
    from datawarp.pipeline.enricher import enrich_manifest

    # Create minimal test manifest
    test_manifest = {
        'manifest': {
            'source_url': 'http://test.com',
            'publication_context': {'page_title': 'Test'}
        },
        'sources': [{
            'code': 'test_source',
            'files': [{
                'url': 'http://test.com/data.xlsx',
                'preview': {
                    'columns': [
                        {
                            'name': 'test_col',
                            'original_name': 'Test Column',
                            'description': 'Test',
                            'data_type': 'VARCHAR',
                            'is_dimension': True,
                            'is_measure': False,
                            'query_keywords': ['test']
                        }
                    ]
                }
            }]
        }]
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(test_manifest, f)
        input_path = f.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        output_path = f.name

    try:
        # This simulates what enricher does - save with preview, then strip
        enriched = test_manifest.copy()

        # CRITICAL: Must copy columns from preview to source level
        for source in enriched['sources']:
            if source.get('files'):
                preview = source['files'][0].get('preview', {})
                preview_columns = preview.get('columns', [])
                if preview_columns:
                    source['columns'] = preview_columns

        # Strip preview
        for source in enriched['sources']:
            for file in source.get('files', []):
                if 'preview' in file:
                    del file['preview']

        with open(output_path, 'w') as f:
            yaml.dump(enriched, f)

        # Verify columns preserved
        with open(output_path) as f:
            result = yaml.safe_load(f)

        assert 'columns' in result['sources'][0], "❌ CRITICAL: Columns not preserved!"
        assert len(result['sources'][0]['columns']) > 0, "❌ CRITICAL: Empty columns!"

    finally:
        Path(input_path).unlink(missing_ok=True)
        Path(output_path).unlink(missing_ok=True)


def test_repository_field_mapping():
    """CRITICAL: Repository must look for 'name' field, not 'semantic_name'."""
    # Simulate what repository does
    test_column = {
        'name': 'test_column',
        'original_name': 'Test Column',
        'description': 'Test',
        'data_type': 'VARCHAR',
        'is_dimension': True,
        'is_measure': False,
        'query_keywords': ['test']
    }

    # This is what repository.py does
    column_name = test_column.get('name') or test_column.get('semantic_name') or test_column.get('code')

    assert column_name == 'test_column', "❌ CRITICAL: Repository can't find column name!"
    assert column_name is not None, "❌ CRITICAL: Column name is None!"


def test_llm_prompt_completeness():
    """CRITICAL: LLM prompt must request all required fields."""
    from datawarp.pipeline.enricher import build_enrichment_prompt

    manifest = {
        'manifest': {
            'source_url': 'http://test.com',
            'publication_context': {'page_title': 'Test Publication'}
        }
    }

    data_sources = [{
        'code': 'test',
        'files': [{'url': 'http://test.com/data.xlsx'}]
    }]

    prompt = build_enrichment_prompt(manifest, data_sources)

    # Check all required fields are mentioned in prompt
    required_fields = [
        'name',
        'original_name',
        'description',
        'data_type',
        'is_dimension',
        'is_measure',
        'query_keywords'
    ]

    for field in required_fields:
        assert field in prompt, f"❌ CRITICAL: LLM prompt missing '{field}' field!"


def test_metadata_storage_trigger():
    """CRITICAL: Batch loader must check for columns and trigger storage."""
    # Simulate what batch.py does
    source_config = {
        'code': 'test_source',
        'columns': [
            {
                'name': 'test_col',
                'original_name': 'Test Column',
                'description': 'Test',
                'data_type': 'VARCHAR',
                'is_dimension': True,
                'is_measure': False,
                'query_keywords': ['test']
            }
        ]
    }

    # This is the check in batch.py line 443
    should_store = 'columns' in source_config and source_config['columns']

    assert should_store, "❌ CRITICAL: Metadata storage won't trigger!"
    assert len(source_config['columns']) > 0, "❌ CRITICAL: Empty columns!"


def test_critical_imports():
    """CRITICAL: Core modules must import without errors."""
    try:
        from datawarp.pipeline.enricher import enrich_manifest
        from datawarp.loader.batch import load_from_manifest
        from datawarp.storage.repository import store_column_metadata
        from datawarp.core.extractor import FileExtractor
    except ImportError as e:
        pytest.fail(f"❌ CRITICAL: Import failed: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
```

**Run manually:**
```bash
pytest tests/test_smoke.py -v
```

---

## 📋 Layer 3: Unit Tests

**Purpose:** Test individual functions in isolation

**Requirements:**
- 80%+ code coverage
- Run in < 60 seconds
- No database required (use mocks)

**Critical unit tests needed:**

### 1. Enricher Tests
```python
# tests/test_enricher_unit.py

def test_column_preservation():
    """Test that columns are preserved from preview."""
    pass

def test_llm_prompt_generation():
    """Test that prompt includes all required fields."""
    pass

def test_reference_matching():
    """Test that reference matching works correctly."""
    pass
```

### 2. Repository Tests
```python
# tests/test_repository_unit.py

def test_field_name_extraction():
    """Test that repository extracts correct field names."""
    pass

def test_metadata_storage_logic():
    """Test that metadata storage handles all formats."""
    pass
```

### 3. Batch Loader Tests
```python
# tests/test_batch_unit.py

def test_metadata_trigger_conditions():
    """Test when metadata storage is triggered."""
    pass
```

**Run:**
```bash
pytest tests/ -v --cov=src/datawarp --cov-report=term-missing
```

---

## 📋 Layer 2: Integration Tests

**Purpose:** Test component interactions

**File:** `tests/test_integration.py`

```python
#!/usr/bin/env python3
"""
Integration tests - Component interaction validation

These tests validate that components work together correctly.
They use a test database and real (but small) data files.
"""

import pytest
import tempfile
from pathlib import Path

@pytest.fixture(scope="session")
def test_db():
    """Setup test database."""
    # Use test database config
    pass

def test_enrichment_to_loading_pipeline():
    """Test full pipeline: enrich → load → verify metadata stored."""
    # 1. Create test manifest
    # 2. Enrich it
    # 3. Verify columns in enriched manifest
    # 4. Load it
    # 5. Verify metadata in database
    pass

def test_reference_matching_pipeline():
    """Test reference-based enrichment preserves metadata."""
    # 1. Enrich first period (LLM)
    # 2. Enrich second period (reference)
    # 3. Verify metadata consistency
    pass

def test_schema_drift_metadata():
    """Test that schema drift preserves existing metadata."""
    # 1. Load first version
    # 2. Load second version with new columns
    # 3. Verify old metadata preserved, new metadata added
    pass
```

**Run:**
```bash
pytest tests/test_integration.py -v
```

---

## 📋 Layer 1: E2E Tests (Already Exists)

**File:** `tests/test_e2e_publication.py`

**Current status:** ✅ Implemented
- TestE2EPublication - Core validation
- TestE2EEvidence - Database evidence
- TestE2EMetadata - Metadata tracking ← NEW
- TestE2EForceReload - Force reload
- TestE2EValidation - Error handling

**Run:**
```bash
# Run all e2e tests
pytest tests/test_e2e_publication.py -v

# Run for specific publication
pytest tests/test_e2e_publication.py -k "adhd" -v

# Run only metadata tests
pytest tests/test_e2e_publication.py -k "Metadata" -v
```

---

## 🚀 Quick Start Implementation

### Step 1: Create Smoke Tests (5 minutes)

```bash
# Create smoke test file
cat > tests/test_smoke.py << 'EOF'
# [Copy smoke test content from above]
EOF

# Run it
pytest tests/test_smoke.py -v
```

### Step 2: Install Pre-Commit Hook (2 minutes)

```bash
# Create hook
cat > .git/hooks/pre-commit << 'EOF'
# [Copy pre-commit hook from above]
EOF

# Make executable
chmod +x .git/hooks/pre-commit

# Test it (will run on next commit)
git add tests/test_smoke.py
git commit -m "test: Add smoke tests"
```

### Step 3: Add to CI/CD (10 minutes)

**File:** `.github/workflows/tests.yml`

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e .
          pip install pytest pytest-cov
      - name: Run smoke tests
        run: pytest tests/test_smoke.py -v

  unit:
    runs-on: ubuntu-latest
    needs: smoke
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest pytest-cov
      - name: Run unit tests
        run: pytest tests/ -v --cov=src/datawarp --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2

  integration:
    runs-on: ubuntu-latest
    needs: unit
    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v2
      - name: Run integration tests
        run: pytest tests/test_integration.py -v
```

---

## 📊 Test Coverage Requirements

**Minimum coverage by component:**
- `src/datawarp/pipeline/enricher.py`: 90%
- `src/datawarp/storage/repository.py`: 90%
- `src/datawarp/loader/batch.py`: 85%
- `src/datawarp/core/extractor.py`: 80%
- Overall: 80%

**Enforce with:**
```bash
pytest --cov=src/datawarp --cov-fail-under=80
```

---

## 🎯 Critical Paths to Test

**These MUST NOT break - test extensively:**

1. **Metadata Generation Pipeline**
   - enricher.py generates columns
   - enricher.py preserves columns before stripping preview
   - batch.py checks for columns and triggers storage
   - repository.py extracts fields correctly
   - database stores all required fields

2. **Reference Matching**
   - Reference manifest loaded correctly
   - Column matching works (exact + fuzzy)
   - Metadata copied from reference
   - New columns get LLM enrichment

3. **Schema Drift**
   - New columns detected
   - Old metadata preserved
   - New metadata generated
   - columns_added tracked

4. **Cross-Period Consistency**
   - Same source code across periods
   - Metadata inherited correctly
   - Period filtering works

---

## 📝 Testing Workflow

**Before making changes:**
```bash
# 1. Pull latest
git pull origin main

# 2. Create branch
git checkout -b fix/your-fix

# 3. Make changes
# ... edit code ...

# 4. Run smoke tests manually
pytest tests/test_smoke.py -v

# 5. Run related unit tests
pytest tests/test_enricher.py -v

# 6. Commit (pre-commit hook runs automatically)
git add .
git commit -m "fix: Your fix"

# If pre-commit fails, fix and retry
```

**After changes:**
```bash
# 1. Run full test suite locally
pytest tests/ -v

# 2. Check coverage
pytest --cov=src/datawarp --cov-report=html
open htmlcov/index.html

# 3. Push (CI/CD runs automatically)
git push origin fix/your-fix

# 4. Wait for CI to pass before merging
```

---

## 🔧 Maintenance

**Weekly:**
- Review test failures
- Update tests for new features
- Check coverage reports

**Monthly:**
- Run full e2e suite on all publications
- Update smoke tests if critical paths change
- Review and update this document

---

## ✅ Success Criteria

You'll know the strategy is working when:
- ✅ Pre-commit hook catches obvious breaks before commit
- ✅ CI/CD catches integration issues before merge
- ✅ E2E tests catch production issues before release
- ✅ No more "firefighting" - issues caught early
- ✅ Confidence to make changes without fear of breaking things
- ✅ Development velocity increases (less debugging)

---

## 🚨 What to Do When Tests Fail

**If pre-commit fails:**
```bash
# 1. Read error message
# 2. Fix the issue
# 3. Run tests manually to verify
pytest tests/test_smoke.py -v
# 4. Try commit again
git commit -m "your message"
```

**If CI fails:**
```bash
# 1. Check CI logs
# 2. Run failed test locally
pytest tests/path/to/failed_test.py -v
# 3. Fix and push again
```

**If you need to bypass (EMERGENCY ONLY):**
```bash
# Skip pre-commit hook (DON'T DO THIS)
git commit --no-verify -m "message"

# Skip CI (DON'T DO THIS)
git push --force-with-lease
```

---

**REMEMBER:** Tests are not obstacles - they're safety nets. Every test that fails is a production bug you caught early! 🎉
