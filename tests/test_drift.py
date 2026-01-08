"""
Tests for drift detection.
"""

import pytest
from datawarp.core.drift import DriftResult, detect_drift


def test_detect_drift_no_changes():
    """Test when columns are identical."""
    file_cols = ['id', 'name', 'value']
    db_cols = ['id', 'name', 'value']
    
    result = detect_drift(file_cols, db_cols)
    
    assert result.new_columns == []
    assert result.missing_columns == []
    assert not result.has_changes


def test_detect_drift_new_columns():
    """Test when file has new columns."""
    file_cols = ['id', 'name', 'value', 'new_col']
    db_cols = ['id', 'name', 'value']
    
    result = detect_drift(file_cols, db_cols)
    
    assert result.new_columns == ['new_col']
    assert result.missing_columns == []
    assert result.has_changes


def test_detect_drift_missing_columns():
    """Test when file is missing columns from DB."""
    file_cols = ['id', 'name']
    db_cols = ['id', 'name', 'value']
    
    result = detect_drift(file_cols, db_cols)
    
    assert result.new_columns == []
    assert result.missing_columns == ['value']
    assert result.has_changes


def test_detect_drift_both_changes():
    """Test when there are both new and missing columns."""
    file_cols = ['id', 'name', 'new_a', 'new_b']
    db_cols = ['id', 'name', 'old_a', 'old_b']
    
    result = detect_drift(file_cols, db_cols)
    
    assert sorted(result.new_columns) == ['new_a', 'new_b']
    assert sorted(result.missing_columns) == ['old_a', 'old_b']
    assert result.has_changes


def test_detect_drift_empty_db():
    """Test when database has no columns (new table)."""
    file_cols = ['id', 'name', 'value']
    db_cols = []
    
    result = detect_drift(file_cols, db_cols)
    
    assert sorted(result.new_columns) == ['id', 'name', 'value']
    assert result.missing_columns == []
    assert result.has_changes


def test_drift_result_sorted():
    """Test that results are sorted."""
    file_cols = ['z', 'a', 'm']
    db_cols = []
    
    result = detect_drift(file_cols, db_cols)
    
    # Should be alphabetically sorted
    assert result.new_columns == ['a', 'm', 'z']
