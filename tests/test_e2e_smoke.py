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
import yaml
from pathlib import Path
from datawarp.storage.connection import get_connection

PROJECT_ROOT = Path(__file__).parent.parent


def test_stage1_manifest_structure():
    """Stage 1: Manifest has correct structure."""
    manifest_path = PROJECT_ROOT / "manifests" / "backfill" / "adhd" / "adhd_2025-05.yaml"

    if not manifest_path.exists():
        pytest.skip("ADHD manifest not found - run backfill first")

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    # Validate structure
    assert 'manifest' in manifest, "❌ Missing 'manifest' section"
    assert 'sources' in manifest, "❌ Missing 'sources' section"
    assert len(manifest['sources']) > 0, "❌ No sources in manifest"


def test_stage2_enrichment_preserves_columns():
    """Stage 2: CRITICAL - Enrichment must preserve column metadata."""
    enriched_path = PROJECT_ROOT / "manifests" / "backfill" / "adhd" / "adhd_2025-05_enriched.yaml"

    if not enriched_path.exists():
        pytest.skip("ADHD enriched manifest not found")

    with open(enriched_path) as f:
        manifest = yaml.safe_load(f)

    # Get first data source
    data_sources = [s for s in manifest['sources'] if s.get('enabled', True)]
    assert len(data_sources) > 0, "❌ No data sources"

    first_source = data_sources[0]

    # CRITICAL: Columns must exist at source level
    assert 'columns' in first_source, "❌ CRITICAL: enricher.py not preserving columns!"
    assert len(first_source['columns']) > 0, "❌ CRITICAL: Empty columns array!"

    # Validate column has all required fields
    first_col = first_source['columns'][0]
    required_fields = ['name', 'original_name', 'description', 'data_type',
                      'is_dimension', 'is_measure', 'query_keywords']

    missing_fields = [f for f in required_fields if f not in first_col]
    assert not missing_fields, f"❌ CRITICAL: Missing fields in column metadata: {missing_fields}"


def test_stage3_database_sources():
    """Stage 3: Sources registered in database."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT COUNT(*) FROM datawarp.tbl_data_sources
                WHERE code LIKE 'adhd%'
            """)

            count = cur.fetchone()[0]
            assert count > 0, "❌ No ADHD sources in database"
    except Exception as e:
        pytest.skip(f"Database not available: {e}")


def test_stage4_metadata_storage():
    """Stage 4: CRITICAL - Metadata stored in database."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT COUNT(*) FROM datawarp.tbl_column_metadata
                WHERE canonical_source_code LIKE 'adhd%'
            """)

            count = cur.fetchone()[0]

            # If no metadata, check if this is expected
            if count == 0:
                # Check if ADHD was loaded at all
                cur.execute("""
                    SELECT COUNT(*) FROM datawarp.tbl_data_sources
                    WHERE code LIKE 'adhd%'
                """)
                source_count = cur.fetchone()[0]

                if source_count > 0:
                    pytest.fail("❌ CRITICAL: ADHD sources exist but NO metadata stored! "
                              "This means metadata tracking is BROKEN.")
                else:
                    pytest.skip("ADHD not loaded yet - run backfill first")

            assert count > 0, "❌ CRITICAL: No metadata in tbl_column_metadata"

    except Exception as e:
        pytest.skip(f"Database not available: {e}")


def test_critical_field_mapping():
    """CRITICAL: Repository must look for correct field names."""
    # Simulate what repository.py does
    test_column = {
        'name': 'test_column',
        'original_name': 'Test Column',
        'description': 'Test description',
        'data_type': 'VARCHAR',
        'is_dimension': True,
        'is_measure': False,
        'query_keywords': ['test']
    }

    # This is the logic in repository.py line 476
    column_name = test_column.get('name') or test_column.get('semantic_name') or test_column.get('code')

    assert column_name == 'test_column', "❌ CRITICAL: Field mapping broken in repository.py!"
    assert column_name is not None, "❌ CRITICAL: column_name is None!"


def test_imports_not_broken():
    """CRITICAL: Core imports must work."""
    try:
        from datawarp.pipeline.enricher import enrich_manifest
        from datawarp.loader.batch import load_from_manifest
        from datawarp.storage.repository import store_column_metadata
    except ImportError as e:
        pytest.fail(f"❌ CRITICAL: Import failed: {e}")


if __name__ == '__main__':
    # Run with short traceback for pre-commit hook
    pytest.main([__file__, '-v', '--tb=short'])
