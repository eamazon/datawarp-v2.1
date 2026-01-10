# DataWarp v2: Semi-Production Implementation Plan (REVISED)

**Status:** Draft for Review
**Created:** 2026-01-07
**Revised:** 2026-01-07 (Smart & Deterministic Approach)
**Target Timeline:** 4-6 weeks (phased rollout)

---

## Executive Summary

This plan moves DataWarp v2 from development to **semi-production** with 10 core NHS publications, addressing three critical challenges:

1. **Code Stability Problem:** LLMs embed dates in source codes, breaking continuity across periods
2. **Monitoring Gap:** No automated detection of new releases or failure tracking
3. **Wide Date Columns:** NHS reports use month columns (Apr_2025, May_2025...) instead of long format

**Key Design Principle:** Leverage existing LLM enrichment and standard libraries instead of hardcoded pattern maintenance.

**Success Criteria:**
- 10 feeds loading automatically with 80%+ success rate
- Historical backfill of 3-5 years completed
- Single table per source (not per period)
- Drift handled gracefully with alerts
- Minimal maintenance burden (no pattern lists to update)

---

## Problem Analysis

### Problem 1: Enrichment Not Applied (CRITICAL)

**Current Reality:**
```
YAML manifest (generated):     code: "summary_nov25_table_1"  ← Has date
JSON enrichment (Gemini):       code: "adhd_summary_estimated_prevalence_age"  ← Clean!
YAML manifest (loaded):         code: "summary_nov25_table_1"  ← Still has date (never updated!)
Database:                       tbl_summary_nov25_table_1      ← Wrong table name
```

**Root Cause:**
- LLM enrichment **already** produces canonical codes
- But enriched codes in JSON never make it back to YAML
- Workflow gap between `enrich.py` and `datawarp load`

**Impact:**
- Creates 12 tables/year for same dataset
- Breaks time-series queries
- Historical analysis requires UNION of 50+ tables

### Problem 2: No Publication Monitoring

**Current State:**
- Manual checking of NHS publication pages
- No record of what's been loaded
- URL patterns change unpredictably
- Failures only discovered when queries break

**Impact:**
- 40% of URLs fail (old XLS, access issues, format changes)
- Missing data goes unnoticed
- Can't predict next release URL

### Problem 3: Wide Date Columns

**Example (GP Appointments):**
```csv
Provider_Name,       Apr_2025, May_2025, Jun_2025
NHS Trust A,         1500,     1600,     1550
```

**Impact:**
- Schema drift every month (new column added)
- Can't query across time periods easily
- Visualization tools struggle with wide format

**Should Be:**
```csv
Provider_Name,    Period,    Value
NHS Trust A,      2025-04,   1500
NHS Trust A,      2025-05,   1600
```

---

## Solution Architecture

### Three-Phase Approach

```
Phase 1: Enrichment Integration (Weeks 1-2)
├── Apply enriched codes from JSON to YAML (no canonicalization module!)
├── Fingerprinting for cross-period matching
├── Database schema for canonical registry
└── Testing with real MSDS/ADHD data

Phase 2: Monitoring & Scheduling (Weeks 3-4)
├── Publication registry (10 feeds)
├── URL discovery module
├── Backfill workflow
└── Alert system

Phase 3: Date Column Pivoting (Week 5)
├── Smart date detection (dateutil.parser, not regex)
├── LLM-enhanced wide date flagging
├── Pivot transformation
└── Integration with insert pipeline

Phase 4: Stabilization & Refinement (Week 6)
├── User testing
├── Bug fixes
└── Documentation
```

---

# Phase 1: Enrichment Integration

## Objectives

1. **Apply LLM-enriched codes** - Use codes from JSON enrichment (already canonical!)
2. **Fingerprinting** - Match sources across periods via column signatures
3. **Audit trail** - Track LLM → canonical mappings
4. **Enable continuity** - Same table across periods

## Key Insight: Don't Rebuild What LLMs Already Do

**OLD APPROACH (REJECTED):**
```python
# Hardcoded pattern maintenance nightmare
def canonicalize_code(llm_code: str) -> str:
    code = re.sub(r'_(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', '_', code)
    code = re.sub(r'_(january|february|march|april|may|june|july|august|september|october|november|december)', '_', code)
    code = re.sub(r'_\d{4}', '_', code)  # Years
    code = re.sub(r'_\d{2}', '_', code)  # Short years
    code = re.sub(r'_(provisional|final|revised)', '_', code)
    # ... 50 more patterns to maintain
    return code
```

**NEW APPROACH (LEAN):**
```python
# Just use what Gemini/Qwen already produced!
def apply_enriched_codes(yaml_path: str, json_path: str) -> None:
    yaml_data = yaml.safe_load(open(yaml_path))
    json_data = json.load(open(json_path))

    # Map by file URL (unique identifier)
    enriched_map = {s['files'][0]['url']: s for s in json_data['manifest']}

    for source in yaml_data['sources']:
        url = source['files'][0]['url']
        if url in enriched_map:
            enriched = enriched_map[url]
            source['code'] = enriched['code']  # LLM already canonicalized!
            source['name'] = enriched['name']
            source['metadata'] = enriched.get('metadata', {})

    yaml.safe_dump(yaml_data, open(yaml_path + '.enriched', 'w'))
```

**Result:** 50 lines instead of 150+ lines with pattern maintenance burden.

