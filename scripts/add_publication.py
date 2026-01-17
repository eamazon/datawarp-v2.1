#!/usr/bin/env python3
"""
Add Publication CLI

Automatically classifies NHS URLs and generates YAML configuration for publications_v2.yaml.

Usage:
    python scripts/add_publication.py <url> [--config path/to/config.yaml] [--dry-run]

Examples:
    # Detect pattern and generate config
    python scripts/add_publication.py https://digital.nhs.uk/.../adhd/august-2025

    # Dry run (don't append to file)
    python scripts/add_publication.py https://digital.nhs.uk/.../adhd/august-2025 --dry-run
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

# Month name mapping
MONTH_NAMES = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12
}

MONTH_ABBREV = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}


def detect_hash_code(url: str) -> bool:
    """Detect if URL contains unpredictable hash codes (5+ char random strings)."""
    # NHS England URLs often have patterns like: .../provider-xY3kL-revised.xls
    # Look for 5+ alphanumeric strings that look random (mix of upper/lower)
    path = urlparse(url).path

    # Pattern: alphanumeric string with mix of upper/lower case
    hash_pattern = re.compile(r'[a-zA-Z0-9]{5,}')

    for match in hash_pattern.finditer(path):
        token = match.group()
        # Check if it's not a common word (has mixed case or numbers)
        if re.search(r'\d', token) or (re.search(r'[a-z]', token) and re.search(r'[A-Z]', token)):
            # Exclude common patterns like dates, months, quarters
            if not re.match(r'^\d{4}$', token):  # Not a year
                if not re.match(r'^\d{6,8}$', token):  # Not a date
                    if token.lower() not in MONTH_NAMES:  # Not a month
                        return True

    return False


def extract_period_from_url(url: str) -> Optional[Tuple[int, int]]:
    """Extract (year, month) from URL if present."""
    url_lower = url.lower()

    # Look for month name + year patterns
    for month_name, month_num in MONTH_NAMES.items():
        # Pattern: month-year or month_year
        pattern = rf'{month_name}[-_](\d{{4}})'
        match = re.search(pattern, url_lower)
        if match:
            return int(match.group(1)), month_num

    # Look for year-month patterns (2025-08)
    pattern = r'(\d{4})[-_](\d{2})'
    match = re.search(pattern, url)
    if match:
        year, month = int(match.group(1)), int(match.group(2))
        if 1 <= month <= 12 and 2020 <= year <= 2030:
            return year, month

    # Look for performance-month-year patterns
    for month_name, month_num in MONTH_NAMES.items():
        pattern = rf'performance[-_]{month_name}[-_](\d{{4}})'
        match = re.search(pattern, url_lower)
        if match:
            return int(match.group(1)), month_num

    return None


def extract_landing_page(url: str, period_info: Optional[Tuple[int, int]]) -> str:
    """Extract landing page by removing period-specific part."""
    parsed = urlparse(url)

    # For NHS England, landing page is typically the statistical-work-areas page
    # not the wp-content path
    if 'england.nhs.uk' in parsed.netloc:
        # For NHS England, use a heuristic - landing page is typically at:
        # /statistics/statistical-work-areas/<topic>/
        if '/statistical-work-areas/' in parsed.path:
            # Extract up to and including the topic
            match = re.search(r'(/statistics/statistical-work-areas/[^/]+/?)', parsed.path)
            if match:
                return f"{parsed.scheme}://{parsed.netloc}{match.group(1)}"
        # Fallback: use base statistics path
        return f"{parsed.scheme}://{parsed.netloc}/statistics/"

    if not period_info:
        # No period detected, use parent path
        path_parts = parsed.path.rstrip('/').split('/')
        if len(path_parts) > 1:
            landing_path = '/'.join(path_parts[:-1])
            return f"{parsed.scheme}://{parsed.netloc}{landing_path}"
        return f"{parsed.scheme}://{parsed.netloc}"

    year, month = period_info
    month_name = [k for k, v in MONTH_NAMES.items() if v == month][0]

    # Remove month-year pattern
    url_lower = url.lower()

    # Try various patterns (look for performance-, england-, etc. prefixes)
    patterns = [
        rf'performance[-_]{month_name}[-_]{year}',
        rf'england[-_]{month_name}[-_]{year}',
        rf'{month_name}[-_]{year}',
        rf'{year}[-_]{month:02d}',
    ]

    for pattern in patterns:
        match = re.search(pattern, url_lower)
        if match:
            # Remove everything from the pattern onwards
            return url[:match.start()].rstrip('/-')

    # Fallback: remove last path component
    return url.rsplit('/', 1)[0]


def extract_url_pattern(url: str, landing_page: str, period_info: Optional[Tuple[int, int]]) -> str:
    """Extract URL pattern with placeholders."""
    if not period_info:
        return "{landing_page}/{period}"

    year, month = period_info
    month_name = [k for k, v in MONTH_NAMES.items() if v == month][0]

    # Get the part after landing page
    suffix = url[len(landing_page):].lstrip('/')

    # Replace actual values with placeholders
    pattern = suffix
    pattern = re.sub(rf'\b{year}\b', '{year}', pattern)
    pattern = re.sub(rf'\b{month_name}\b', '{month_name}', pattern, flags=re.IGNORECASE)
    pattern = re.sub(rf'\b{month:02d}\b', '{month:02d}', pattern)

    # Check for 'performance-' prefix
    if pattern.startswith('performance-'):
        pass  # Keep as is

    # Check for 'england-' prefix
    if pattern.startswith('england-'):
        pass  # Keep as is

    return f"{{landing_page}}/{pattern}"


def detect_frequency(url: str, period_info: Optional[Tuple[int, int]]) -> str:
    """Detect publication frequency from URL."""
    url_lower = url.lower()

    # Look for quarterly indicators
    if re.search(r'\bq[1-4]\b', url_lower) or re.search(r'quarter', url_lower):
        return 'quarterly'

    # Look for fiscal year indicators
    if re.search(r'\bfy\d{2}\b', url_lower):
        return 'quarterly'

    # Default to monthly if month detected
    if period_info:
        return 'monthly'

    return 'monthly'


def generate_publication_code(landing_page: str, url: str) -> str:
    """Generate publication code from landing page URL."""
    parsed = urlparse(landing_page)
    path_parts = [p for p in parsed.path.split('/') if p]

    if not path_parts:
        return 'new_publication'

    # For NHS England, use topic from statistical-work-areas
    if 'england.nhs.uk' in parsed.netloc:
        for i, part in enumerate(path_parts):
            if part == 'statistical-work-areas' and i + 1 < len(path_parts):
                code = path_parts[i + 1]
                # Clean up
                code = code.replace('-and-', '_')
                code = code.replace('-', '_')
                return code

    # Take last part, clean it up
    code = path_parts[-1]

    # Remove common prefixes
    code = re.sub(r'^(mi-|statistical-)', '', code)

    # Replace hyphens with underscores
    code = code.replace('-', '_')

    # If code is too generic (like 'performance'), try second-to-last part
    generic_codes = ['performance', 'data', 'statistics', 'publications', 'statistical']
    if code in generic_codes and len(path_parts) > 1:
        code = path_parts[-2]
        code = re.sub(r'^(mi-|statistical-)', '', code)
        code = code.replace('-', '_')

    return code


def generate_publication_name(code: str, url: str) -> str:
    """Generate human-readable publication name from code."""
    # Convert code to title case
    name = code.replace('_', ' ').title()

    # Expand common abbreviations
    expansions = {
        'Mi': 'Management Information',
        'Gp': 'GP',
        'Nhs': 'NHS',
        'Adhd': 'ADHD',
        'Ae': 'A&E',
        'Rtt': 'RTT',
    }

    for abbrev, expansion in expansions.items():
        name = name.replace(abbrev, expansion)

    return name


def classify_url(url: str) -> Dict:
    """Classify NHS URL and extract metadata.

    Returns:
        {
            'source': 'nhs_digital' | 'nhs_england' | 'unknown',
            'has_hash': bool,
            'landing_page': str,
            'period': (year, month) or None,
            'frequency': 'monthly' | 'quarterly',
            'url_pattern': str,
            'periods_mode': 'schedule' | 'manual',
            'url_mode': 'template' | 'explicit',
            'publication_code': str,
            'publication_name': str,
        }
    """
    parsed = urlparse(url)

    # Detect source
    if 'digital.nhs.uk' in parsed.netloc:
        source = 'nhs_digital'
    elif 'england.nhs.uk' in parsed.netloc:
        source = 'nhs_england'
    else:
        source = 'unknown'

    # Detect hash codes
    has_hash = detect_hash_code(url)

    # Extract period
    period_info = extract_period_from_url(url)

    # Extract landing page
    landing_page = extract_landing_page(url, period_info)

    # Detect frequency
    frequency = detect_frequency(url, period_info)

    # Extract URL pattern
    url_pattern = extract_url_pattern(url, landing_page, period_info)

    # Determine modes
    if has_hash:
        periods_mode = 'manual'
        url_mode = 'explicit'
    else:
        periods_mode = 'schedule'
        url_mode = 'template'

    # Generate publication code and name
    pub_code = generate_publication_code(landing_page, url)
    pub_name = generate_publication_name(pub_code, url)

    return {
        'source': source,
        'has_hash': has_hash,
        'landing_page': landing_page,
        'period': period_info,
        'frequency': frequency,
        'url_pattern': url_pattern,
        'periods_mode': periods_mode,
        'url_mode': url_mode,
        'publication_code': pub_code,
        'publication_name': pub_name,
        'original_url': url,
    }


def generate_yaml_config(classification: Dict) -> str:
    """Generate YAML configuration from classification."""
    pub_code = classification['publication_code']
    pub_name = classification['publication_name']
    landing_page = classification['landing_page']
    frequency = classification['frequency']
    periods_mode = classification['periods_mode']
    url_mode = classification['url_mode']
    url_pattern = classification['url_pattern']
    period_info = classification['period']

    yaml_lines = [
        f"  {pub_code}:",
        f'    name: "{pub_name}"',
        f'    frequency: {frequency}',
        f'    landing_page: {landing_page}',
        f'    reference_manifest: null',
    ]

    if periods_mode == 'schedule':
        # Schedule mode config
        yaml_lines.append('')
        yaml_lines.append('    periods:')
        yaml_lines.append('      mode: schedule')

        # Use detected period as start, or default to current year
        if period_info:
            year, month = period_info
            start_period = f"{year}-{month:02d}"
        else:
            today = date.today()
            start_period = f"{today.year}-01"

        yaml_lines.append(f'      start: "{start_period}"')
        yaml_lines.append('      end: current')

        # Add months filter for quarterly
        if frequency == 'quarterly':
            # Guess quarterly months (user may need to adjust)
            if period_info:
                _, month = period_info
                # Common quarterly patterns: Feb/May/Aug/Nov or Mar/Jun/Sep/Dec
                if month in [2, 5, 8, 11]:
                    yaml_lines.append('      months: [2, 5, 8, 11]')
                elif month in [3, 6, 9, 12]:
                    yaml_lines.append('      months: [3, 6, 9, 12]')
                else:
                    yaml_lines.append(f'      months: [{month}]  # TODO: Add other quarterly months')

        yaml_lines.append('      publication_lag_weeks: 6  # TODO: Verify actual lag')

        yaml_lines.append('')
        yaml_lines.append('    url:')
        yaml_lines.append('      mode: template')
        yaml_lines.append(f'      pattern: "{url_pattern}"')

    else:
        # Manual/explicit mode config
        yaml_lines.append('')
        yaml_lines.append('    periods:')
        yaml_lines.append('      mode: manual')
        yaml_lines.append('')
        yaml_lines.append('    url:')
        yaml_lines.append('      mode: explicit')
        yaml_lines.append('')
        yaml_lines.append('    urls:')

        if period_info:
            year, month = period_info
            period_str = f"{year}-{month:02d}"
            yaml_lines.append(f'      - period: "{period_str}"')
            yaml_lines.append(f'        url: {classification["original_url"]}')
        else:
            yaml_lines.append('      - period: "YYYY-MM"  # TODO: Add period')
            yaml_lines.append(f'        url: {classification["original_url"]}')

    return '\n'.join(yaml_lines)


def append_to_config_file(yaml_config: str, config_path: Path) -> bool:
    """Append YAML config to publications file."""
    try:
        # Read existing config
        if not config_path.exists():
            print(f"Error: Config file not found: {config_path}")
            return False

        content = config_path.read_text()

        # Append new config
        # Add spacing if file doesn't end with newline
        if not content.endswith('\n\n'):
            if content.endswith('\n'):
                content += '\n'
            else:
                content += '\n\n'

        content += yaml_config + '\n'

        # Write back
        config_path.write_text(content)
        print(f"✅ Added to {config_path}")
        return True

    except Exception as e:
        print(f"Error appending to config: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Add NHS publication to DataWarp configuration',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('url', help='NHS publication URL')
    parser.add_argument('--config', default='config/publications_v2.yaml',
                       help='Path to publications config (default: config/publications_v2.yaml)')
    parser.add_argument('--dry-run', action='store_true',
                       help="Show config without appending to file")

    args = parser.parse_args()

    # Classify URL
    print(f"Analyzing URL: {args.url}")
    print()

    classification = classify_url(args.url)

    # Display classification
    print("📊 Classification:")
    print(f"  Source:       {classification['source']}")
    print(f"  Has hash:     {classification['has_hash']}")
    print(f"  Templatable:  {classification['url_mode'] == 'template'}")
    print(f"  Frequency:    {classification['frequency']}")

    if classification['period']:
        year, month = classification['period']
        print(f"  Detected period: {year}-{month:02d}")

    print(f"  Landing page: {classification['landing_page']}")

    if classification['url_mode'] == 'template':
        print(f"  URL pattern:  {classification['url_pattern']}")

    print()

    # Generate YAML
    yaml_config = generate_yaml_config(classification)

    print("📝 Generated YAML:")
    print()
    print(yaml_config)
    print()

    # Append to file (if not dry-run)
    if args.dry_run:
        print("🔍 Dry run - not appending to config file")
        return

    # Ask for confirmation
    response = input(f"Append to {args.config}? [y/n]: ").strip().lower()

    if response == 'y':
        config_path = Path(args.config)
        success = append_to_config_file(yaml_config, config_path)

        if success:
            print()
            print("✨ Next steps:")
            print(f"   1. Review config in {args.config}")
            print(f"   2. Adjust publication_lag_weeks if needed")
            if classification['frequency'] == 'quarterly':
                print(f"   3. Verify quarterly months are correct")
            print(f"   4. Run: python scripts/backfill.py --pub {classification['publication_code']}")
    else:
        print("❌ Cancelled")


if __name__ == '__main__':
    main()
