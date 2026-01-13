"""Canonicalize source codes by removing date/period patterns.

This module ensures cross-period consolidation by stripping temporal identifiers
from LLM-generated source codes, enabling consistent table naming across periods.
"""
import re
from typing import Dict, List


def remove_date_patterns(code: str) -> str:
    """Remove date/period patterns from source code.

    Examples:
        adhd_may25_data → adhd_data
        pcn_workforce_apr2024 → pcn_workforce
        mhsds_historic_2025_05 → mhsds_historic

    Args:
        code: Original source code (may contain dates)

    Returns:
        Canonical code with date patterns removed
    """
    canonical = code

    # Remove month-year combined patterns FIRST (may25, apr2024, etc.)
    # This must come before individual month/year removal to avoid partial matches
    canonical = re.sub(
        r'_(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\d{2,4}',
        '', canonical, flags=re.IGNORECASE
    )

    # Remove ISO date patterns (2025_05, 2025-05, etc.)
    canonical = re.sub(r'_?\d{4}[-_]\d{2}', '', canonical)

    # Remove year patterns (2023, 2024, 2025, etc.)
    canonical = re.sub(r'_?20\d{2}', '', canonical)

    # Remove month names (full)
    canonical = re.sub(
        r'_(january|february|march|april|may|june|july|august|september|october|november|december)',
        '', canonical, flags=re.IGNORECASE
    )

    # Remove month abbreviations
    canonical = re.sub(
        r'_(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',
        '', canonical, flags=re.IGNORECASE
    )

    # Remove quarter patterns (q1, q2, q3, q4)
    canonical = re.sub(r'_?q[1-4]', '', canonical, flags=re.IGNORECASE)

    # Remove standalone 2-digit numbers that might be year shorts (25, 24, etc.)
    canonical = re.sub(r'_\d{2}(?=_|$)', '', canonical)

    # Remove standalone month numbers (01-12)
    canonical = re.sub(r'_0?[1-9](?=_|$)', '', canonical)
    canonical = re.sub(r'_1[0-2](?=_|$)', '', canonical)

    # Clean up multiple underscores and trailing/leading underscores
    canonical = re.sub(r'_+', '_', canonical)
    canonical = canonical.strip('_')

    return canonical


def canonicalize_source(source: Dict) -> Dict:
    """Canonicalize a single source by removing date patterns from code and table.

    Args:
        source: Source dict with 'code' and 'table' fields

    Returns:
        Modified source dict with canonical code and table name
    """
    if 'code' not in source:
        return source

    original_code = source['code']
    canonical_code = remove_date_patterns(original_code)

    # Only update if canonicalization changed the code
    if canonical_code != original_code:
        source['_original_code'] = original_code  # Preserve for audit
        source['code'] = canonical_code

        # Update table name to match canonical code
        if 'table' in source:
            # Extract prefix (e.g., "tbl_") and rebuild table name
            table = source['table']
            if table.startswith('tbl_'):
                source['table'] = f"tbl_{canonical_code}"
            else:
                # Handle other prefixes or no prefix
                source['table'] = canonical_code

    return source


def canonicalize_manifest(manifest: Dict) -> Dict:
    """Canonicalize all sources in a manifest.

    Args:
        manifest: Manifest dict with 'sources' array

    Returns:
        Modified manifest with canonical source codes
    """
    if 'sources' not in manifest:
        return manifest

    manifest['sources'] = [
        canonicalize_source(source)
        for source in manifest['sources']
    ]

    return manifest