## Database Schema Changes

### New Tables

```sql
-- scripts/schema/04_create_registry_tables.sql

-- Canonical source registry
CREATE TABLE datawarp.tbl_canonical_sources (
  canonical_code VARCHAR(100) PRIMARY KEY,
  publication_id VARCHAR(50),
  canonical_name TEXT NOT NULL,
  canonical_table VARCHAR(100) NOT NULL,

  -- Structural fingerprint for matching
  fingerprint JSONB NOT NULL,

  -- Tracking
  first_seen_period VARCHAR(20),
  last_seen_period VARCHAR(20),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),

  -- Stats
  total_loads INTEGER DEFAULT 0,
  total_rows_loaded BIGINT DEFAULT 0
);

CREATE INDEX idx_canonical_publication ON datawarp.tbl_canonical_sources(publication_id);
CREATE INDEX idx_canonical_fingerprint ON datawarp.tbl_canonical_sources USING gin(fingerprint);

-- Source mapping history
CREATE TABLE datawarp.tbl_source_mappings (
  id SERIAL PRIMARY KEY,

  -- What the LLM generated
  llm_generated_code VARCHAR(100) NOT NULL,
  period VARCHAR(20),

  -- What it was mapped to
  canonical_code VARCHAR(100) REFERENCES datawarp.tbl_canonical_sources(canonical_code),

  -- Match quality
  match_confidence FLOAT NOT NULL,  -- 0.0 to 1.0
  match_method VARCHAR(50) NOT NULL,  -- 'exact', 'fingerprint', 'manual'

  -- Fingerprint at time of match
  source_fingerprint JSONB,

  -- Audit
  mapped_at TIMESTAMP DEFAULT NOW(),
  mapped_by VARCHAR(50) DEFAULT 'system',
  reviewed BOOLEAN DEFAULT FALSE,
  review_notes TEXT,

  UNIQUE(llm_generated_code, period)
);

CREATE INDEX idx_mapping_canonical ON datawarp.tbl_source_mappings(canonical_code);
CREATE INDEX idx_mapping_period ON datawarp.tbl_source_mappings(period);
CREATE INDEX idx_mapping_confidence ON datawarp.tbl_source_mappings(match_confidence);

-- Drift event log
CREATE TABLE datawarp.tbl_drift_events (
  id SERIAL PRIMARY KEY,
  canonical_code VARCHAR(100),
  period VARCHAR(20),

  drift_type VARCHAR(50) NOT NULL,  -- 'new_columns', 'missing_columns', 'type_change', 'wide_date_detected'
  severity VARCHAR(20) NOT NULL,     -- 'info', 'warning', 'error'

  details JSONB NOT NULL,

  -- Actions taken
  auto_resolved BOOLEAN DEFAULT FALSE,
  resolution_action TEXT,

  detected_at TIMESTAMP DEFAULT NOW(),
  notified BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_drift_code ON datawarp.tbl_drift_events(canonical_code);
CREATE INDEX idx_drift_severity ON datawarp.tbl_drift_events(severity);
CREATE INDEX idx_drift_notified ON datawarp.tbl_drift_events(notified) WHERE NOT notified;
```

## Code Modules

### Module 1: Fingerprinting (Pure Deterministic)

**File:** `src/datawarp/registry/__init__.py` (new package)

```python
"""Source code fingerprinting and registry management."""
```

**File:** `src/datawarp/registry/fingerprint.py` (~80 lines)

```python
"""
Structural fingerprinting for cross-period source matching.
Pure deterministic - no LLM calls, no pattern matching.
"""
import hashlib
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass

@dataclass
class Fingerprint:
    """Structural fingerprint for source matching."""
    column_names: Set[str]
    column_count: int
    signature_hash: str  # MD5 of sorted column names

def generate_fingerprint(columns: List[Dict]) -> Fingerprint:
    """
    Create structural fingerprint from column metadata.
    Used for matching sources across periods when column structures are identical.
    """
    # Extract and normalize column names
    col_names = set(c['original_name'].lower() for c in columns)

    # Generate signature hash
    sorted_names = sorted(col_names)
    signature = '|'.join(sorted_names)
    sig_hash = hashlib.md5(signature.encode()).hexdigest()

    return Fingerprint(
        column_names=col_names,
        column_count=len(col_names),
        signature_hash=sig_hash
    )

def jaccard_similarity(fp1: Fingerprint, fp2: Fingerprint) -> float:
    """
    Calculate Jaccard similarity between two fingerprints.
    Returns: 0.0 (no match) to 1.0 (perfect match)
    """
    if fp1.signature_hash == fp2.signature_hash:
        return 1.0  # Exact match

    intersection = len(fp1.column_names & fp2.column_names)
    union = len(fp1.column_names | fp2.column_names)

    return intersection / union if union > 0 else 0.0

def find_best_match(
    new_fp: Fingerprint,
    registry: Dict[str, Fingerprint],
    threshold: float = 0.80
) -> Tuple[str, float]:
    """
    Find best matching canonical code from registry.

    Returns:
        (canonical_code, confidence) or (None, 0.0) if no match
    """
    best_match = None
    best_score = 0.0

    for canonical_code, stored_fp in registry.items():
        score = jaccard_similarity(new_fp, stored_fp)
        if score > best_score:
            best_score = score
            best_match = canonical_code

    if best_score >= threshold:
        return (best_match, best_score)

    return (None, 0.0)
```

