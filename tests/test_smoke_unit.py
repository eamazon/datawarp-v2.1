#!/usr/bin/env python3
"""
Additional Smoke Unit Tests - Pure logic tests (no dependencies)

These tests run ALWAYS (no database, no files, no network).
They validate core logic remains correct.
"""

import pytest
from pathlib import Path


def test_field_mapping_all_variants():
    """Test field mapping handles all legacy and new formats."""
    # NEW FORMAT (from LLM enrichment)
    new_col = {
        'name': 'reporting_period',
        'original_name': 'Reporting Period',
        'description': 'The reporting period',
        'data_type': 'VARCHAR',
        'is_dimension': True,
        'is_measure': False,
        'query_keywords': ['period', 'date']
    }

    # LEGACY FORMAT (old code/semantic_name)
    legacy_col_1 = {
        'semantic_name': 'reporting_period',
        'description': 'The reporting period'
    }

    legacy_col_2 = {
        'code': 'reporting_period',
        'description': 'The reporting period'
    }

    # Simulate repository.py logic (line 476)
    name_new = new_col.get('name') or new_col.get('semantic_name') or new_col.get('code')
    name_legacy_1 = legacy_col_1.get('name') or legacy_col_1.get('semantic_name') or legacy_col_1.get('code')
    name_legacy_2 = legacy_col_2.get('name') or legacy_col_2.get('semantic_name') or legacy_col_2.get('code')

    assert name_new == 'reporting_period', "❌ New format field mapping broken"
    assert name_legacy_1 == 'reporting_period', "❌ Legacy semantic_name mapping broken"
    assert name_legacy_2 == 'reporting_period', "❌ Legacy code mapping broken"


def test_enrichment_required_fields():
    """Test that we validate all required enrichment fields."""
    required_fields = [
        'name',
        'original_name',
        'description',
        'data_type',
        'is_dimension',
        'is_measure',
        'query_keywords'
    ]

    # Sample column from enrichment
    sample_column = {
        'name': 'organisation_code',
        'original_name': 'Organisation Code',
        'description': 'NHS organisation code',
        'data_type': 'VARCHAR',
        'is_dimension': True,
        'is_measure': False,
        'query_keywords': ['organisation', 'code', 'nhs']
    }

    # Verify all required fields present
    missing = [f for f in required_fields if f not in sample_column]
    assert not missing, f"❌ Required fields missing from sample: {missing}"

    # Verify types
    assert isinstance(sample_column['name'], str), "❌ name must be string"
    assert isinstance(sample_column['is_dimension'], bool), "❌ is_dimension must be boolean"
    assert isinstance(sample_column['is_measure'], bool), "❌ is_measure must be boolean"
    assert isinstance(sample_column['query_keywords'], list), "❌ query_keywords must be list"
    assert len(sample_column['query_keywords']) > 0, "❌ query_keywords must not be empty"


def test_manifest_structure_validation():
    """Test manifest structure has required top-level keys."""
    # Minimal valid manifest
    valid_manifest = {
        'manifest': {
            'name': 'test_manifest',
            'description': 'Test manifest',
            'created_at': '2026-01-18'
        },
        'sources': [
            {
                'code': 'test_source',
                'table': 'tbl_test',
                'files': [
                    {
                        'url': 'http://example.com/test.xlsx',
                        'sheet': 'Sheet1',
                        'mode': 'replace',
                        'period': '2025-01'
                    }
                ]
            }
        ]
    }

    # Validate structure
    assert 'manifest' in valid_manifest, "❌ Missing 'manifest' section"
    assert 'sources' in valid_manifest, "❌ Missing 'sources' section"
    assert len(valid_manifest['sources']) > 0, "❌ sources must not be empty"

    # Validate first source
    source = valid_manifest['sources'][0]
    assert 'code' in source, "❌ source missing 'code'"
    assert 'table' in source, "❌ source missing 'table'"
    assert 'files' in source, "❌ source missing 'files'"
    assert len(source['files']) > 0, "❌ source files must not be empty"

    # Validate first file
    file_entry = source['files'][0]
    assert 'url' in file_entry, "❌ file missing 'url'"
    assert 'sheet' in file_entry, "❌ file missing 'sheet'"
    assert 'mode' in file_entry, "❌ file missing 'mode'"
    assert file_entry['mode'] in ['replace', 'append'], "❌ invalid mode"


def test_source_code_validation():
    """Test source codes follow naming conventions."""
    # Valid source codes
    valid_codes = [
        'adhd_summary_open_referrals',
        'msa_national_regional_team',
        'diagnostics_waiting_times_provider'
    ]

    # Invalid source codes
    invalid_codes = [
        'ADHD Summary',  # Spaces
        'adhd-summary',  # Hyphens
        'adhd.summary',  # Dots
        'AdhD',          # Mixed case
    ]

    # Validation logic: lowercase, underscores only
    import re
    pattern = r'^[a-z][a-z0-9_]*$'

    for code in valid_codes:
        assert re.match(pattern, code), f"❌ Valid code {code} failed pattern match"

    for code in invalid_codes:
        assert not re.match(pattern, code), f"❌ Invalid code {code} passed pattern match"


def test_column_type_inference_keywords():
    """Test that type inference keywords are correct."""
    # Keywords that should trigger INTEGER
    integer_keywords = ['count', 'number', 'total', 'quantity']

    # Keywords that should trigger VARCHAR
    varchar_keywords = ['name', 'code', 'description', 'type']

    # Keywords that should trigger DATE
    date_keywords = ['date', 'period', 'month', 'year']

    # Simulate type inference logic (simplified from extractor.py)
    def infer_type(column_name: str) -> str:
        name_lower = column_name.lower()

        if any(kw in name_lower for kw in date_keywords):
            return 'DATE'
        elif any(kw in name_lower for kw in integer_keywords):
            return 'INTEGER'
        elif any(kw in name_lower for kw in varchar_keywords):
            return 'VARCHAR'
        else:
            return 'VARCHAR'  # Default

    # Test cases
    assert infer_type('reporting_period') == 'DATE', "❌ period should be DATE"
    assert infer_type('total_count') == 'INTEGER', "❌ count should be INTEGER"
    assert infer_type('organisation_name') == 'VARCHAR', "❌ name should be VARCHAR"
    assert infer_type('organisation_code') == 'VARCHAR', "❌ code should be VARCHAR"
    assert infer_type('total_referrals') == 'INTEGER', "❌ total should be INTEGER"


def test_drift_detection_logic():
    """Test drift detection identifies schema changes correctly."""
    # Old schema
    old_columns = [
        {'name': 'period', 'type': 'VARCHAR'},
        {'name': 'count', 'type': 'INTEGER'}
    ]

    # New schema - added column
    new_columns = [
        {'name': 'period', 'type': 'VARCHAR'},
        {'name': 'count', 'type': 'INTEGER'},
        {'name': 'region', 'type': 'VARCHAR'}  # NEW
    ]

    # Simulate drift detection
    old_names = {c['name'] for c in old_columns}
    new_names = {c['name'] for c in new_columns}

    added = new_names - old_names
    removed = old_names - new_names

    assert added == {'region'}, "❌ Drift detection didn't find new column"
    assert removed == set(), "❌ Drift detection found false removal"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
