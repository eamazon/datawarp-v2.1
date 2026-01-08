"""
Basic tests for FileExtractor.
"""

import pytest
from pathlib import Path
from datawarp.core.extractor import (
    FileExtractor,
    TableStructure,
    SheetType,
    DataOrientation,
    FirstColumnType
)


def test_file_extractor_imports():
    """Test that FileExtractor can be imported."""
    assert FileExtractor is not None
    assert TableStructure is not None


def test_sheet_type_enum():
    """Test SheetType enum values."""
    assert SheetType.TABULAR
    assert SheetType.METADATA
    assert SheetType.EMPTY
    assert SheetType.UNRECOGNISED


def test_data_orientation_enum():
    """Test DataOrientation enum values."""
    assert DataOrientation.VERTICAL
    assert DataOrientation.HORIZONTAL


def test_first_column_type_enum():
    """Test FirstColumnType enum values."""
    assert FirstColumnType.FISCAL_YEAR
    assert FirstColumnType.CALENDAR_YEAR
    assert FirstColumnType.MONTH_YEAR
    assert FirstColumnType.QUARTER
    assert FirstColumnType.ORG_CODE
    assert FirstColumnType.CATEGORY
    assert FirstColumnType.UNKNOWN


# Integration tests will be added once we have test fixtures