### Module 2: Enrichment Applier (Workflow Integration)

**File:** `scripts/apply_enrichment.py` (~50 lines)

```python
#!/usr/bin/env python3
"""
Apply LLM-enriched codes and metadata back to YAML manifest.

This bridges the gap between enrichment and loading:
  url_to_manifest → enrich → apply_enrichment → load
                               ↑ YOU ARE HERE

Usage:
    python scripts/apply_enrichment.py \
        manifests/adhd_enriched.yaml \
        manifests/adhd_enriched_llm_response.json \
        manifests/adhd_canonical.yaml
"""
import sys
import yaml
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table

console = Console()

def apply_enrichment(yaml_path: str, json_path: str, output_path: str):
    """Apply enriched codes and metadata from JSON to YAML."""

    # Load both files
    console.print(f"[cyan]Loading YAML:[/cyan] {yaml_path}")
    yaml_data = yaml.safe_load(open(yaml_path))

    console.print(f"[cyan]Loading JSON:[/cyan] {json_path}")
    json_data = json.load(open(json_path))

    # Map enriched sources by file URL (unique identifier)
    enriched_map = {}
    for source in json_data.get('manifest', []):
        if source.get('files') and len(source['files']) > 0:
            url = source['files'][0]['url']
            enriched_map[url] = source

    console.print(f"\n[green]Found {len(enriched_map)} enriched sources[/green]")

    # Track updates
    updates = []

    # Apply enriched data to YAML sources
    for source in yaml_data.get('sources', []):
        if not source.get('files') or len(source['files']) == 0:
            continue

        url = source['files'][0]['url']

        if url in enriched_map:
            enriched = enriched_map[url]

            # Track change
            old_code = source.get('code', 'N/A')
            new_code = enriched['code']

            # Update source with enriched data
            source['code'] = new_code
            source['table'] = f"tbl_{new_code}"
            source['name'] = enriched.get('name', source.get('name', ''))
            source['description'] = enriched.get('description', '')
            source['metadata'] = enriched.get('metadata', {})
            source['columns'] = enriched.get('columns', [])

            # Preserve original for audit
            source['_original_code'] = old_code

            updates.append({
                'url': url[:50] + '...' if len(url) > 50 else url,
                'old_code': old_code,
                'new_code': new_code,
                'changed': old_code != new_code
            })

    # Display changes
    table = Table(title="Code Updates")
    table.add_column("File URL", style="dim")
    table.add_column("Original Code", style="yellow")
    table.add_column("Enriched Code", style="green")
    table.add_column("Changed", justify="center")

    for update in updates:
        changed_icon = "✓" if update['changed'] else "="
        changed_style = "bold green" if update['changed'] else "dim"

        table.add_row(
            update['url'],
            update['old_code'],
            update['new_code'],
            f"[{changed_style}]{changed_icon}[/{changed_style}]"
        )

    console.print(table)

    # Save updated YAML
    with open(output_path, 'w') as f:
        yaml.dump(yaml_data, f, sort_keys=False, default_flow_style=False)

    console.print(f"\n[bold green]✅ Enriched manifest saved:[/bold green] {output_path}")

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)

    apply_enrichment(sys.argv[1], sys.argv[2], sys.argv[3])
```

## Integration with Existing Workflow

### Updated Workflow (CRITICAL CHANGE)

**OLD (broken):**
```bash
url_to_manifest → enrich → load
                           ↑
                    Enrichment never applied!
```

**NEW (fixed):**
```bash
# Step 1: Generate raw manifest (unchanged)
python scripts/url_to_manifest.py \
  "https://digital.nhs.uk/.../april-2025" \
  manifests/gp_apr25_raw.yaml

# Step 2: Enrich with LLM (unchanged)
python scripts/enrich.py \
  manifests/gp_apr25_raw.yaml \
  manifests/gp_apr25_enriched.yaml

# Step 3: Apply enrichment (NEW STEP - CRITICAL!)
python scripts/apply_enrichment.py \
  manifests/gp_apr25_enriched.yaml \
  manifests/gp_apr25_enriched_llm_response.json \
  manifests/gp_apr25_canonical.yaml

# Step 4: Load (unchanged)
datawarp load-batch manifests/gp_apr25_canonical.yaml
```

## Testing Strategy

### Test 1: ADHD Manifest (Real Example)

```bash
# Apply enrichment to your actual ADHD data
python scripts/apply_enrichment.py \
  manifests/test_adhd_nov25_enriched_external.yaml \
  manifests/test_adhd_nov25_enriched_external_llm_response.json \
  manifests/test_adhd_canonical.yaml

# Check what changed
grep "^  code:" manifests/test_adhd_nov25_enriched_external.yaml
grep "^  code:" manifests/test_adhd_canonical.yaml
```

**Expected:**
```
Original:  code: summary_nov25_table_1
Enriched:  code: adhd_summary_estimated_prevalence_age  # ✓ No date!
```

### Test 2: Cross-Period Consistency

Load November ADHD, then December ADHD - verify fingerprint matching:

```sql
-- After loading both periods
SELECT
    canonical_code,
    COUNT(DISTINCT period) as period_count,
    MIN(period) as first_period,
    MAX(period) as last_period
FROM datawarp.tbl_source_mappings
WHERE canonical_code LIKE 'adhd%'
GROUP BY canonical_code;

-- Expected: Each canonical_code has 2 periods (Nov, Dec)
```

