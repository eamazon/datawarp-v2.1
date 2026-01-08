"""Simple data models for DataWarp v2 - dataclasses, no ORM."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List


@dataclass
class Source:
    """A registered data source."""
    id: Optional[int] = None
    code: str = ""
    name: str = ""
    table_name: str = ""
    schema_name: str = "staging"
    default_sheet: Optional[str] = None
    created_at: Optional[datetime] = None
    last_load_at: Optional[datetime] = None


@dataclass
class LoadEvent:
    """Audit log of a load."""
    id: Optional[int] = None
    source_id: int = 0
    file_url: str = ""
    rows_loaded: int = 0
    columns_added: Optional[List[str]] = None
    duration_ms: int = 0
    created_at: Optional[datetime] = None
