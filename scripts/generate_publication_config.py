#!/usr/bin/env python3
"""Generate publication config from NHS URL. LLM-powered with smart filtering."""

import json, os, re, sys, warnings
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

def fetch(url):
    soup = BeautifulSoup(requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=30).content, 'html.parser')
    h1, title = soup.find('h1'), soup.find('title')
    base = urlparse(url).path.rstrip('/')
    files, pages = [], []
    for a in soup.find_all('a', href=True):
        href = urljoin(url, a['href'])
        path = urlparse(href).path.lower()
        if path.endswith(('.xlsx','.xls','.csv','.zip')): files.append({'url':href,'name':path.split('/')[-1]})
        elif urlparse(href).path.startswith(base+'/'):
            path_parts = [p for p in urlparse(href).path.split('/') if p]
            pages.append({'url':href,'path':path_parts[-1] if path_parts else ''})
    return {'title': (h1 or title).get_text(strip=True) if (h1 or title) else '', 'files':files, 'pages':pages}

def parse_periods(items):
    results = []
    for item in items:
        text = (item.get('name') or item.get('path') or '').lower()
        for name, num in MONTHS.items():
            # Pattern 1: month-YYYY (standard) or month-YYYY-YY (fiscal)
            m = re.search(rf'{name}[-_]?(\d{{4}})', text)
            if m:
                year = int(m.group(1))
                code = f"{MSHORT[num-1]}{str(year)[-2:]}"
                results.append({'period':code, 'url':item['url'], 'sort':year*100+num, 'text':text})
                break
    return sorted(results, key=lambda x: x['sort'])

def fy_to_sort_range(fy_list):
    """Convert list of FYs to (min_sort, max_sort) for filtering"""
    if not fy_list: return None, None
    min_sort = min((2000 + int(fy[:2])) * 100 + 4 for fy in fy_list)  # apr of first FY
    max_sort = max((2000 + int(fy[3:])) * 100 + 3 for fy in fy_list)  # mar of last FY
    return min_sort, max_sort

