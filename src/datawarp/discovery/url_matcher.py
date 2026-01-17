"""
URL Matcher for Period-based File Discovery

Matches URLs to specific periods based on patterns.
"""

import re
from typing import Optional, List
from urllib.parse import urlparse


# Month name mappings
MONTH_NAMES_FULL = {
    1: 'january', 2: 'february', 3: 'march', 4: 'april',
    5: 'may', 6: 'june', 7: 'july', 8: 'august',
    9: 'september', 10: 'october', 11: 'november', 12: 'december'
}

MONTH_ABBREV_3 = {
    1: 'jan', 2: 'feb', 3: 'mar', 4: 'apr', 5: 'may', 6: 'jun',
    7: 'jul', 8: 'aug', 9: 'sep', 10: 'oct', 11: 'nov', 12: 'dec'
}

# NHS England uses capitalized 3-letter abbrev (Jan, Feb, Mar)
MONTH_ABBREV_NHS = {
    1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
    7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
}


def period_to_month_patterns(period: str) -> List[str]:
    """Convert period (YYYY-MM) to possible month representations.

    Args:
        period: Period string like "2025-11"

    Returns:
        List of possible month patterns: ["Nov25", "november-2025", "2025-11", etc.]
    """
    year_str, month_str = period.split('-')
    year = int(year_str)
    month = int(month_str)
    year_short = year % 100  # 2025 → 25

    patterns = [
        f"{MONTH_ABBREV_NHS[month]}{year_short:02d}",  # Nov25
        f"{MONTH_ABBREV_3[month]}{year_short:02d}",    # nov25
        f"{MONTH_ABBREV_NHS[month]}{year}",            # Nov2025 (NHS Digital Maternity)
        f"{MONTH_ABBREV_3[month]}{year}",              # nov2025 (NHS Digital Maternity)
        f"{MONTH_NAMES_FULL[month]}-{year}",            # november-2025
        f"{MONTH_NAMES_FULL[month]}_{year}",            # november_2025
        f"{MONTH_NAMES_FULL[month].title()} {year}",   # November 2025 (NHS England)
        f"{MONTH_ABBREV_NHS[month]} {year}",           # Nov 2025 (NHS England)
        f"{MONTH_ABBREV_NHS[month]}-{year}",           # Nov-2025 (NHS England Cancer)
        f"{MONTH_ABBREV_3[month]}-{year}",             # nov-2025
        f"{year}{month:02d}",                           # 202511 (YYYYMM for Ambulance)
        f"{year}-{month:02d}",                           # 2025-11
        f"{year}_{month:02d}",                           # 2025_11
        f"{month:02d}-{year}",                           # 11-2025
    ]

    return patterns


def match_url_to_period(url: str, period: str, file_pattern: Optional[str] = None) -> bool:
    """Check if URL matches the given period.

    Args:
        url: Full URL to check
        period: Period string like "2025-11"
        file_pattern: Optional pattern like "Incomplete-Commissioner" to match

    Returns:
        True if URL appears to be for this period
    """
    url_lower = url.lower()
    path = urlparse(url).path

    # Get all possible month patterns for this period
    patterns = period_to_month_patterns(period)

    # Check if any pattern appears in URL
    found_period = False
    for pattern in patterns:
        if pattern.lower() in url_lower:
            found_period = True
            break

    if not found_period:
        return False

    # If file_pattern specified, check for it too
    if file_pattern:
        pattern_lower = file_pattern.lower()
        # Replace placeholders in pattern
        pattern_lower = re.sub(r'\{month\w*\}', '', pattern_lower)
        pattern_lower = re.sub(r'\{year\w*\}', '', pattern_lower)
        pattern_lower = re.sub(r'\{yy\}', '', pattern_lower)
        # Normalize separators and remove parentheses for flexible matching
        pattern_normalized = re.sub(r'[()_\s-]+', ' ', pattern_lower).strip()
        url_normalized = re.sub(r'[()_\s-]+', ' ', url_lower)

        if pattern_normalized and pattern_normalized not in url_normalized:
            return False

    return True


def find_url_for_period(urls: List[str], period: str, file_pattern: Optional[str] = None) -> Optional[str]:
    """Find the best matching URL for a given period.

    Args:
        urls: List of candidate URLs
        period: Period string like "2025-11"
        file_pattern: Optional pattern to match

    Returns:
        Best matching URL or None if no match
    """
    matches = []

    for url in urls:
        if match_url_to_period(url, period, file_pattern):
            matches.append(url)

    if not matches:
        return None

    # If multiple matches, prefer:
    # 1. Final data over provisional (NHS maternity services)
    # 2. Shortest URL (less likely to be a revision/variant)
    # 3. First alphabetically (deterministic)
    def sort_key(url):
        # Prefer URLs without "provisional" or "prov" in name
        is_provisional = 'provisional' in url.lower() or 'prov' in url.lower()
        return (is_provisional, len(url), url)

    matches.sort(key=sort_key)

    return matches[0]