## Success Criteria (Phase 1)

- [ ] Database schema deployed
- [ ] Fingerprinting module passes unit tests
- [ ] apply_enrichment.py successfully merges JSON→YAML
- [ ] ADHD data consolidates correctly across periods
- [ ] Registry stores fingerprints correctly
- [ ] Drift detection identifies structural changes

## Rollout Plan

1. **Week 1:** Implement modules, database schema, testing
2. **Week 2:** Test with ADHD + MSDS data, refine fingerprinting
3. **Sign-off:** User approval before Phase 2

---

# Phase 2: Monitoring & Scheduling

## Objectives

1. Track 10 core NHS publications
2. Automatically detect new releases
3. Backfill 3-5 years of historical data
4. Alert on failures

## Database Schema Changes

### New Tables

```sql
-- scripts/schema/05_create_publication_tracking.sql

-- Publication registry
CREATE TABLE datawarp.tbl_publications (
  publication_id VARCHAR(50) PRIMARY KEY,
  publication_name TEXT NOT NULL,

  -- URL patterns
  base_url_pattern TEXT NOT NULL,
  latest_url TEXT,

  -- Schedule
  frequency VARCHAR(20) NOT NULL,  -- 'monthly', 'quarterly', 'annual'
  expected_delay_days INTEGER,     -- Days after period end until published

  -- Expectations
  expected_sources_count INTEGER,

  -- Status
  active BOOLEAN DEFAULT TRUE,
  last_check_timestamp TIMESTAMP,
  next_expected_period VARCHAR(20),

  -- Metadata
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  notes TEXT
);

-- Period tracking
CREATE TABLE datawarp.tbl_publication_periods (
  id SERIAL PRIMARY KEY,
  publication_id VARCHAR(50) REFERENCES datawarp.tbl_publications(publication_id),
  period VARCHAR(20) NOT NULL,

  -- URLs
  expected_url TEXT,
  actual_url TEXT,
  url_discovered_at TIMESTAMP,

  -- Manifest
  manifest_path TEXT,

  -- Load status
  load_status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- 'pending', 'in_progress', 'success', 'failed', 'skipped'
  load_started_at TIMESTAMP,
  load_completed_at TIMESTAMP,
  rows_loaded BIGINT,
  sources_loaded INTEGER,

  -- Errors
  error_message TEXT,
  error_detail JSONB,
  retry_count INTEGER DEFAULT 0,

  UNIQUE(publication_id, period)
);

CREATE INDEX idx_period_pub ON datawarp.tbl_publication_periods(publication_id);
CREATE INDEX idx_period_status ON datawarp.tbl_publication_periods(load_status);

-- URL discovery log
CREATE TABLE datawarp.tbl_url_discovery (
  id SERIAL PRIMARY KEY,
  publication_id VARCHAR(50),
  period VARCHAR(20),

  attempted_url TEXT NOT NULL,
  discovery_method VARCHAR(50) NOT NULL,  -- 'regex_pattern', 'scrape', 'manual', 'prediction'

  -- Result
  success BOOLEAN NOT NULL,
  http_status INTEGER,
  response_time_ms INTEGER,

  discovered_at TIMESTAMP DEFAULT NOW(),
  error_detail TEXT
);

CREATE INDEX idx_discovery_pub ON datawarp.tbl_url_discovery(publication_id);
CREATE INDEX idx_discovery_success ON datawarp.tbl_url_discovery(success);
```

### Seed Data (10 Core Publications)

```sql
-- Initial publication registry
INSERT INTO datawarp.tbl_publications (
  publication_id,
  publication_name,
  base_url_pattern,
  frequency,
  expected_delay_days,
  expected_sources_count
) VALUES
  ('gp_appointments', 'GP Appointments', 'https://digital.nhs.uk/data-and-information/publications/statistical/appointments-in-general-practice/{period}', 'monthly', 14, 4),
  ('gp_registration', 'Patients Registered at a GP Practice', 'https://digital.nhs.uk/data-and-information/publications/statistical/patients-registered-at-a-gp-practice/{period}', 'monthly', 21, 6),
  ('ae_attendances', 'A&E Attendances and Emergency Admissions', 'https://digital.nhs.uk/data-and-information/publications/statistical/monthly-accident-and-emergency-attendances-and-emergency-admissions/{period}', 'monthly', 21, 5),
  ('msds', 'Maternity Services Monthly Statistics', 'https://digital.nhs.uk/data-and-information/publications/statistical/maternity-services-monthly-statistics/{period}', 'monthly', 21, 3),
  ('cancer_waiting_times', 'Cancer Waiting Times', 'https://digital.nhs.uk/data-and-information/publications/statistical/cancer-waiting-times/{period}', 'monthly', 28, 8),
  ('adhd', 'ADHD Management Information', 'https://digital.nhs.uk/data-and-information/publications/statistical/mi-adhd/{period}', 'monthly', 14, 20)
  -- Add 4 more publications
;
```

## Code Modules

### Module 3: URL Discovery

**File:** `src/datawarp/scheduler/__init__.py` (new package)

**File:** `src/datawarp/scheduler/url_discovery.py` (~150 lines)

