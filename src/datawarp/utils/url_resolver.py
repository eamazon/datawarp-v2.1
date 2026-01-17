"""
URL Resolver for DataWarp Publications

Resolves periods and URLs from publications.yaml based on configuration.

Period Discovery Modes:
- schedule: Generate periods from start→end with publication_lag filter
- manual: Use explicit periods/urls list

URL Generation Modes:
- template: Generate URL from pattern + period
- explicit: Return stored URL from urls list
"""

import calendar
from datetime import date
from dateutil.relativedelta import relativedelta
from typing import Dict, Iterator, List, Optional, Tuple

TODAY = date.today()

MONTH_NAMES = {
    1: 'january', 2: 'february', 3: 'march', 4: 'april',
    5: 'may', 6: 'june', 7: 'july', 8: 'august',
    9: 'september', 10: 'october', 11: 'november', 12: 'december'
}


def _parse_period(period: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Parse period string. Returns (year, month, quarter)."""
    if len(period) == 7 and period[4] == '-':
        try:
            return int(period[:4]), int(period[5:7]), None
        except ValueError:
            pass
    if period.startswith('FY') and '-Q' in period:
        try:
            parts = period[2:].split('-Q')
            fy = int(parts[0])
            return (2000 + fy if fy < 100 else fy), None, int(parts[1])
        except (ValueError, IndexError):
            pass
    return None, None, None


def _get_last_day(year: int, month: int) -> int:
    """Get last day of month."""
    return calendar.monthrange(year, month)[1]


def _generate_schedule_periods(config: Dict) -> List[str]:
    """Generate periods from schedule configuration."""
    periods_cfg = config.get('periods', {})
    if periods_cfg.get('mode') != 'schedule':
        return []

    start = periods_cfg.get('start', '2024-01')
    end = periods_cfg.get('end', 'current')
    months_filter = periods_cfg.get('months')  # e.g., [5, 8, 11] for quarterly
    lag_weeks = periods_cfg.get('publication_lag_weeks', 6)
    offset_months = periods_cfg.get('publication_offset_months', 0)
    period_type = periods_cfg.get('type', 'monthly')

    # Parse start
    start_year, start_month = int(start[:4]), int(start[5:7])
    current = date(start_year, start_month, 1)

    # Calculate end date with publication lag
    if end == 'current':
        end_date = TODAY - relativedelta(weeks=lag_weeks)
    else:
        end_year, end_month = int(end[:4]), int(end[5:7])
        end_date = date(end_year, end_month, _get_last_day(end_year, end_month))

    periods = []

    if period_type == 'fiscal_quarter':
        # Fiscal quarter generation (FY25-Q1 format)
        start_fy = periods_cfg.get('start_fy', 2025)
        fy, q = start_fy, 1
        while True:
            # Calculate quarter end date
            q_ends = {1: (fy - 1, 6, 30), 2: (fy - 1, 9, 30), 3: (fy - 1, 12, 31), 4: (fy, 3, 31)}
            q_end = date(*q_ends[q])
            pub_date = q_end + relativedelta(weeks=lag_weeks)
            if pub_date > TODAY:
                break
            periods.append(f"FY{fy % 100:02d}-Q{q}")
            q += 1
            if q > 4:
                q, fy = 1, fy + 1
            if len(periods) > 50:
                break
    else:
        # Monthly period generation
        while current <= end_date:
            if months_filter is None or current.month in months_filter:
                # Apply publication offset for SHMI-style sources
                if offset_months:
                    pub_month = current + relativedelta(months=offset_months)
                    if pub_month.replace(day=1) <= TODAY:
                        periods.append(f"{current.year}-{current.month:02d}")
                else:
                    periods.append(f"{current.year}-{current.month:02d}")
            current += relativedelta(months=1)

    return periods


def _generate_url(template: str, landing_page: str, period: str,
                  offset_months: int = 0, exceptions: Dict = None) -> Optional[str]:
    """Generate URL from template and period."""
    # Check for exception first
    if exceptions and period in exceptions:
        template = exceptions[period]

    year, month, quarter = _parse_period(period)
    if year is None:
        return None

    url = template.replace("{landing_page}", landing_page.rstrip('/'))

    if month:
        url = url.replace("{month_name}", MONTH_NAMES[month])
        url = url.replace("{year}", str(year))
        url = url.replace("{day}", str(_get_last_day(year, month)))

        # Publication offset (for SHMI)
        if offset_months:
            pub = date(year, month, 1) + relativedelta(months=offset_months)
            url = url.replace("{pub_year}", str(pub.year))
            url = url.replace("{pub_month}", f"{pub.month:02d}")

    if quarter:
        url = url.replace("{quarter}", str(quarter))
        url = url.replace("{fy}", f"{year % 100:02d}")

    return url


def resolve_urls(pub_config: Dict) -> Iterator[Tuple[str, str]]:
    """Resolve all period/URL pairs for a publication.

    Yields: (period, url) tuples
    """
    periods_cfg = pub_config.get('periods', {})
    url_cfg = pub_config.get('url', {})
    landing_page = pub_config.get('landing_page', '')

    # Determine periods
    if periods_cfg.get('mode') == 'schedule':
        periods = _generate_schedule_periods(pub_config)
    else:
        # Manual/explicit mode - get from urls list or periods list
        if 'urls' in pub_config:
            for entry in pub_config['urls']:
                yield entry.get('period'), entry.get('url')
            return
        periods = pub_config.get('periods', [])
        if isinstance(periods, dict):
            periods = []

    # Generate URLs for each period
    url_mode = url_cfg.get('mode', 'template') if isinstance(url_cfg, dict) else 'template'

    if url_mode == 'template':
        pattern = url_cfg.get('pattern', '') if isinstance(url_cfg, dict) else pub_config.get('url_template', '')
        exceptions = url_cfg.get('exceptions', {}) if isinstance(url_cfg, dict) else {}
        offset = pub_config.get('periods', {}).get('publication_offset_months', 0)

        for period in periods:
            url = _generate_url(pattern, landing_page, period, offset, exceptions)
            if url:
                yield period, url
    else:
        # Explicit URLs - lookup from urls list
        url_map = {u['period']: u['url'] for u in pub_config.get('urls', [])}
        for period in periods:
            if period in url_map:
                yield period, url_map[period]


def get_all_periods(pub_config: Dict) -> List[str]:
    """Get all available periods for a publication."""
    periods_cfg = pub_config.get('periods', {})

    if periods_cfg.get('mode') == 'schedule':
        return _generate_schedule_periods(pub_config)
    elif 'urls' in pub_config:
        return [u.get('period') for u in pub_config['urls'] if u.get('period')]
    elif isinstance(periods_cfg, list):
        return periods_cfg
    else:
        return pub_config.get('periods', []) if isinstance(pub_config.get('periods'), list) else []


def is_schedule_mode(pub_config: Dict) -> bool:
    """Check if publication uses schedule-based period discovery."""
    return pub_config.get('periods', {}).get('mode') == 'schedule'
