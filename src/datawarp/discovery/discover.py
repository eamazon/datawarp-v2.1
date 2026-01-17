"""
Main Discovery Logic

Discovers download URLs for NHS England publications at runtime.
"""

import logging
from typing import Optional, Dict
from .html_parser import extract_nhs_england_links
from .url_matcher import find_url_for_period

logger = logging.getLogger(__name__)


def discover_url_for_period(landing_page: str, period: str,
                            file_pattern: Optional[str] = None,
                            cache: Optional[Dict] = None) -> Optional[str]:
    """Discover download URL for a specific period.

    Args:
        landing_page: URL of the landing page containing links
        period: Period string like "2025-11"
        file_pattern: Optional pattern to match (e.g., "Incomplete-Commissioner")
        cache: Optional cache dict to avoid re-fetching

    Returns:
        Download URL for the period, or None if not found

    Raises:
        requests.RequestException: If landing page fetch fails
    """
    # Check cache first
    if cache and landing_page in cache:
        urls = cache[landing_page]
        logger.debug(f"Using cached URLs for {landing_page}")
    else:
        # Fetch links from landing page
        logger.info(f"Discovering URLs from {landing_page}")
        urls = list(extract_nhs_england_links(landing_page))
        logger.info(f"Found {len(urls)} download links")

        # Update cache
        if cache is not None:
            cache[landing_page] = urls

    # Find matching URL for period
    matched_url = find_url_for_period(urls, period, file_pattern)

    if matched_url:
        logger.info(f"Discovered URL for period {period}: {matched_url}")
    else:
        logger.warning(f"No URL found for period {period} (pattern: {file_pattern})")

    return matched_url


def discover_urls_for_periods(landing_page: str, periods: list,
                              file_pattern: Optional[str] = None) -> Dict[str, Optional[str]]:
    """Discover URLs for multiple periods with caching.

    Args:
        landing_page: URL of the landing page
        periods: List of period strings
        file_pattern: Optional pattern to match

    Returns:
        Dict mapping period → URL (or None if not found)
    """
    cache = {}  # Single fetch, reuse for all periods
    results = {}

    for period in periods:
        url = discover_url_for_period(landing_page, period, file_pattern, cache)
        results[period] = url

    return results
