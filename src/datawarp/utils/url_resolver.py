"""
URL Resolver for DataWarp Publications

Resolves URLs from publications.yaml based on discovery_mode:
- template: Generate URL from url_template + landing_page + period
- explicit: Return URL from urls list
- scrape: Raise NotImplementedError (requires landing page scraping)

Usage:
    from datawarp.utils.url_resolver import resolve_urls, resolve_url

    # Get all resolved URLs for a publication
    urls = resolve_urls(pub_config)
    for period, url in urls:
        print(f"{period}: {url}")

    # Get URL for a specific period
    url = resolve_url(pub_config, "2025-11")
"""

import calendar
from datetime import date
from typing import Dict, Iterator, List, Optional, Tuple


# Month name mapping for URL generation
MONTH_NAMES = {
    1: 'january', 2: 'february', 3: 'march', 4: 'april',
    5: 'may', 6: 'june', 7: 'july', 8: 'august',
    9: 'september', 10: 'october', 11: 'november', 12: 'december'
}


def _parse_period(period: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Parse period string to year, month, quarter components.

    Returns: (year, month, quarter) - month/quarter may be None for FY periods
    """
    # Monthly: YYYY-MM
    if len(period) == 7 and period[4] == '-':
        try:
            year = int(period[:4])
            month = int(period[5:7])
            return (year, month, None)
        except ValueError:
            pass

    # Fiscal Quarter: FYyy-QN
    if period.startswith('FY') and '-Q' in period:
        try:
            parts = period[2:].split('-Q')
            fy_year = int(parts[0])
            quarter = int(parts[1])
            # Convert to full year (FY25 = 2025)
            if fy_year < 100:
                fy_year = 2000 + fy_year
            return (fy_year, None, quarter)
        except (ValueError, IndexError):
            pass

    # Fiscal Year: FYyyyy-yy
    if period.startswith('FY') and '-' in period and 'Q' not in period:
        try:
            parts = period[2:].split('-')
            fy_year = int(parts[0])
            return (fy_year, None, None)
        except (ValueError, IndexError):
            pass

    return (None, None, None)


def _get_last_day_of_month(year: int, month: int) -> int:
    """Get the last day of a month."""
    return calendar.monthrange(year, month)[1]


def _generate_url_from_template(
    template: str,
    landing_page: str,
    period: str
) -> Optional[str]:
    """Generate URL from template and period.

    Supported placeholders:
    - {landing_page}: The landing page URL
    - {month_name}: Full month name (e.g., "november")
    - {year}: 4-digit year (e.g., "2025")
    - {day}: Last day of month (e.g., "30")
    - {pub_year}: Publication year (for SHMI offset)
    - {pub_month}: Publication month as 2-digit (for SHMI offset)
    """
    year, month, quarter = _parse_period(period)

    if year is None:
        return None

    replacements = {
        'landing_page': landing_page.rstrip('/'),
    }

    if month is not None:
        replacements['month_name'] = MONTH_NAMES[month]
        replacements['year'] = str(year)
        replacements['day'] = str(_get_last_day_of_month(year, month))

        # SHMI special case: publication date is ~5 months after data end
        pub_date = date(year, month, 1)
        # Add 5 months
        pub_month = month + 5
        pub_year = year
        if pub_month > 12:
            pub_month -= 12
            pub_year += 1
        replacements['pub_year'] = str(pub_year)
        replacements['pub_month'] = f"{pub_month:02d}"

    elif quarter is not None:
        # Fiscal quarter - convert to dates
        # Q1 = Apr-Jun, Q2 = Jul-Sep, Q3 = Oct-Dec, Q4 = Jan-Mar
        quarter_months = {1: 4, 2: 7, 3: 10, 4: 1}
        quarter_year = year if quarter != 4 else year + 1
        replacements['quarter'] = str(quarter)
        replacements['year'] = str(year)
        replacements['fy_year'] = f"{year % 100:02d}-{(year + 1) % 100:02d}"

    # Apply replacements
    url = template
    for key, value in replacements.items():
        url = url.replace(f'{{{key}}}', value)

    return url


def resolve_urls(pub_config: Dict) -> Iterator[Tuple[str, str]]:
    """Resolve all URLs for a publication.

    Args:
        pub_config: Publication configuration dict from publications.yaml

    Yields:
        Tuples of (period, url)

    Raises:
        NotImplementedError: If discovery_mode is 'scrape'
    """
    discovery_mode = pub_config.get('discovery_mode', 'explicit')

    if discovery_mode == 'scrape':
        raise NotImplementedError(
            f"Scrape mode not yet implemented. "
            f"Landing page: {pub_config.get('landing_page')}"
        )

    if discovery_mode == 'template':
        template = pub_config.get('url_template')
        landing_page = pub_config.get('landing_page')
        periods = pub_config.get('periods', [])

        if not template or not landing_page:
            return

        for period in periods:
            url = _generate_url_from_template(template, landing_page, period)
            if url:
                yield (period, url)

    else:  # explicit
        urls = pub_config.get('urls', [])
        for entry in urls:
            period = entry.get('period')
            url = entry.get('url')
            if period and url:
                yield (period, url)


def resolve_url(pub_config: Dict, period: str) -> Optional[str]:
    """Resolve a single URL for a specific period.

    Args:
        pub_config: Publication configuration dict from publications.yaml
        period: Period code (e.g., "2025-11", "FY25-Q1")

    Returns:
        Resolved URL or None if not found
    """
    discovery_mode = pub_config.get('discovery_mode', 'explicit')

    if discovery_mode == 'scrape':
        raise NotImplementedError(
            f"Scrape mode not yet implemented. "
            f"Landing page: {pub_config.get('landing_page')}"
        )

    if discovery_mode == 'template':
        template = pub_config.get('url_template')
        landing_page = pub_config.get('landing_page')
        periods = pub_config.get('periods', [])

        if period not in periods:
            return None

        return _generate_url_from_template(template, landing_page, period)

    else:  # explicit
        urls = pub_config.get('urls', [])
        for entry in urls:
            if entry.get('period') == period:
                return entry.get('url')
        return None


def get_all_periods(pub_config: Dict) -> List[str]:
    """Get all available periods for a publication.

    Args:
        pub_config: Publication configuration dict from publications.yaml

    Returns:
        List of period codes
    """
    discovery_mode = pub_config.get('discovery_mode', 'explicit')

    if discovery_mode == 'template':
        return pub_config.get('periods', [])
    else:
        return [entry.get('period') for entry in pub_config.get('urls', []) if entry.get('period')]


def is_templatable(pub_config: Dict) -> bool:
    """Check if a publication uses URL templates."""
    return pub_config.get('discovery_mode') == 'template'
