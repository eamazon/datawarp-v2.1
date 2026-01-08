"""Simple drift handling. No policies, just facts."""

from typing import List
from dataclasses import dataclass


@dataclass
class DriftResult:
    """What changed between file and database."""
    new_columns: List[str]      # In file, not in DB → ADD
    missing_columns: List[str]  # In DB, not in file → INSERT NULL
    
    @property
    def has_changes(self) -> bool:
        return bool(self.new_columns or self.missing_columns)


def detect_drift(
    file_columns: List[str],
    db_columns: List[str]
) -> DriftResult:
    """Compare file columns against database columns."""
    file_set = set(file_columns)
    db_set = set(db_columns)
    
    return DriftResult(
        new_columns=sorted(file_set - db_set),
        missing_columns=sorted(db_set - file_set)
    )
