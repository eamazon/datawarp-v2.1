#!/usr/bin/env python3
"""
Batch generate publications.yaml from NHS landing pages.
Handles different page structures (NHS England yearly, NHS Digital monthly).
"""

import json, os, re, sys, time, warnings
warnings.filterwarnings('ignore')

from urllib.parse import urljoin, urlparse
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
load_dotenv()

MONTHS = {'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,
          'july':7,'august':8,'september':9,'october':10,'november':11,'december':12}
MSHORT = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']

# Sources to skip (login required or special handling needed)
SKIP_SOURCES = ['IPS', 'MH Core Data Pack', 'Operational Planning', 'Oversight Framework']

def fetch_page(url):
    """Fetch page and return soup + basic info."""
    try:
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        soup = BeautifulSoup(resp.content, 'html.parser')
        h1 = soup.find('h1')
        title = h1.get_text(strip=True) if h1 else soup.find('title').get_text(strip=True) if soup.find('title') else ''
        return soup, title
    except Exception as e:
        print(f"      ❌ Failed to fetch: {e}")
        return None, None

def find_links(soup, base_url):
    """Find all links on page, categorized."""
    files, sub_pages = [], []
    base_path = urlparse(base_url).path.rstrip('/')

    for a in soup.find_all('a', href=True):
        href = urljoin(base_url, a['href'])
        path = urlparse(href).path.lower()
        text = a.get_text(strip=True).lower()

        # File links
        if path.endswith(('.xlsx', '.xls', '.csv', '.zip', '.ods')):
            files.append({'url': href, 'text': path.split('/')[-1]})
        # Sub-page links (child of current page)
        elif urlparse(href).netloc == urlparse(base_url).netloc:
            if urlparse(href).path.startswith(base_path + '/') and urlparse(href).path != base_path + '/':
                sub_pages.append({'url': href, 'text': urlparse(href).path.split('/')[-1] or text})

    return files, sub_pages

# Use centralized period parsing from utility module
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from datawarp.utils.period import parse_period

def analyze_page_structure(url):
    """
    Analyze a landing page and extract all periods with URLs.
    Handles multi-level navigation automatically.
    """
    print(f"   📄 Fetching: {url[:70]}...")
    soup, title = fetch_page(url)
    if not soup:
        return None, []

    files, sub_pages = find_links(soup, url)
    periods = []

    # Check if files have period info directly
    file_periods = []
    for f in files:
        period, sort = parse_period(f['text'])
        if period:
            file_periods.append({'period': period, 'url': f['url'], 'sort': sort, 'text': f['text']})

    # Check sub-pages for period info
    sub_periods = []
    for sp in sub_pages:
        period, sort = parse_period(sp['text'])
        if period:
            sub_periods.append({'period': period, 'url': sp['url'], 'sort': sort, 'text': sp['text']})

    # Determine structure type and collect periods
    if file_periods and len(file_periods) >= len(sub_periods):
        # Files directly on landing page
        print(f"      → Direct files: {len(file_periods)} periods found")
        periods = file_periods
    elif sub_periods:
        # Need to navigate sub-pages
        print(f"      → Sub-pages: {len(sub_pages)} found, checking top 3...")

        # Check if sub-pages are yearly (NHS England) or monthly (NHS Digital)
        yearly_pattern = any('data-20' in sp['text'] or re.search(r'\d{4}-\d{2}$', sp['text']) for sp in sub_pages[:5])

        if yearly_pattern:
            # NHS England yearly structure - get latest year page
            latest_year_pages = sorted(sub_pages, key=lambda x: x['text'], reverse=True)[:2]
            for yp in latest_year_pages:
                print(f"      → Fetching year page: {yp['text']}")
                sub_soup, _ = fetch_page(yp['url'])
                if sub_soup:
                    sub_files, _ = find_links(sub_soup, yp['url'])
                    for f in sub_files:
                        period, sort = parse_period(f['text'])
                        if period:
                            periods.append({'period': period, 'url': f['url'], 'sort': sort, 'text': f['text']})
        else:
            # Monthly sub-pages - these ARE the period pages
            print(f"      → Monthly pages: {len(sub_periods)} periods")
            periods = sub_periods

    # Deduplicate and sort
    seen = set()
    unique_periods = []
    for p in sorted(periods, key=lambda x: x['sort'], reverse=True):
        if p['period'] not in seen:
            seen.add(p['period'])
            unique_periods.append(p)

    return title, sorted(unique_periods, key=lambda x: x['sort'])