```python
"""
URL discovery strategies for NHS publications.
"""
import re
import requests
from typing import Optional, List, Tuple
from bs4 import BeautifulSoup

class URLDiscovery:
    """Discovers URLs for NHS publications."""

    def __init__(self, publication_id: str, base_pattern: str):
        self.publication_id = publication_id
        self.base_pattern = base_pattern

    def discover_url(self, period: str) -> Optional[Tuple[str, str]]:
        """
        Try multiple strategies to find URL for a period.

        Returns: (url, method) or None
        """
        # Strategy 1: Pattern substitution
        url = self._try_pattern(period)
        if url and self._check_url(url):
            return (url, 'regex_pattern')

        # Strategy 2: Scrape landing page
        url = self._try_scrape(period)
        if url:
            return (url, 'scrape')

        # Strategy 3: Predictive variations
        url = self._try_variations(period)
        if url:
            return (url, 'prediction')

        return None

    def _try_pattern(self, period: str) -> Optional[str]:
        """Try pattern substitution."""
        patterns = self._generate_period_patterns(period)
        for pattern_value in patterns:
            url = self.base_pattern.replace('{period}', pattern_value)
            return url  # Return first attempt
        return None

    def _try_scrape(self, period: str) -> Optional[str]:
        """Scrape publication landing page for links."""
        base = self.base_pattern.split('{period}')[0].rstrip('/')

        try:
            resp = requests.get(base, timeout=10)
            soup = BeautifulSoup(resp.content, 'html.parser')

            for link in soup.find_all('a', href=True):
                href = link['href']
                if self._matches_period(href, period):
                    return href if href.startswith('http') else f"{base}{href}"
        except:
            pass

        return None

    def _try_variations(self, period: str) -> Optional[str]:
        """Try common URL pattern variations."""
        variations = [
            period.replace('-', '_'),  # 2025-04 → 2025_04
            period.replace('-', ''),   # 2025-04 → 202504
        ]

        for var in variations:
            url = self.base_pattern.replace('{period}', var)
            if self._check_url(url):
                return url

        return None

    def _check_url(self, url: str) -> bool:
        """Check if URL exists (HEAD request)."""
        try:
            resp = requests.head(url, timeout=5, allow_redirects=True)
            return resp.status_code == 200
        except:
            return False

    def _generate_period_patterns(self, period: str) -> List[str]:
        """Generate common date format variations."""
        year, month = period.split('-')
        month_num = int(month)

        month_names = [
            'january', 'february', 'march', 'april', 'may', 'june',
            'july', 'august', 'september', 'october', 'november', 'december'
        ]
        month_abbr = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                      'jul', 'aug', 'sep', 'oct', 'nov', 'dec']

        month_name = month_names[month_num - 1]
        month_short = month_abbr[month_num - 1]

        return [
            f"{month_name}-{year}",           # april-2025
            f"{month_short}-{year}",          # apr-2025
            f"{year}-{month}",                # 2025-04
            f"{month_name}_{year}",           # april_2025
            f"{year}_{month}",                # 2025_04
            f"{month_name.capitalize()}-{year}",  # April-2025
        ]

    def _matches_period(self, text: str, period: str) -> bool:
        """Check if text contains period reference."""
        patterns = self._generate_period_patterns(period)
        text_lower = text.lower()
        return any(p in text_lower for p in patterns)
```

### Module 4: Backfill Workflow

**File:** `src/datawarp/scheduler/backfill.py` (~100 lines)

```python
"""
Historical data backfill workflow.
"""
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import List

def generate_periods(
    start_date: str,
    end_date: str,
    frequency: str = 'monthly'
) -> List[str]:
    """
    Generate list of periods to backfill.

    Examples:
        start='2022-01', end='2025-12', frequency='monthly'
        → ['2022-01', '2022-02', ..., '2025-12']
    """
    start = datetime.strptime(start_date, '%Y-%m')
    end = datetime.strptime(end_date, '%Y-%m')

    periods = []
    current = start

    while current <= end:
        periods.append(current.strftime('%Y-%m'))
        if frequency == 'monthly':
            current += relativedelta(months=1)
        elif frequency == 'quarterly':
            current += relativedelta(months=3)
        elif frequency == 'annual':
            current += relativedelta(years=1)

    return periods

def backfill_publication(
    publication_id: str,
    start_period: str,
    end_period: str,
    dry_run: bool = True
):
    """
    Backfill historical data for a publication.

    Workflow:
    1. Generate period list
    2. Discover URLs
    3. Generate manifests
    4. Enrich
    5. Apply enrichment
    6. Load
    """
    from .url_discovery import URLDiscovery
    from ..storage.connection import get_connection

    conn = get_connection()

    # Load publication config
    with conn.cursor() as cur:
        cur.execute("""
            SELECT publication_name, base_url_pattern, frequency
            FROM datawarp.tbl_publications
            WHERE publication_id = %s
        """, (publication_id,))
        pub = cur.fetchone()

    if not pub:
        raise ValueError(f"Publication {publication_id} not found")

    # Generate periods
    periods = generate_periods(start_period, end_period, pub['frequency'])
    print(f"Backfilling {len(periods)} periods for {pub['publication_name']}")

    discovery = URLDiscovery(publication_id, pub['base_url_pattern'])

    for period in periods:
        print(f"\nProcessing {period}...")

        # Discover URL
        result = discovery.discover_url(period)
        if not result:
            print(f"  ❌ URL not found")
            continue

        url, method = result
        print(f"  ✓ Found URL via {method}: {url}")

        if dry_run:
            continue

        # TODO: Implement full workflow
        # - Generate manifest
        # - Enrich
        # - Apply enrichment
        # - Load

    conn.close()
```

