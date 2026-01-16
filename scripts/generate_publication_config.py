#!/usr/bin/env python3
"""Generate publication config from NHS URL. LLM-powered, minimal questions."""

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
    results, seen = [], set()
    for item in items:
        text = (item.get('name') or item.get('path') or '').lower()
        for name, num in MONTHS.items():
            # Pattern 1: month-YYYY (standard)
            m = re.search(rf'{name}[-_]?(\d{{4}})', text)
            if m:
                year = int(m.group(1))
                code = f"{MSHORT[num-1]}{str(year)[-2:]}"
                if (code, item['url']) not in seen:
                    seen.add((code, item['url']))
                    results.append({'period':code, 'url':item['url'], 'sort':year*100+num})
                break
            # Pattern 2: month-YYYY-YY (fiscal year format like march-2023-24)
            m = re.search(rf'{name}[-_](\d{{4}})[-_]\d{{2}}', text)
            if m:
                year = int(m.group(1))
                code = f"{MSHORT[num-1]}{str(year)[-2:]}"
                if (code, item['url']) not in seen:
                    seen.add((code, item['url']))
                    results.append({'period':code, 'url':item['url'], 'sort':year*100+num})
                break
    return sorted(results, key=lambda x: x['sort'])

def llm(prompt):
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel(os.getenv('LLM_MODEL','gemini-2.0-flash-exp'),
        generation_config={"temperature":0.1})
    response = model.generate_content(prompt)
    # Extract usage stats
    stats = {'input': 0, 'output': 0, 'cost': 0.0}
    if hasattr(response, 'usage_metadata'):
        stats['input'] = getattr(response.usage_metadata, 'prompt_token_count', 0)
        stats['output'] = getattr(response.usage_metadata, 'candidates_token_count', 0)
        # Gemini Flash pricing: $0.075/1M input, $0.30/1M output
        stats['cost'] = (stats['input'] * 0.000000075) + (stats['output'] * 0.0000003)
    return response.text.strip(), stats

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/generate_publication_config.py <url>")
        sys.exit(1)

    url = sys.argv[1]
    print(f"\n🔍 {url}\n")

    data = fetch(url)
    is_files = len(data['files']) > len(data['pages'])
    periods = parse_periods(data['files'] if is_files else data['pages'])

    if not periods:
        print("❌ No periods found"); return

    print(f"   {data['title'][:60]}")
    print(f"   {'Files' if is_files else 'Pages'}: {len(periods)} ({periods[0]['period']}→{periods[-1]['period']})")

    # Build context for LLM - include sample URLs so it can spot patterns
    sample_urls = [p['url'].split('/')[-1] if '/' in p['url'] else p['url'] for p in periods[:10]]
    unique_periods = len(set(p['period'] for p in periods))
    has_duplicates = len(periods) > unique_periods

    default_start = periods[0]['period'] if len(periods) < 20 else 'jan24'
    prompt = f"""NHS publication config generator. Analyze the data and ask smart questions.

DATA:
- URL: {url}
- Title: {data['title']}
- Items found: {len(periods)} ({unique_periods} unique periods)
- Range: {periods[0]['period']} → {periods[-1]['period']}
- Sample URLs: {sample_urls}
- Has duplicates: {has_duplicates}

Return JSON:
{{"code":"short_code","name":"Clean Name","frequency":"monthly|quarterly","start":"{default_start}","filters":{{}},"questions":[]}}

RULES:
- code: SHORT snake_case max 15 chars
- frequency: infer from period gaps
- questions: Array of {{"id":"xxx","q":"Question?","options":["opt1","opt2"],"default":"opt1"}}

IMPORTANT - Be AGENTIC. Ask smart questions:

1. PATTERN-BASED (if you spot them in sample URLs):
   - "final" vs "provisional" → ask which version
   - "revised" vs original → ask preference
   - regional vs national scope → ask which
   - different file types → ask format preference

2. ALWAYS ASK these open-ended questions to capture domain knowledge:
   - "Any URL keywords to INCLUDE?" (e.g., user might say "commissioner" or "provider")
   - "Any URL keywords to EXCLUDE?" (e.g., user might say "time-series" or "summary")

3. If >20 periods, ask start period

Question format: {{"id":"xxx","q":"Short question?","options":["opt1","opt2"],"default":"opt1"}}
For open-ended: {{"id":"include_keyword","q":"Include URLs containing? (blank=all)","default":""}}

JSON only, no markdown."""

    stats = {'input': 0, 'output': 0, 'cost': 0.0}
    try:
        response, stats = llm(prompt)
        r = json.loads(re.sub(r'^```json\s*|\s*```$', '', response))
    except:
        r = {'code':url.split('/')[-1].replace('-','_')[:15], 'name':data['title'][:40], 'frequency':'monthly', 'start':periods[0]['period'], 'questions':[]}

    print(f"\n🤖 {r['code']} | {r['frequency']} | {stats['input']}→{stats['output']} tokens | ${stats['cost']:.6f}")

    cfg = {k:r.get(k,'') for k in ['code','name','frequency','start']}
    filters = {}

    # Ask LLM-generated questions
    questions = r.get('questions', [])
    if questions:
        print("\n📝 Questions:\n")
        for q in questions:
            opts = q.get('options', [])
            default = q.get('default', opts[0] if opts else '')

            if opts:
                print(f"   {q.get('q','?')}")
                for i, opt in enumerate(opts, 1):
                    marker = " ←" if opt == default else ""
                    print(f"      {i}. {opt}{marker}")
                ans = input(f"   [{default}]: ").strip()

                # Parse answer
                if ans.isdigit() and 1 <= int(ans) <= len(opts):
                    ans = opts[int(ans)-1]
                elif not ans:
                    ans = default
            else:
                ans = input(f"   {q.get('q','?')} [{default}]: ").strip() or default

            qid = q.get('id', '')
            if qid == 'start': cfg['start'] = ans
            elif qid: filters[qid] = ans
            print()

    # Apply start filter
    if cfg.get('start') and cfg['start'] != 'all':
        m = re.match(r'([a-z]{3})(\d{2})', cfg['start'])
        if m: periods = [p for p in periods if p['sort'] >= (2000+int(m.group(2)))*100+MSHORT.index(m.group(1))+1]

    # Apply pattern filters
    for fid, fval in filters.items():
        if not fval or fval.lower() in ['all', 'both', '']:
            continue

        if fid == 'exclude_keyword':
            # Exclude URLs containing this keyword
            periods = [p for p in periods if fval.lower() not in p['url'].lower()]
        else:
            # Include URLs containing this keyword (for include_keyword and pattern matches)
            filtered = [p for p in periods if fval.lower() in p['url'].lower()]
            if filtered:  # Only apply if matches something
                periods = filtered

    # YAML
    yaml = f"""  {cfg['code']}:
    name: "{cfg['name']}"
    frequency: {cfg['frequency']}
    landing_page: {url}
    reference_manifest: null
    urls:"""
    for p in periods: yaml += f"\n      - period: {p['period']}\n        url: {p['url']}"

    print("\n" + "="*60 + "\n" + yaml + "\n" + "="*60)
    if periods:
        print(f"\n✅ {cfg['code']} | {len(periods)} periods | {periods[0]['period']}→{periods[-1]['period']}")
    else:
        print(f"\n⚠️  No periods after filtering")

if __name__ == "__main__": main()