def llm_analyze(title, url, periods):
    """Use LLM to generate code and determine frequency."""
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel(os.getenv('LLM_MODEL', 'gemini-2.0-flash-exp'),
        generation_config={"temperature": 0.1})

    sample = [p['period'] for p in periods[:10]]
    prompt = f"""NHS publication config. Generate code and frequency.

Title: {title}
URL: {url}
Periods found: {len(periods)} - {sample}

Return JSON: {{"code":"short_snake_case_max20","name":"Clean Title","frequency":"monthly|quarterly|annual"}}
code should be SHORT (e.g., "ae_attendances", "ambulance_qi", "cancer_wait").
JSON only."""

    try:
        resp = model.generate_content(prompt)
        r = json.loads(re.sub(r'^```json\s*|\s*```$', '', resp.text.strip()))
        return r
    except:
        # Fallback
        code = re.sub(r'[^a-z0-9]+', '_', url.split('/')[-1].lower())[:20]
        return {'code': code, 'name': title[:50], 'frequency': 'monthly'}

def process_source(name, source, url):
    """Process a single source and return YAML config."""
    print(f"\n{'='*60}")
    print(f"📊 {name} ({source})")
    print(f"   {url}")

    title, periods = analyze_page_structure(url)

    if not periods:
        print(f"   ⚠️  No periods found - may need manual review")
        return None

    # Filter to recent periods (last 2 fiscal years)
    recent_periods = [p for p in periods if p['sort'] >= 202400]  # From 2024 onwards
    if not recent_periods:
        recent_periods = periods[-12:]  # Last 12 if nothing recent

    print(f"   ✅ Found {len(periods)} total, using {len(recent_periods)} recent periods")

    # Get LLM config
    config = llm_analyze(title, url, recent_periods)
    print(f"   🤖 Code: {config['code']} | Frequency: {config['frequency']}")

    # Build YAML structure
    yaml_config = {
        'code': config['code'],
        'name': config['name'],
        'frequency': config['frequency'],
        'landing_page': url,
        'periods': recent_periods
    }

    return yaml_config

def generate_yaml(configs):
    """Generate the full publications2.yaml content."""
    yaml = """# DataWarp Publication Registry v2
#
# Auto-generated by batch_generate_publications.py
# Generated: {timestamp}
#
# Sources: {count} NHS publications
#

publications:
"""

    for cfg in configs:
        if not cfg:
            continue

        yaml += f"""
  # {'='*70}
  # {cfg['name'][:60]}
  # {'='*70}
  {cfg['code']}:
    name: "{cfg['name']}"
    frequency: {cfg['frequency']}
    landing_page: {cfg['landing_page']}
    reference_manifest: null
    urls:
"""
        for p in cfg['periods']:
            yaml += f"      - period: {p['period']}\n"
            yaml += f"        url: {p['url']}\n"

    return yaml.format(timestamp=time.strftime('%Y-%m-%d %H:%M UTC'), count=len([c for c in configs if c]))

def parse_landing_pages_md(filepath):
    """Parse the nhs_landing_pages.md table."""
    sources = []
    with open(filepath) as f:
        for line in f:
            # Parse markdown table rows
            if line.startswith('|') and '](http' in line:
                parts = line.split('|')
                if len(parts) >= 4:
                    name = parts[1].strip().replace('**', '')
                    source = parts[2].strip()
                    # Extract URL from markdown link
                    url_match = re.search(r'\((https?://[^)]+)\)', parts[3])
                    if url_match:
                        url = url_match.group(1)
                        sources.append({'name': name, 'source': source, 'url': url})
    return sources

def main():
    md_path = 'config/nhs_landing_pages.md'
    if not os.path.exists(md_path):
        print(f"❌ File not found: {md_path}")
        sys.exit(1)

    sources = parse_landing_pages_md(md_path)
    print(f"📋 Found {len(sources)} sources in {md_path}")

    # Filter out skip sources
    processable = [s for s in sources if s['name'] not in SKIP_SOURCES and 'Login Required' not in s.get('notes', '')]
    skipped = [s for s in sources if s['name'] in SKIP_SOURCES or 'future.nhs.uk' in s['url']]

    print(f"   ✅ Processable: {len(processable)}")
    print(f"   ⏭️  Skipping: {[s['name'] for s in skipped]}")

    # Process each source
    configs = []
    for i, src in enumerate(processable):
        if 'future.nhs.uk' in src['url']:
            print(f"\n⏭️  Skipping {src['name']} (login required)")
            continue

        print(f"\n[{i+1}/{len(processable)}]", end="")
        cfg = process_source(src['name'], src['source'], src['url'])
        configs.append(cfg)

        # Rate limiting
        time.sleep(1)

    # Generate YAML
    yaml_content = generate_yaml(configs)

    output_path = 'config/publications2.yaml'
    with open(output_path, 'w') as f:
        f.write(yaml_content)

    print(f"\n{'='*60}")
    print(f"✅ Generated: {output_path}")
    print(f"   Sources: {len([c for c in configs if c])}")
    print(f"   Total periods: {sum(len(c['periods']) for c in configs if c)}")

if __name__ == "__main__":
    main()
