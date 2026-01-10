"""Tests for load validation functionality."""

import pytest
from datawarp.loader.pipeline import validate_load, LoadResult


def test_validate_successful_load():
    """Validation should pass for normal successful loads."""
    result = LoadResult(
        success=True,
        rows_loaded=1000,
        table_name="staging.test_table",
        columns_added=[],
        duration_ms=500
    )

    validated = validate_load(result)
    assert validated.success is True
    assert validated.rows_loaded == 1000


def test_validate_zero_rows_raises_error():
    """Validation should raise ValueError for 0-row loads."""
    result = LoadResult(
        success=True,
        rows_loaded=0,
        table_name="staging.test_table",
        columns_added=[],
        duration_ms=500
    )

    with pytest.raises(ValueError, match="Validation failed: Loaded 0 rows"):
        validate_load(result)


def test_validate_low_rows_logs_warning(caplog):
    """Validation should log warning for low row counts but still succeed."""
    result = LoadResult(
        success=True,
        rows_loaded=50,  # Below default threshold of 100
        table_name="staging.test_table",
        columns_added=[],
        duration_ms=500
    )

    validated = validate_load(result)
    assert validated.success is True
    assert validated.rows_loaded == 50
    assert "Low row count" in caplog.text


def test_validate_custom_threshold():
    """Validation should respect custom min_rows threshold."""
    result = LoadResult(
        success=True,
        rows_loaded=500,
        table_name="staging.test_table",
        columns_added=[],
        duration_ms=500
    )

    # Should pass with default threshold (100)
    validated = validate_load(result, expected_min_rows=100)
    assert validated.success is True

    # Should log warning with higher threshold (1000)
    validated = validate_load(result, expected_min_rows=1000)
    assert validated.success is True


def test_validate_skips_already_failed_loads():
    """Validation should skip loads that already failed."""
    result = LoadResult(
        success=False,
        rows_loaded=0,
        table_name="",
        columns_added=[],
        duration_ms=500,
        error="Some error"
    )

    # Should not raise even though rows_loaded is 0
    validated = validate_load(result)
    assert validated.success is False
    assert validated.error == "Some error"