### CLI Command

**File:** `src/datawarp/cli/commands.py` (add to existing)

```python
@app.command()
def backfill(
    publication_id: str = typer.Argument(..., help="Publication ID"),
    start_period: str = typer.Option(..., help="Start period (YYYY-MM)"),
    end_period: str = typer.Option(None, help="End period (YYYY-MM, default: current)"),
    dry_run: bool = typer.Option(True, help="Preview without loading")
):
    """Backfill historical data for a publication."""
    from datawarp.scheduler.backfill import backfill_publication

    if not end_period:
        from datetime import datetime
        end_period = datetime.now().strftime('%Y-%m')

    backfill_publication(publication_id, start_period, end_period, dry_run)
```

## Success Criteria (Phase 2)

- [ ] 10 publications registered
- [ ] URL discovery succeeds for 80%+ of attempts
- [ ] Backfill workflow completes for GP Appointments (2023-2025)
- [ ] Period tracking table populated
- [ ] Email alerts sent on failures

---

# Phase 3: Date Column Pivoting (Smart Detection)

## Objectives

1. Detect wide date columns without hardcoded patterns
2. Optionally use LLM to flag pivoting needs
3. Pivot to long format during insert
4. Track transformations in metadata

## Key Insight: Use Standard Libraries, Not Regex Hell

**OLD APPROACH (REJECTED):**
```python
# Pattern maintenance nightmare
date_patterns = [
    r'^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)_\d{4}$',  # 50 patterns
    r'^(january|february|...|december)_\d{4}$',
    r'^\d{4}_(jan|feb|mar|...|dec)$',
    r'^q[1-4]_\d{4}$',
    # ... breaks with: "Q1FY2024", "2024/25", "Autumn_2025"
]

exclusion_patterns = [
    r'^age_\d+_to_\d+',      # 20 exclusions
    r'^age_\d+_plus',
    r'^gender\d+_',
    # ... what about "waiting_time_up_to_13_weeks"?
]
```

**NEW APPROACH 1: Smart Date Parsing (Deterministic)**
```python
from dateutil import parser as date_parser

def detect_wide_dates_smart(columns: List[str]) -> Optional[WideDateInfo]:
    """Detect wide dates using actual date parsing, not patterns."""

    # Try to parse dates from column names
    parsed_columns = []
    for col in columns:
        tokens = re.split(r'[_\s-]', col.lower())

        for token in tokens:
            try:
                # dateutil handles: "apr", "2025", "apr_2025", "q1", etc.
                parsed_date = date_parser.parse(token, fuzzy=False)
                parsed_columns.append({
                    'column': col,
                    'date': parsed_date,
                    'token': token
                })
                break
            except (ValueError, TypeError):
                continue

    # Need 3+ columns with dates
    if len(parsed_columns) < 3:
        return None

    # Check if dates form a sequence (monthly, quarterly, yearly)
    dates = sorted([pc['date'] for pc in parsed_columns])
    intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
    avg_interval = sum(intervals) / len(intervals)

    if 25 <= avg_interval <= 35:  # Monthly
        return WideDateInfo(columns=parsed_columns, period_type='monthly')
    elif 85 <= avg_interval <= 95:  # Quarterly
        return WideDateInfo(columns=parsed_columns, period_type='quarterly')
    elif 360 <= avg_interval <= 370:  # Yearly
        return WideDateInfo(columns=parsed_columns, period_type='yearly')

    return None  # Not a regular sequence
```

**NEW APPROACH 2: LLM Enhancement (Smart)**

Add to enrichment prompt:
```python
ENRICHMENT_PROMPT_ADDITION = """
WIDE DATE DETECTION:

If you detect that multiple columns represent the same measure across different time periods
(e.g., "Apr_2025", "May_2025", "Jun_2025" all containing patient counts), add this flag:

"requires_pivoting": true
"pivot_config": {
    "date_columns": ["Apr_2025", "May_2025", "Jun_2025"],
    "measure_name": "patient_count",
    "period_type": "monthly"
}

IMPORTANT: Do NOT flag age brackets (e.g., "Age 0 to 4", "Age 5 to 17") as dates.
"""
```

## Code Modules

### Module 5: Smart Wide Date Detection

**File:** `src/datawarp/transforms/__init__.py` (new package)

**File:** `src/datawarp/transforms/wide_date_detector.py` (~100 lines)

