"""Period parsing and formatting utilities.

Standard period formats:
- Monthly: YYYY-MM (e.g., "2025-11" for November 2025)
- Fiscal Quarter: FYyy-QN (e.g., "FY25-Q1" for Q1 of FY 2025-26, Apr-Jun 2025)
- Fiscal Year: FYyyyy-yy (e.g., "FY2024-25" for April 2024 - March 2025)

NHS fiscal year runs April to March.
"""

import re
from datetime import date
from typing import Tuple, Optional
from calendar import monthrange

# Month name mappings
MONTHS = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
}
MONTH_ABBREV = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June',
               'July', 'August', 'September', 'October', 'November', 'December']


def parse_period(text: str) -> Tuple[Optional[str], int]:
    """Parse period from text and return (period_code, sort_key).

    Args:
        text: Text containing period info (filename, URL, link text)

    Returns:
        Tuple of (period_code, sort_key) where:
        - period_code: Standardized format like "2025-11", "FY25-Q1", "FY2024-25"
        - sort_key: Integer for sorting (YYYYMM format, e.g., 202511)

    Examples:
        "november-2025" -> ("2025-11", 202511)
        "Q1 2024-25" -> ("FY24-Q1", 202406)
        "2024-25" -> ("FY2024-25", 202403)
    """
    text = text.lower().strip()

    # Pattern 1: Fiscal Quarter - "Q1 2024-25", "q3-2024-25", "Q2 FY2024-25"
    m = re.search(r'q\s*(\d)\s*[-_\s]*(?:fy\s*)?(\d{4})[-_](\d{2})', text)
    if m:
        q = int(m.group(1))
        start_year = int(m.group(2))
        # FY quarter end months: Q1=Jun, Q2=Sep, Q3=Dec, Q4=Mar
        end_month = {1: 6, 2: 9, 3: 12, 4: 3}[q]
        end_year = start_year if q < 4 else start_year + 1
        fy_code = f"FY{str(start_year)[-2:]}-Q{q}"
        return fy_code, end_year * 100 + end_month

    # Pattern 2: Month-Year - "november-2025", "nov 2025", "November 2025"
    for name, num in MONTHS.items():
        m = re.search(rf'{name}[-_\s]*(\d{{4}})', text)
        if m:
            year = int(m.group(1))
            return f"{year}-{num:02d}", year * 100 + num

    # Pattern 3: Short month - "nov-25", "nov25", "nov-2025"
    for i, abbrev in enumerate(MONTH_ABBREV):
        m = re.search(rf'\b{abbrev}[-_\s]*(\d{{2,4}})\b', text)
        if m:
            year = int(m.group(1))
            if year < 100:
                year += 2000
            month = i + 1
            return f"{year}-{month:02d}", year * 100 + month

    # Pattern 4: YYYY-MM format (already correct)
    m = re.search(r'(\d{4})-(\d{2})(?!\d)', text)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12:
            return f"{year}-{month:02d}", year * 100 + month

    # Pattern 5: Fiscal year only - "2024-25", "FY2024-25"
    m = re.search(r'(?:fy\s*)?(\d{4})[-_](\d{2})(?!\d)', text)
    if m:
        start_year = int(m.group(1))
        end_year_short = int(m.group(2))
        # Validate it's a fiscal year (end = start + 1)
        if end_year_short == (start_year + 1) % 100:
            return f"FY{start_year}-{end_year_short:02d}", (start_year + 1) * 100 + 3

    return None, 0


def period_to_dates(period: str) -> Tuple[Optional[date], Optional[date]]:
    """Convert period code to start and end dates.

    Args:
        period: Period code like "2025-11", "FY25-Q1", "FY2024-25"

    Returns:
        Tuple of (start_date, end_date) or (None, None) if invalid
    """
    if not period:
        return None, None

    # Monthly: YYYY-MM
    m = re.match(r'^(\d{4})-(\d{2})$', period)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        start = date(year, month, 1)
        _, last_day = monthrange(year, month)
        end = date(year, month, last_day)
        return start, end

    # Fiscal Quarter: FYyy-QN
    m = re.match(r'^FY(\d{2})-Q(\d)$', period)
    if m:
        fy_short = int(m.group(1))
        q = int(m.group(2))
        fy_start_year = 2000 + fy_short if fy_short < 50 else 1900 + fy_short
        # Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar
        quarter_starts = {1: (0, 4), 2: (0, 7), 3: (0, 10), 4: (1, 1)}
        year_offset, start_month = quarter_starts[q]
        start_year = fy_start_year + year_offset
        start = date(start_year, start_month, 1)
        end_month = start_month + 2
        end_year = start_year
        if end_month > 12:
            end_month -= 12
            end_year += 1
        _, last_day = monthrange(end_year, end_month)
        end = date(end_year, end_month, last_day)
        return start, end

    # Fiscal Year: FYyyyy-yy
    m = re.match(r'^FY(\d{4})-(\d{2})$', period)
    if m:
        start_year = int(m.group(1))
        start = date(start_year, 4, 1)  # April 1
        end = date(start_year + 1, 3, 31)  # March 31
        return start, end

    return None, None


def format_period_display(period: str) -> str:
    """Format period code for human display.

    Args:
        period: Period code like "2025-11", "FY25-Q1", "FY2024-25"

    Returns:
        Human-readable string like "Nov 2025", "Q1 FY25", "FY 2024-25"
    """
    if not period:
        return "Unknown"

    # Monthly: YYYY-MM -> "Nov 2025"
    m = re.match(r'^(\d{4})-(\d{2})$', period)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        return f"{MONTH_NAMES[month-1][:3]} {year}"

    # Fiscal Quarter: FYyy-QN -> "Q1 FY25"
    m = re.match(r'^FY(\d{2})-Q(\d)$', period)
    if m:
        return f"Q{m.group(2)} FY{m.group(1)}"

    # Fiscal Year: FYyyyy-yy -> "FY 2024-25"
    m = re.match(r'^FY(\d{4})-(\d{2})$', period)
    if m:
        return f"FY {m.group(1)}-{m.group(2)}"

    return period


def get_fiscal_year(period: str) -> Optional[str]:
    """Get the fiscal year for a period.

    NHS fiscal year runs April to March.

    Args:
        period: Period code like "2025-11", "FY25-Q1"

    Returns:
        Fiscal year code like "FY2025-26" or None if invalid
    """
    start, _ = period_to_dates(period)
    if not start:
        return None

    # Fiscal year starts in April
    if start.month >= 4:
        fy_start = start.year
    else:
        fy_start = start.year - 1

    return f"FY{fy_start}-{(fy_start + 1) % 100:02d}"


def get_fiscal_year_april(period: str) -> Optional[str]:
    """Get the April period for a fiscal year.

    Used to find reference manifests - April is baseline for each FY.

    Args:
        period: Period code like "2025-11", "FY25-Q1"

    Returns:
        April period like "2025-04" or None if invalid
    """
    start, _ = period_to_dates(period)
    if not start:
        return None

    # Fiscal year starts in April
    if start.month >= 4:
        april_year = start.year
    else:
        april_year = start.year - 1

    return f"{april_year}-04"


def is_first_of_fiscal_year(period: str) -> bool:
    """Check if period is April (first month of fiscal year)."""
    return period.endswith("-04") if period else False
