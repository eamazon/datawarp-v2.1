"""
HTML Parser for NHS Publication Discovery

Extracts download links from NHS England landing pages.
"""

import re
from typing import List, Set
from urllib.parse import urljoin, urlparse
import requests


def fetch_html(url: str, timeout: int = 30) -> str:
    """Fetch HTML content from URL."""
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def extract_download_links(html: str, base_url: str, extensions: List[str] = None) -> Set[str]:
    """Extract all download links from HTML.

    Args:
        html: HTML content
        base_url: Base URL for resolving relative links
        extensions: List of file extensions to filter (e.g., ['.xlsx', '.zip'])

    Returns:
        Set of absolute URLs to downloadable files
    """
    if extensions is None:
        extensions = ['.xlsx', '.xls', '.zip', '.csv', '.ods']

    # Pattern to match href="..." or href='...'
    link_pattern = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)

    links = set()
    for match in link_pattern.finditer(html):
        href = match.group(1)

        # Check if link ends with desired extension
        if any(href.lower().endswith(ext) for ext in extensions):
            # Convert to absolute URL
            absolute_url = urljoin(base_url, href)
            links.add(absolute_url)

    return links


def extract_nhs_england_links(landing_page_url: str) -> Set[str]:
    """Extract download links from NHS England landing page.

    Convenience function that fetches and parses in one call.
    """
    html = fetch_html(landing_page_url)
    return extract_download_links(html, landing_page_url)