```python
"""
Smart wide date column detection using dateutil.parser.
No hardcoded patterns - handles any date format automatically.
"""
from dateutil import parser as date_parser
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class WideDateInfo:
    """Information about detected wide date columns."""
    date_columns: List[str]
    period_type: str  # 'monthly', 'quarterly', 'yearly'
    base_measure: str

def detect_wide_dates(columns: List[str]) -> Optional[WideDateInfo]:
    """
    Detect wide date format using smart date parsing.

    No patterns needed - dateutil.parser handles everything:
    - Month names (Jan, January, apr)
    - Years (2025, 25)
    - Quarters (Q1, q1)
    - Any combination

    Returns WideDateInfo if detected, None otherwise.
    """
    parsed_columns = []

    for col in columns:
        # Split column name into tokens
        tokens = col.replace('_', ' ').replace('-', ' ').split()

        # Try to parse each token as a date
        for token in tokens:
            try:
                parsed_date = date_parser.parse(token, fuzzy=False)
                parsed_columns.append({
                    'column': col,
                    'date': parsed_date,
                    'token': token
                })
                break  # Found a date in this column
            except (ValueError, TypeError, OverflowError):
                continue

    # Need at least 3 date columns to consider it wide format
    if len(parsed_columns) < 3:
        return None

    # Check if dates form a regular sequence
    dates = sorted([pc['date'] for pc in parsed_columns])
    intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]

    if not intervals:
        return None

    avg_interval = sum(intervals) / len(intervals)

    # Determine period type based on average interval
    if 25 <= avg_interval <= 35:
        period_type = 'monthly'
    elif 85 <= avg_interval <= 95:
        period_type = 'quarterly'
    elif 360 <= avg_interval <= 370:
        period_type = 'yearly'
    else:
        return None  # Not a regular sequence

    # Extract base measure name (remove date tokens)
    base_names = []
    for pc in parsed_columns:
        base = pc['column']
        # Remove the date token
        base = base.replace(pc['token'], '').strip('_- ')
        base_names.append(base)

    # All base names should be similar (or empty)
    unique_bases = set(base_names)
    if len(unique_bases) > 1:
        # Different base names - might not be wide format
        return None

    base_measure = base_names[0] if base_names[0] else 'value'

    return WideDateInfo(
        date_columns=[pc['column'] for pc in parsed_columns],
        period_type=period_type,
        base_measure=base_measure
    )
```

### Module 6: Pivot Transformation

**File:** `src/datawarp/transforms/pivot.py` (~150 lines)

```python
"""
Wide-to-long format pivoting using pandas.
"""
import pandas as pd
from typing import List
from .wide_date_detector import WideDateInfo
from dateutil import parser as date_parser

def pivot_dataframe(
    df: pd.DataFrame,
    wide_date_info: WideDateInfo,
    id_columns: List[str]
) -> pd.DataFrame:
    """
    Pivot wide format to long format.

    Args:
        df: Wide format DataFrame
        wide_date_info: Detected date column info
        id_columns: Identifier columns (non-date columns)

    Returns:
        Long format DataFrame with 'period' and measure columns
    """
    # Create period mapping (column name → parsed date)
    period_map = {}
    for col in wide_date_info.date_columns:
        tokens = col.replace('_', ' ').replace('-', ' ').split()
        for token in tokens:
            try:
                parsed_date = date_parser.parse(token, fuzzy=False)
                # Format as YYYY-MM or YYYY-QQ
                if wide_date_info.period_type == 'monthly':
                    period_map[col] = parsed_date.strftime('%Y-%m')
                elif wide_date_info.period_type == 'quarterly':
                    quarter = (parsed_date.month - 1) // 3 + 1
                    period_map[col] = f"{parsed_date.year}-Q{quarter}"
                elif wide_date_info.period_type == 'yearly':
                    period_map[col] = str(parsed_date.year)
                break
            except:
                continue

    # Melt DataFrame
    df_long = df.melt(
        id_vars=id_columns,
        value_vars=wide_date_info.date_columns,
        var_name='_temp_period',
        value_name=wide_date_info.base_measure
    )

    # Map column names to periods
    df_long['period'] = df_long['_temp_period'].map(period_map)
    df_long = df_long.drop(columns=['_temp_period'])

    # Sort by id columns and period
    df_long = df_long.sort_values(id_columns + ['period'])

    return df_long
```

### Integration with Insert Pipeline

**File:** `src/datawarp/loader/insert.py` (modify existing)

```python
# Add to insert_dataframe function

from datawarp.transforms.wide_date_detector import detect_wide_dates
from datawarp.transforms.pivot import pivot_dataframe

def insert_dataframe(
    conn,
    df: pd.DataFrame,
    table_name: str,
    columns: List[ColumnInfo],
    mode: str = "replace",
    source_metadata: Dict = None
) -> int:
    """Insert DataFrame with optional pivoting."""

    # Check if LLM flagged this for pivoting
    requires_pivoting = False
    if source_metadata:
        requires_pivoting = source_metadata.get('requires_pivoting', False)

    # Or detect automatically
    if not requires_pivoting:
        col_names = [c.pg_name for c in columns]
        wide_date_info = detect_wide_dates(col_names)

        if wide_date_info:
            logging.info(f"Auto-detected wide date format: {len(wide_date_info.date_columns)} columns")
            requires_pivoting = True

    # Pivot if needed
    if requires_pivoting and wide_date_info:
        logging.info(f"Pivoting to long format ({wide_date_info.period_type})...")

        # Identify non-date columns as IDs
        date_col_set = set(wide_date_info.date_columns)
        id_columns = [c.pg_name for c in columns if c.pg_name not in date_col_set]

        # Pivot
        df = pivot_dataframe(df, wide_date_info, id_columns)

        # Log drift event
        _log_drift_event(
            canonical_code=table_name.replace('tbl_', ''),
            drift_type='wide_date_detected',
            severity='info',
            details={
                'date_columns': wide_date_info.date_columns,
                'period_type': wide_date_info.period_type,
                'base_measure': wide_date_info.base_measure,
                'transformation': 'pivot_to_long'
            }
        )

    # Continue with existing insert logic
    # ...
```

