#!/usr/bin/env python3
"""
Add Publication CLI - Compact Version

Automatically classifies NHS URLs and generates YAML configuration.

Usage:
    python scripts/add_publication.py <url> [--config path] [--dry-run]
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
import yaml


# Configuration patterns
PATTERNS = {
    'month_names': {
        'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
        'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
    },
    'url_extraction': [
        # (regex pattern, landing_group, year_group, month_group, pattern_template)
        (r'(.+)/for-(\w+)-(\d{4})', 1, 3, 2, '{landing_page}/for-{month_name}-{year}'),
        (r'(.+)/performance-(\w+)-(\d{4})', 1, 3, 2, '{landing_page}/performance-{month_name}-{year}'),
        (r'(.+)/england-(\w+)-(\d{4})', 1, 3, 2, '{landing_page}/england-{month_name}-{year}'),
        (r'(.+)/(\w+)-(\d{4})', 1, 3, 2, '{landing_page}/{month_name}-{year}'),
        (r'(.+)/(\d{4})-(\d{2})', 1, 2, 3, '{landing_page}/{year}-{month:02d}'),
    ],
    'expansions': {
        'mi': 'Management Information', 'gp': 'GP', 'nhs': 'NHS',
        'adhd': 'ADHD', 'ae': 'A&E', 'rtt': 'RTT'
    }
}


def classify_url(url: str) -> dict:
    """Classify NHS URL and extract all metadata."""
    parsed = urlparse(url)
    url_lower = url.lower()

    # Detect source
    source = 'nhs_digital' if 'digital.nhs.uk' in parsed.netloc else \
             'nhs_england' if 'england.nhs.uk' in parsed.netloc else 'unknown'

    # Check if this is a landing page (no file extension)
    is_landing_page = not any(url_lower.endswith(ext) for ext in ['.xlsx', '.xls', '.zip', '.csv', '.pdf', '.ods'])

    # Extract period, landing page, and pattern in one pass
    period_info = None
    landing_page = None
    url_pattern = None

    for regex, land_grp, year_grp, month_grp, template in PATTERNS['url_extraction']:
        match = re.search(regex, url_lower, re.IGNORECASE)
        if match:
            landing_page = url[:match.start(land_grp)] + match.group(land_grp)
            year_str = match.group(year_grp)
            month_val = match.group(month_grp)

            # Parse month
            if month_val.isdigit():
                month = int(month_val)
            else:
                month = PATTERNS['month_names'].get(month_val.lower())

            if month and 1 <= month <= 12:
                year = int(year_str)
                if 2020 <= year <= 2030:
                    period_info = (year, month)
                    url_pattern = template
                    break

    # Fallback landing page extraction
    if not landing_page:
        if is_landing_page:
            # User provided landing page directly
            landing_page = url.rstrip('/')
        elif source == 'nhs_england' and '/statistical-work-areas/' in parsed.path:
            match = re.search(r'(/statistics/statistical-work-areas/[^/]+/?)', parsed.path)
            landing_page = f"{parsed.scheme}://{parsed.netloc}{match.group(1)}" if match else \
                          f"{parsed.scheme}://{parsed.netloc}/statistics/"
        else:
            landing_page = url.rsplit('/', 1)[0]

    # Detect hash codes (5+ char alphanumeric with mixed case or numbers)
    has_hash = bool(re.search(r'[a-zA-Z0-9]{5,}', parsed.path) and
                    re.search(r'\d.*[A-Z]|[A-Z].*\d', parsed.path))

    # EDGE CASE DETECTION: NHS Digital pages that redirect to NHS England
    # Check if actual data files are hosted on england.nhs.uk even though landing page is digital.nhs.uk
    redirects_to_england = False
    if source == 'nhs_digital' and is_landing_page:
        try:
            import requests
            from bs4 import BeautifulSoup
            
            # Fetch the landing page
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # First check if landing page itself has england.nhs.uk data file links
                england_links = soup.find_all('a', href=re.compile(r'england\.nhs\.uk'))
                data_extensions = ['.xlsx', '.xls', '.csv', '.zip']
                for link in england_links:
                    href = link.get('href', '')
                    if any(ext in href.lower() for ext in data_extensions):
                        redirects_to_england = True
                        break
                
                # If not found on landing page, check one level deeper (latest publication sub-page)
                if not redirects_to_england:
                    # Look for links to sub-pages (e.g., "/november-2025")
                    subpage_links = soup.find_all('a', href=re.compile(rf'{re.escape(landing_page)}/'))
                    if subpage_links:
                        # Check the first sub-page (usually latest month)
                        subpage_url = subpage_links[0].get('href')
                        if subpage_url and subpage_url.startswith('http'):
                            try:
                                subpage_response = requests.get(subpage_url, timeout=10)
                                if subpage_response.status_code == 200:
                                    subpage_soup = BeautifulSoup(subpage_response.content, 'html.parser')
                                    subpage_england_links = subpage_soup.find_all('a', href=re.compile(r'england\.nhs\.uk'))
                                    for link in subpage_england_links:
                                        href = link.get('href', '')
                                        if any(ext in href.lower() for ext in data_extensions):
                                            redirects_to_england = True
                                            break
                            except:
                                pass  # Subpage check failed, continue
        except Exception as e:
            # If validation fails, proceed with default classification
            # (Better to have false negative than break the script)
            pass

    # Generate publication code
    path_parts = [p for p in urlparse(landing_page).path.split('/') if p]
    if source == 'nhs_england' and 'statistical-work-areas' in path_parts:
        idx = path_parts.index('statistical-work-areas')
        code = path_parts[idx + 1] if idx + 1 < len(path_parts) else 'new_pub'
    else:
        code = path_parts[-1] if path_parts else 'new_pub'

    # Clean up code
    code = re.sub(r'^(mi-|statistical-|rtt-data-)', '', code).replace('-', '_')

    # Generate name
    name = code.replace('_', ' ').title()
    for abbr, full in PATTERNS['expansions'].items():
        name = re.sub(rf'\b{abbr}\b', full, name, flags=re.IGNORECASE)

    # Determine mode with edge case handling
    if is_landing_page and (source == 'nhs_england' or redirects_to_england):
        # Landing page for NHS England OR NHS Digital that redirects to NHS England → use discover mode
        periods_mode = 'schedule'
        url_mode = 'discover'
        if redirects_to_england:
            # Override detected source for clarity
            source = 'nhs_digital_redirect_england'
    elif has_hash:
        # Hash detected → explicit mode
        periods_mode = 'manual'
        url_mode = 'explicit'
    else:
        # NHS Digital → template mode
        periods_mode = 'schedule'
        url_mode = 'template'

    return {
        'source': source,
        'has_hash': has_hash,
        'is_landing_page': is_landing_page,
        'landing_page': landing_page,
        'period': period_info,
        'url_pattern': url_pattern or '{landing_page}/{period}',
        'frequency': 'quarterly' if re.search(r'\bq[1-4]\b|quarter|fy\d{2}', url_lower) else 'monthly',
        'periods_mode': periods_mode,
        'url_mode': url_mode,
        'code': code,
        'name': name,
        'url': url,
        'redirects_to_england': redirects_to_england,
    }


def detect_file_pattern_and_dates(landing_page: str) -> tuple:
    """Detect common file pattern and available date range from landing page.

    Returns:
        (file_pattern, earliest_period, latest_period)
    """
    try:
        import sys
        from pathlib import Path
        # Add project root to path
        project_root = Path(__file__).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from src.datawarp.discovery.html_parser import extract_nhs_england_links
        import re
        from collections import Counter

        # Get all links
        links = list(extract_nhs_england_links(landing_page))

        if not links:
            return ('data-file', None, None)

        # Extract filenames and look for patterns
        filenames = [link.split('/')[-1] for link in links if any(ext in link for ext in ['.xlsx', '.xls', '.csv'])]

        if not filenames:
            return ('data-file', None, None)

        # Find common prefix (file pattern)
        # Look for consistent prefixes before month names or dates
        prefixes = Counter()
        month_patterns = r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february|march|april|june|july|august|september|october|november|december|q[1-4]|\d{4})'

        for filename in filenames:
            # Find prefix before date/month components
            match = re.match(rf'^([A-Za-z\-_]+?)[-_\s]*{month_patterns}', filename, re.IGNORECASE)
            if match:
                prefix = match.group(1).rstrip('-_')
                prefixes[prefix] += 1

        # Use most common prefix as file_pattern
        if prefixes:
            file_pattern = prefixes.most_common(1)[0][0]
        else:
            file_pattern = 'data-file'

        # Extract periods from filenames
        periods = []
        month_map = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
            'january': 1, 'february': 2, 'march': 3, 'april': 4, 'june': 6,
            'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
        }

        for filename in filenames:
            # Try to match month-year patterns
            for month_name, month_num in month_map.items():
                pattern = rf'{month_name}[_\-\s]*(\d{{4}}|\d{{2}})'
                match = re.search(pattern, filename, re.IGNORECASE)
                if match:
                    year_str = match.group(1)
                    year = int(year_str) if len(year_str) == 4 else 2000 + int(year_str)
                    if 2010 <= year <= 2030:  # Sanity check
                        periods.append(f"{year}-{month_num:02d}")
                    break

        if periods:
            periods_sorted = sorted(set(periods))
            earliest = periods_sorted[0]
            latest = periods_sorted[-1]
            return (file_pattern, earliest, latest)

        return (file_pattern, None, None)

    except Exception as e:
        # Silently fall back to defaults if detection fails
        return ('data-file', None, None)


def generate_config(cls: dict) -> dict:
    """Generate YAML config structure from classification."""
    config = {
        'name': cls['name'],
        'frequency': cls['frequency'],
        'landing_page': cls['landing_page'],
        'reference_manifest': None,
    }

    if cls['periods_mode'] == 'schedule':
        # For discover mode, detect file pattern and date range from landing page
        if cls['url_mode'] == 'discover':
            file_pattern, earliest_period, latest_period = detect_file_pattern_and_dates(cls['landing_page'])

            # Use detected earliest period or fall back to default
            if earliest_period:
                start = earliest_period
            elif cls['period']:
                start = f"{cls['period'][0]}-{cls['period'][1]:02d}"
            else:
                start = f"{date.today().year}-01"

            # Add info comment if we detected data
            if earliest_period and latest_period:
                config['_detected_range'] = f"Detected data from {earliest_period} to {latest_period}"
        else:
            # Template mode - use URL period or default
            start = f"{cls['period'][0]}-{cls['period'][1]:02d}" if cls['period'] else f"{date.today().year}-01"
            file_pattern = None

        # Schedule mode
        config['periods'] = {
            'mode': 'schedule',
            'start': start,
            'end': 'current',
            'publication_lag_weeks': 6,
        }

        # Add months filter for quarterly
        if cls['frequency'] == 'quarterly' and cls['period']:
            _, month = cls['period']
            # Detect common quarterly patterns
            if month in [2, 5, 8, 11]:
                config['periods']['months'] = [2, 5, 8, 11]
            elif month in [3, 6, 9, 12]:
                config['periods']['months'] = [3, 6, 9, 12]
            else:
                config['periods']['months'] = [month]

        if cls['url_mode'] == 'discover':
            config['url'] = {
                'mode': 'discover',
                'file_pattern': file_pattern,
            }
        else:
            config['url'] = {
                'mode': 'template',
                'pattern': cls['url_pattern'],
            }
    else:
        # Manual/explicit mode
        config['periods'] = {'mode': 'manual'}
        config['url'] = {'mode': 'explicit'}
        period_str = f"{cls['period'][0]}-{cls['period'][1]:02d}" if cls['period'] else "YYYY-MM"
        config['urls'] = [{
            'period': period_str,
            'url': cls['url'],
        }]

    # Store metadata for TODO comments (handled in formatting)
    config['_todos'] = {}
    if cls['periods_mode'] == 'schedule':
        config['_todos']['publication_lag_weeks'] = 'TODO: Verify actual lag'
        if cls['frequency'] == 'quarterly' and cls['period']:
            _, month = cls['period']
            if month not in [2, 5, 8, 11, 3, 6, 9, 12]:
                config['_todos']['months'] = 'TODO: Add other quarterly months'
    else:
        if not cls['period']:
            config['_todos']['period'] = 'TODO: Add period'

    return {cls['code']: config}


def display_classification(cls: dict, config: dict = None):
    """Display classification results."""
    print(f"Analyzing URL: {cls['url']}\n")
    print("📊 Classification:")
    print(f"  Source:       {cls['source']}")
    if cls.get('redirects_to_england'):
        print(f"  ⚠️  EDGE CASE:   NHS Digital page redirects to NHS England data!")
        print(f"                Data files hosted on england.nhs.uk (not digital.nhs.uk)")
    print(f"  Has hash:     {cls['has_hash']}")
    print(f"  Templatable:  {cls['url_mode'] == 'template'}")
    print(f"  Frequency:    {cls['frequency']}")
    if cls['period']:
        print(f"  Detected period: {cls['period'][0]}-{cls['period'][1]:02d}")
    print(f"  Landing page: {cls['landing_page']}")

    # Show detected info if available
    if config and '_detected_range' in config.get(cls['code'], {}):
        print(f"  ℹ️  {config[cls['code']]['_detected_range']}")
    if cls['url_mode'] == 'template':
        print(f"  URL pattern:  {cls['url_pattern']}")
    elif cls['url_mode'] == 'discover':
        print(f"  ℹ️  Will use runtime URL discovery (hash-coded filenames)")
    print()


def main():
    parser = argparse.ArgumentParser(description='Add NHS publication to DataWarp')
    parser.add_argument('url', help='NHS publication URL')
    parser.add_argument('--config', default='config/publications_v2.yaml',
                       help='Config file path')
    parser.add_argument('--dry-run', action='store_true', help='Preview without appending')
    args = parser.parse_args()

    # Classify and generate
    cls = classify_url(args.url)
    config = generate_config(cls)

    # Display
    display_classification(cls, config)
    print("\n📝 Generated YAML:\n")

    # Extract internal metadata (don't show in YAML)
    pub_code = list(config.keys())[0]
    todos = config[pub_code].pop('_todos', {})
    config[pub_code].pop('_detected_range', None)  # Remove from YAML output

    # Format YAML with proper indentation (selective quoting)
    yaml_str = yaml.dump(config, default_flow_style=False, sort_keys=False, allow_unicode=True)
    # Clean up YAML output: remove null quotes, fix indentation
    yaml_str = yaml_str.replace("'null'", "null").replace('"null"', 'null')
    yaml_str = yaml_str.replace('!!null', '')

    # Add TODO comments as YAML comments
    lines = yaml_str.split('\n')
    for i, line in enumerate(lines):
        for key, todo_msg in todos.items():
            if f'{key}:' in line:
                lines[i] = line + f'  # {todo_msg}'

    # Add 2-space indent to all lines
    yaml_output = '\n'.join('  ' + line if line.strip() else '' for line in '\n'.join(lines).rstrip().split('\n'))
    print(yaml_output)
    print()

    if args.dry_run:
        print("🔍 Dry run - not appending to config file")
        return

    # Append to file
    response = input(f"\nAppend to {args.config}? [y/n]: ").strip().lower()
    if response == 'y':
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"Error: {config_path} not found")
            sys.exit(1)

        content = config_path.read_text()
        if not content.endswith('\n\n'):
            content += '\n\n' if content.endswith('\n') else '\n\n'

        content += yaml_output + '\n'
        config_path.write_text(content)

        print(f"\n✅ Added to {config_path}")
        print("\n✨ Next steps:")
        print(f"   1. Review config in {args.config}")
        print(f"   2. Adjust publication_lag_weeks if needed")
        if cls['frequency'] == 'quarterly':
            print(f"   3. Verify quarterly months are correct")
        print(f"   {'4' if cls['frequency'] == 'quarterly' else '3'}. Run: python scripts/backfill.py --pub {cls['code']}")
    else:
        print("❌ Cancelled")


if __name__ == '__main__':
    main()
