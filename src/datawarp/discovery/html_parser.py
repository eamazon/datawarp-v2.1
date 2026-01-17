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


def extract_publication_subpage_links(html: str, base_url: str) -> Set[str]:
    """Extract publication sub-page links from NHS Digital landing pages.

    Args:
        html: HTML content
        base_url: Base URL for resolving relative links

    Returns:
        Set of absolute URLs to publication sub-pages
    """
    # Pattern to match publication URLs (e.g., /maternity.../final-october-2025-...)
    link_pattern = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)

    parsed_base = urlparse(base_url)
    base_path = parsed_base.path.rstrip('/')

    links = set()
    for match in link_pattern.finditer(html):
        href = match.group(1)

        # Check if this looks like a publication sub-page
        # (starts with same base path, longer than base path, no file extension)
        if href.startswith(base_path) and len(href) > len(base_path) + 1:
            # Exclude links with file extensions or anchors
            if not any(href.lower().endswith(ext) for ext in ['.xlsx', '.xls', '.pdf', '.zip', '.csv', '.ods']):
                if '#' not in href:
                    absolute_url = urljoin(base_url, href)
                    links.add(absolute_url)

    return links


def extract_nhs_england_links(landing_page_url: str) -> Set[str]:
    """Extract download links from NHS England/Digital landing pages.

    Handles two structures:
    1. NHS England: Direct Excel links on landing page
    2. NHS Digital: Sub-pages → Excel links (two-level)

    Convenience function that fetches and parses in one call.
    """
    html = fetch_html(landing_page_url)

    # First, try to find direct download links (NHS England style)
    direct_links = extract_download_links(html, landing_page_url)

    if direct_links:
        return direct_links

    # No direct links found - try NHS Digital two-level structure
    # Extract publication sub-page links
    subpage_urls = extract_publication_subpage_links(html, landing_page_url)

    all_download_links = set()
    for subpage_url in subpage_urls:
        try:
            subpage_html = fetch_html(subpage_url)
            download_links = extract_download_links(subpage_html, subpage_url)
            all_download_links.update(download_links)
        except Exception as e:
            # Log but continue with other sub-pages
            import logging
            logging.getLogger(__name__).warning(f"Failed to fetch {subpage_url}: {e}")
            continue

    return all_download_links