## Testing Strategy

### Test 1: Smart Detection

```python
from src.datawarp.transforms.wide_date_detector import detect_wide_dates

# Test with various formats - no patterns needed!
columns1 = ['Provider', 'Apr_2025', 'May_2025', 'Jun_2025']
columns2 = ['Provider', '2025_04', '2025_05', '2025_06']
columns3 = ['Provider', 'Q1_2025', 'Q2_2025', 'Q3_2025']
columns4 = ['Provider', 'Age 0 to 4', 'Age 5 to 17']  # Should NOT detect

assert detect_wide_dates(columns1) is not None  # ✓
assert detect_wide_dates(columns2) is not None  # ✓
assert detect_wide_dates(columns3) is not None  # ✓
assert detect_wide_dates(columns4) is None      # ✓ No false positive!
```

### Test 2: Pivot Accuracy

```python
import pandas as pd

df_wide = pd.DataFrame({
    'Provider': ['Trust A', 'Trust B'],
    'Apr_2025': [1500, 2300],
    'May_2025': [1600, 2400]
})

info = detect_wide_dates(['Provider', 'Apr_2025', 'May_2025'])
df_long = pivot_dataframe(df_wide, info, ['Provider'])

assert len(df_long) == 4  # 2 providers × 2 months
assert list(df_long.columns) == ['Provider', 'value', 'period']
assert '2025-04' in df_long['period'].values
```

## Success Criteria (Phase 3)

- [ ] Smart detection works for ANY date format (no patterns to maintain)
- [ ] Age brackets and other non-dates correctly excluded
- [ ] LLM enrichment includes `requires_pivoting` flag
- [ ] Pivot transformation preserves all data
- [ ] Drift events logged

---

# Implementation Schedule

## Week 1: Phase 1 Core

- [ ] Database schema (04_create_registry_tables.sql)
- [ ] Fingerprinting module (80 lines)
- [ ] Enrichment applier script (50 lines)
- [ ] Unit tests

## Week 2: Phase 1 Integration

- [ ] Test with ADHD + MSDS data
- [ ] Verify cross-period consolidation
- [ ] Refinements based on testing
- [ ] Documentation

**CHECKPOINT:** User approval before Phase 2

## Week 3: Phase 2 Core

- [ ] Database schema (05_create_publication_tracking.sql)
- [ ] URL discovery module
- [ ] Backfill workflow
- [ ] CLI commands

## Week 4: Phase 2 Deployment

- [ ] Seed 10 publications
- [ ] Run backfill for GP Appointments (2023-2025)
- [ ] Test URL discovery
- [ ] Email alerts

**CHECKPOINT:** User approval before Phase 3

## Week 5: Phase 3 Implementation

- [ ] Smart wide date detection (dateutil-based)
- [ ] Update enrichment prompts
- [ ] Pivot transformation
- [ ] Integration with insert pipeline

## Week 6: Stabilization

- [ ] User acceptance testing
- [ ] Bug fixes
- [ ] Performance optimization
- [ ] Final documentation

---

# Comparison: Old vs New Approach

| Component | Old Approach | New Approach | Lines Saved |
|-----------|-------------|--------------|-------------|
| Canonicalization | Pattern-based module (150 lines) | Use LLM enrichment (0 lines) | 150 |
| Enrichment Integration | Not implemented | apply_enrichment.py (50 lines) | -50 |
| Wide Date Detection | Regex patterns + exclusions (200 lines) | dateutil.parser (100 lines) | 100 |
| **TOTAL** | **350 lines** | **150 lines** | **200 lines (57% reduction)** |

## Maintenance Burden

**Old:**
- Update patterns for new date formats
- Add exclusions for false positives
- Handle edge cases manually
- Break with: "Q1FY2024", "2024/25", "Autumn_2025"

**New:**
- dateutil.parser handles all date formats automatically
- LLM learns from context
- No pattern lists to maintain
- Adapts to new formats

---

# Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Fingerprinting false positives | Medium | High | Manual review queue for low-confidence matches |
| URL patterns change mid-year | High | Medium | Fallback to scraping, manual override |
| dateutil.parser false positives | Low | Medium | Sequence validation (3+ columns, regular intervals) |
| LLM enrichment inconsistency | Medium | Medium | Use enrichment for semantic understanding, fingerprinting for structural matching |
| Backfill time (50+ months) | High | Low | Run overnight, pause/resume capability |

---

# Success Metrics

## Phase 1
- 90%+ sources enriched correctly
- Zero duplicate tables for same source
- apply_enrichment.py works with all test manifests

## Phase 2
- 10 publications tracked
- 80%+ URL discovery success
- 36 months backfilled per publication

## Phase 3
- Wide date detection works for any date format
- Zero false positives on age brackets
- Zero data loss in pivoting

## Overall
- 10 feeds running automatically
- <10% manual intervention rate
- Email alerts working
- Maintenance burden minimized (no pattern lists)

---

# Next Steps

1. **Review this plan** - provide feedback, questions, concerns
2. **Approve Phase 1** - green light to implement enrichment integration
3. **Test with ADHD data** - verify apply_enrichment.py works
4. **Schedule kickoff** - plan implementation timeline

---

**End of Implementation Plan**