def get_available_fy(periods):
    """Get available fiscal years from periods"""
    if not periods: return []
    min_sort, max_sort = periods[0]['sort'], periods[-1]['sort']
    # Convert to fiscal years (Apr-Mar)
    min_fy = (min_sort // 100) if (min_sort % 100) >= 4 else (min_sort // 100) - 1
    max_fy = (max_sort // 100) if (max_sort % 100) >= 4 else (max_sort // 100) - 1
    return [f"{y%100:02d}/{(y+1)%100:02d}" for y in range(min_fy, max_fy + 1)]

def llm(prompt, stats_accum=None):
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel(os.getenv('LLM_MODEL','gemini-2.0-flash-exp'),
        generation_config={"temperature":0.1})
    response = model.generate_content(prompt)
    stats = {'input': 0, 'output': 0, 'cost': 0.0}
    if hasattr(response, 'usage_metadata'):
        stats['input'] = getattr(response.usage_metadata, 'prompt_token_count', 0)
        stats['output'] = getattr(response.usage_metadata, 'candidates_token_count', 0)
        stats['cost'] = (stats['input'] * 0.000000075) + (stats['output'] * 0.0000003)
    if stats_accum:
        for k in stats: stats_accum[k] += stats[k]
    return response.text.strip(), stats

def select_best(group, prefs):
    """Select best URL from group based on preference order (e.g., ['final','provisional'])"""
    for pref in prefs:
        for item in group:
            if pref in item['text']: return item
    return group[0]  # fallback to first

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/generate_publication_config.py <url> [filters]")
        print("       filters: optional, e.g. '22/23, final preferred, xlsx'")
        sys.exit(1)

    url = sys.argv[1]
    explicit_filters = ' '.join(sys.argv[2:]) if len(sys.argv) > 2 else None
    print(f"\n🔍 {url}\n")

    data = fetch(url)
    is_files = len(data['files']) > len(data['pages'])
    all_periods = parse_periods(data['files'] if is_files else data['pages'])

    if not all_periods:
        print("❌ No periods found"); return

    # Calculate context for smart questions
    unique = len(set(p['period'] for p in all_periods))
    has_dupes = len(all_periods) > unique
    avail_fy = get_available_fy(all_periods)
    latest_fy = avail_fy[-1] if avail_fy else None
    sample = [p['text'][:80] for p in all_periods[:15]]

    print(f"   {data['title'][:60]}")
    print(f"   {'Files' if is_files else 'Pages'}: {len(all_periods)} items, {unique} unique periods")
    print(f"   📅 Available: {all_periods[0]['period']}→{all_periods[-1]['period']} (FY {avail_fy[0]}→{avail_fy[-1]})" if avail_fy else "")
    if has_dupes: print(f"   ⚠️  Duplicates detected (likely final/provisional versions)")

    total_stats = {'input': 0, 'output': 0, 'cost': 0.0}

    # LLM generates just the config (code, name, frequency)
    prompt = f"""NHS publication config. Generate code and name.

URL: {url}
Title: {data['title']}

Return JSON: {{"code":"short_snake_case_max15","name":"Clean Title","frequency":"monthly|quarterly|annual"}}
IMPORTANT: code should be SHORT identifier (e.g. "proms", "ae_attendances"), NOT include dates.
Infer frequency from: {unique} periods over {len(avail_fy)} years. JSON only."""

    try:
        resp, _ = llm(prompt, total_stats)
        r = json.loads(re.sub(r'^```json\s*|\s*```$', '', resp))
    except:
        r = {'code':url.split('/')[-1].replace('-','_')[:15], 'name':data['title'][:40], 'frequency':'monthly'}

    cfg = {'code':r.get('code',''), 'name':r.get('name',''), 'frequency':r.get('frequency','monthly')}

    # PROACTIVE: Analyze data and present findings FIRST
    analysis_prompt = f"""Analyze this NHS publication data for a user who wants to extract and tabularize it.

PUBLICATION: {data['title']}
AVAILABLE DATA:
- Fiscal years: {avail_fy} (latest: {latest_fy})
- Total items: {len(all_periods)}, unique periods: {unique}
- Has duplicates: {has_dupes}
- Sample URLs:
{chr(10).join(f'  {p["period"]}: {p["text"]}' for p in all_periods[:20])}

Analyze the URLs and identify:
1. Data versions (provisional/final/revised?) - which exist?
2. Data granularity (monthly/quarterly releases?)
3. Any special patterns (regional variants, file types, etc.)
4. Recommended default filter for most users

Return JSON:
{{
  "summary": "2-3 sentence summary of what data is available",
  "versions": ["final", "provisional"] or null (versions found in URLs),
  "has_quarterly": true/false (quarterly aggregates present?),
  "patterns": ["pattern1"] or null (other notable patterns),
  "recommendation": "Suggested filter for typical use case"
}}
JSON only."""

    try:
        analysis_resp, _ = llm(analysis_prompt, total_stats)
        analysis = json.loads(re.sub(r'^```json\s*|\s*```$', '', analysis_resp))
    except:
        analysis = {'summary': f'{unique} periods available from {avail_fy[0]} to {latest_fy}', 'recommendation': latest_fy}

    # Present findings to user
    print(f"\n🤖 {r['code']} | {r['frequency']}")
    print(f"\n📊 Analysis:")
    print(f"   {analysis.get('summary', 'Data available for extraction.')}")
    if analysis.get('versions'): print(f"   • Versions: {', '.join(analysis['versions'])}")
    if analysis.get('has_quarterly'): print(f"   • Includes quarterly aggregates")
    if analysis.get('patterns'): print(f"   • Patterns: {', '.join(analysis['patterns'])}")
    print(f"\n   💡 Recommendation: {analysis.get('recommendation', latest_fy)}")

    # Now ask what they want (with context already provided)
    if explicit_filters:
        user_input = explicit_filters
        print(f"\n📝 Using: {user_input}")
    else:
        user_input = input(f"\n📝 What do you want? (Enter for recommendation): ").strip()
        if not user_input:
            user_input = analysis.get('recommendation', latest_fy)
            print(f"   → Using: {user_input}")

    # Parse filter request
    filter_prompt = f"""Create filter rules for NHS publication data.

USER REQUEST: "{user_input}"
Available FYs: {avail_fy} (latest: {latest_fy})
Has duplicates: {has_dupes}
Detected versions: {analysis.get('versions', [])}

Return JSON:
{{
  "fy_start": "XX/XX or null",
  "fy_end": "XX/XX or null",
  "must_contain": ["keyword"] or null,
  "must_not_contain": ["keyword"] or null,
  "prefer_keywords": ["final", "provisional"] or null (preference order),
  "dedupe_by_period": true/false
}}
JSON only."""

    try:
        parsed, _ = llm(filter_prompt, total_stats)
        filters = json.loads(re.sub(r'^```json\s*|\s*```$', '', parsed))
    except:
        filters = {'fy_start': latest_fy, 'fy_end': latest_fy}

    # Show applied filters
    applied = []
    if filters.get('fy_start') or filters.get('fy_end'):
        applied.append(f"FY {filters.get('fy_start') or 'start'}→{filters.get('fy_end') or 'end'}")
    if filters.get('must_contain'): applied.append(f"include {filters['must_contain']}")
    if filters.get('prefer_keywords'): applied.append(f"prefer {filters['prefer_keywords']}")
    if applied: print(f"\n   📋 Applying: {', '.join(applied)}")

    periods = all_periods[:]

    # Apply fiscal year range
    fy_start, fy_end = filters.get('fy_start'), filters.get('fy_end')
    if fy_start or fy_end:
        fy_list = []
        started = not fy_start  # if no start, include from beginning
        for fy in avail_fy:
            if fy == fy_start: started = True
            if started: fy_list.append(fy)
            if fy == fy_end: break
        if fy_list:
            start, end = fy_to_sort_range(fy_list)
            periods = [p for p in periods if start <= p['sort'] <= end]
            print(f"   📅 FY {fy_list[0]}→{fy_list[-1]}: {len(periods)} periods")

    # Apply must_contain (ANY match)
    must = filters.get('must_contain') or []
    if must:
        before = len(periods)
        filtered = [p for p in periods if any(kw.lower() in p['text'] or kw.lower() in p['url'].lower() for kw in must)]
        if filtered:
            periods = filtered
            print(f"   ✓ Must contain {must}: {before}→{len(periods)}")

    # Apply must_not_contain
    must_not = filters.get('must_not_contain') or []
    if must_not:
        before = len(periods)
        periods = [p for p in periods if not any(kw.lower() in p['text'] or kw.lower() in p['url'].lower() for kw in must_not)]
        print(f"   ✗ Excluding {must_not}: {before}→{len(periods)}")

    # Dedupe by period with preference
    if filters.get('dedupe_by_period') and filters.get('prefer_keywords'):
        prefs = filters['prefer_keywords']
        from collections import defaultdict
        by_period = defaultdict(list)
        for p in periods: by_period[p['period']].append(p)
        periods = sorted([select_best(g, prefs) for g in by_period.values()], key=lambda x: x['sort'])
        print(f"   🎯 Dedupe (prefer {prefs}): {len(periods)} periods")

    print(f"\n   💰 {total_stats['input']}→{total_stats['output']} tokens | ${total_stats['cost']:.6f}")

    # YAML output
    yaml = f"""  {cfg['code']}:
    name: "{cfg['name']}"
    frequency: {cfg['frequency']}
    landing_page: {url}
    reference_manifest: null
    urls:"""
    for p in periods: yaml += f"\n      - period: {p['period']}\n        url: {p['url']}"

    print("\n" + "="*60 + "\n" + yaml + "\n" + "="*60)
    print(f"\n✅ {cfg['code']} | {len(periods)} periods" + (f" | {periods[0]['period']}→{periods[-1]['period']}" if periods else " | ⚠️ empty"))

if __name__ == "__main__": main()
