#!/usr/bin/env python3
"""
Deep recursive explorer for NHS sources with nested structures.
Navigates like a human would - following sub-pages until files are found.
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

def fetch_page(url, timeout=30):
    """Fetch page and return soup."""
    try:
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=timeout)
        return BeautifulSoup(resp.content, 'html.parser')
    except Exception as e:
        print(f"      ❌ Failed: {e}")
        return None

def get_links(soup, base_url):
    """Extract all links from page, categorized."""
    if not soup:
        return [], []

    files, pages = [], []
    base_netloc = urlparse(base_url).netloc
    base_path = urlparse(base_url).path.rstrip('/')

    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.startswith('#') or href.startswith('mailto:') or href.startswith('javascript:'):
            continue

        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        # Skip external links
        if parsed.netloc != base_netloc:
            continue

        path_lower = parsed.path.lower()
        link_text = a.get_text(strip=True)

        # File links
        if path_lower.endswith(('.xlsx', '.xls', '.csv', '.zip', '.ods', '.pdf')):
            files.append({
                'url': full_url,
                'text': link_text or path_lower.split('/')[-1],
                'filename': path_lower.split('/')[-1]
            })
        # Sub-page links (children of current page)
        elif parsed.path.startswith(base_path + '/') and parsed.path != base_path + '/':
            # Avoid duplicates and self-references
            if parsed.path.rstrip('/') != base_path:
                pages.append({
                    'url': full_url.rstrip('/'),
                    'text': link_text,
                    'path': parsed.path
                })

    # Deduplicate
    seen_files = set()
    unique_files = []
    for f in files:
        if f['url'] not in seen_files:
            seen_files.add(f['url'])
            unique_files.append(f)

    seen_pages = set()
    unique_pages = []
    for p in pages:
        if p['url'] not in seen_pages:
            seen_pages.add(p['url'])
            unique_pages.append(p)

    return unique_files, unique_pages

# Use centralized period parsing from utility module
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from datawarp.utils.period import parse_period

def llm_analyze_page(url, title, sub_pages, files):
    """Use LLM to understand page structure and recommend what to explore."""
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel(os.getenv('LLM_MODEL', 'gemini-2.0-flash-exp'),
        generation_config={"temperature": 0.1})

    sub_page_list = [f"- {p['text'][:50]}: {p['path']}" for p in sub_pages[:15]]
    file_list = [f"- {f['text'][:50]}: {f['filename']}" for f in files[:10]]

    prompt = f"""Analyze this NHS statistics page structure.

URL: {url}
Title: {title}

SUB-PAGES FOUND ({len(sub_pages)}):
{chr(10).join(sub_page_list) if sub_page_list else '(none)'}

FILES FOUND ({len(files)}):
{chr(10).join(file_list) if file_list else '(none)'}

Determine:
1. Is this a DATA page (has downloadable files) or NAVIGATION page (links to sub-categories)?
2. If navigation, which sub-pages likely lead to actual data files?
3. Are there multiple data categories (e.g., "overnight beds" vs "day beds")?

Return JSON:
{{
  "page_type": "data|navigation|mixed",
  "has_useful_files": true/false,
  "explore_pages": ["url1", "url2"] (sub-pages to explore for data),
  "data_categories": ["category1", "category2"] or null,
  "notes": "Brief explanation"
}}
JSON only."""

    try:
        resp = model.generate_content(prompt)
        return json.loads(re.sub(r'^```json\s*|\s*```$', '', resp.text.strip()))
    except:
        return {"page_type": "unknown", "has_useful_files": len(files) > 0, "explore_pages": [], "notes": "LLM parse failed"}

def deep_explore(url, max_depth=4, visited=None):
    """
    Recursively explore a source to find all data files.
    Returns: list of {url, period, category, depth}
    """
    if visited is None:
        visited = set()

    if url in visited:
        return []
    visited.add(url)

    depth = len(visited)
    indent = "   " * min(depth, 4)

    print(f"{indent}📄 [{depth}] {url.split('/')[-1] or url.split('/')[-2]}")

    soup = fetch_page(url)
    if not soup:
        return []

    title = soup.find('h1')
    title = title.get_text(strip=True) if title else url.split('/')[-1]

    files, sub_pages = get_links(soup, url)

    results = []

    # Collect files at this level
    for f in files:
        period, sort = parse_period(f['text'] + ' ' + f['filename'])
        if period and sort >= 202400:  # Recent data only
            results.append({
                'url': f['url'],
                'period': period,
                'sort': sort,
                'text': f['text'],
                'depth': depth,
                'category': url.split('/')[-1]
            })

    if files:
        print(f"{indent}   📁 Found {len(files)} files, {len(results)} with periods")

    # Decide whether to explore sub-pages
    if sub_pages and depth < max_depth:
        # If no files found at this level, explore ALL sub-pages
        if not files:
            print(f"{indent}   🔍 No files here, exploring {len(sub_pages)} sub-pages...")
            for sp in sub_pages[:15]:
                results.extend(deep_explore(sp['url'], max_depth, visited))
        else:
            # Have files but also sub-pages - explore those that look like data
            data_pattern = re.compile(r'(data|statistics|download|file|202\d|q[1-4]|overnight|day)', re.I)
            for sp in sub_pages:
                if data_pattern.search(sp['text']) or data_pattern.search(sp['path']):
                    results.extend(deep_explore(sp['url'], max_depth, visited))

    return results

def generate_yaml(code, name, url, results):
    """Generate YAML config for this source."""
    # Deduplicate by period, keeping first occurrence
    seen = {}
    for r in sorted(results, key=lambda x: (-x['sort'], x['depth'])):
        key = r['period']
        if key not in seen:
            seen[key] = r

    periods = sorted(seen.values(), key=lambda x: x['sort'])

    yaml = f"""
  # {'='*70}
  # {name}
  # {'='*70}
  {code}:
    name: "{name}"
    frequency: quarterly
    landing_page: {url}
    reference_manifest: null
    urls:
"""
    for p in periods:
        yaml += f"      - period: {p['period']}\n"
        yaml += f"        url: {p['url']}\n"

    return yaml, len(periods)

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/deep_explore_source.py <url> [code]")
        print("\nExample:")
        print("  python scripts/deep_explore_source.py https://www.england.nhs.uk/.../bed-availability-and-occupancy/")
        sys.exit(1)

    url = sys.argv[1].rstrip('/')
    code = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"\n🔍 Deep exploring: {url}\n")

    results = deep_explore(url, max_depth=4)

    if not results:
        print("\n❌ No data files found")
        return

    # Group by category
    categories = {}
    for r in results:
        cat = r.get('category', 'default')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)

    print(f"\n{'='*60}")
    print(f"📊 Results: {len(results)} files in {len(categories)} categories")

    for cat, items in categories.items():
        print(f"\n   {cat}: {len(items)} files")
        periods = sorted(set(r['period'] for r in items))
        print(f"   Periods: {periods[:5]}{'...' if len(periods) > 5 else ''}")

    # Generate YAML
    if not code:
        code = re.sub(r'[^a-z0-9]+', '_', url.split('/')[-1])[:20] or 'source'

    # Get title from first page
    soup = fetch_page(url)
    title = soup.find('h1').get_text(strip=True) if soup and soup.find('h1') else url.split('/')[-1]

    yaml, count = generate_yaml(code, title, url, results)

    print(f"\n{'='*60}")
    print(yaml)
    print(f"{'='*60}")
    print(f"\n✅ {code} | {count} periods")
    print(f"\nTo add to publications2.yaml, copy the above YAML block.")

if __name__ == "__main__":
    main()
