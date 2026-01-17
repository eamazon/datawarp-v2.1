#!/usr/bin/env python3
"""
Deep Simulation: Edge Cases and State Management

Simulates complex scenarios to validate design before implementation.
"""

from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Optional, Tuple
import json

TODAY = date(2026, 1, 17)

print("=" * 70)
print("EDGE CASE DEEP DIVE")
print(f"Simulation Date: {TODAY}")
print("=" * 70)


# ============================================================================
# EDGE CASE 1: Fiscal Quarters
# ============================================================================
print("\n" + "=" * 70)
print("EDGE CASE 1: FISCAL QUARTERS")
print("=" * 70)

def generate_fiscal_quarters(start_fy: int, end: str = "current") -> List[str]:
    """Generate fiscal quarter periods.

    NHS Fiscal Year: April to March
    FY25 = April 2024 - March 2025
    FY25-Q1 = Apr-Jun 2024
    FY25-Q2 = Jul-Sep 2024
    FY25-Q3 = Oct-Dec 2024
    FY25-Q4 = Jan-Mar 2025
    """
    quarters = []

    # Map FY to calendar dates
    # FY25-Q1 starts April 2024
    current_fy = start_fy
    current_q = 1

    while True:
        period = f"FY{current_fy % 100:02d}-Q{current_q}"

        # Calculate quarter end date
        if current_q == 1:
            q_end = date(current_fy - 1, 6, 30)  # Jun of previous calendar year
        elif current_q == 2:
            q_end = date(current_fy - 1, 9, 30)  # Sep
        elif current_q == 3:
            q_end = date(current_fy - 1, 12, 31)  # Dec
        else:  # Q4
            q_end = date(current_fy, 3, 31)  # Mar of FY year

        # Publication lag (~6 weeks after quarter end)
        expected_publish = q_end + relativedelta(weeks=6)

        if end == "current" and expected_publish > TODAY:
            break

        quarters.append({
            "period": period,
            "quarter_end": q_end.isoformat(),
            "expected_publish": expected_publish.isoformat(),
            "available": expected_publish <= TODAY
        })

        # Next quarter
        current_q += 1
        if current_q > 4:
            current_q = 1
            current_fy += 1

        # Safety limit
        if len(quarters) > 20:
            break

    return quarters


print("\nBed Occupancy (Quarterly, Fiscal):")
print("  Config: start_fy=2025, end=current")
quarters = generate_fiscal_quarters(2025, "current")
for q in quarters:
    status = "✓" if q["available"] else "⏳"
    print(f"  {status} {q['period']} (ends {q['quarter_end']}, publish ~{q['expected_publish']})")

print(f"\n  Generated: {len(quarters)} quarters")
print(f"  Available: {sum(1 for q in quarters if q['available'])}")


# ============================================================================
# EDGE CASE 2: SHMI Publication Offset
# ============================================================================
print("\n" + "=" * 70)
print("EDGE CASE 2: SHMI PUBLICATION OFFSET")
print("=" * 70)

def generate_shmi_periods(start: str, end: str = "current") -> List[Dict]:
    """Generate SHMI periods with publication offset.

    SHMI is rolling 12-month data.
    Data ending Aug 2025 → Published Jan 2026 (5 month offset)
    """
    periods = []
    year, month = int(start[:4]), int(start[5:7])
    current = date(year, month, 1)

    while True:
        data_period = f"{current.year}-{current.month:02d}"

        # Publication is ~5 months after data period end
        pub_date = current + relativedelta(months=5)
        pub_period = f"{pub_date.year}-{pub_date.month:02d}"

        # URL uses publication date
        url = f"https://digital.nhs.uk/.../shmi/{pub_period}"

        if end == "current" and pub_date.replace(day=1) > TODAY:
            break

        periods.append({
            "data_period": data_period,
            "publication_period": pub_period,
            "url": url,
            "available": pub_date.replace(day=1) <= TODAY
        })

        current = current + relativedelta(months=1)

        if len(periods) > 24:
            break

    return periods


print("\nSHMI Simulation:")
print("  Config: start='2024-08', publication_offset=5 months")
shmi = generate_shmi_periods("2024-08", "current")
for p in shmi[-5:]:  # Last 5
    status = "✓" if p["available"] else "⏳"
    print(f"  {status} Data: {p['data_period']} → Published: {p['publication_period']}")
    print(f"       URL: {p['url']}")


# ============================================================================
# EDGE CASE 3: State Management Scenarios
# ============================================================================
print("\n" + "=" * 70)
print("EDGE CASE 3: STATE MANAGEMENT")
print("=" * 70)

# Simulated state.json
state = {
    "processed": {
        "adhd/2024-05": {"completed_at": "2026-01-10T10:00:00", "rows_loaded": 5000, "version": 1},
        "adhd/2024-08": {"completed_at": "2026-01-10T10:05:00", "rows_loaded": 5200, "version": 1},
    },
    "failed": {
        "gp_appointments/2024-04": {"failed_at": "2026-01-10T10:10:00", "error": "404 Not Found", "attempts": 3}
    },
    "not_available": {
        "out_of_area_mental_health/2024-04": {"checked_at": "2026-01-10T10:15:00", "reason": "404 - Source discontinued"}
    },
    "pending_revision": {
        "adhd/2024-05": {"original_processed": "2026-01-10T10:00:00", "revision_detected": "2026-01-15T09:00:00"}
    }
}

print("\nProposed State Categories:")
print("""
  1. 'processed'       - Successfully loaded, skip on re-run
  2. 'failed'          - Error during processing, retry with --retry-failed
  3. 'not_available'   - 404/discontinued, don't retry unless --force
  4. 'pending_revision'- Original loaded, revision detected, needs reprocessing

  New fields per entry:
  - version: int       - Increment when revision processed
  - file_hash: str     - Detect if file changed since last load
  - last_checked: date - When we last verified the source
""")

print("\nState Transition Scenarios:")
scenarios = [
    ("Normal success", "Process adhd/2025-11", "→ processed (version=1)"),
    ("404 error", "Process discontinued source", "→ not_available (don't retry)"),
    ("Transient error", "Network timeout", "→ failed (retry later)"),
    ("Revision detected", "File hash changed", "→ pending_revision"),
    ("Force reload", "--force flag", "processed → reprocess → processed (version++)"),
]

for name, action, result in scenarios:
    print(f"  {name}:")
    print(f"    Action: {action}")
    print(f"    Result: {result}")


# ============================================================================
# EDGE CASE 4: URL Template Exceptions
# ============================================================================
print("\n" + "=" * 70)
print("EDGE CASE 4: URL TEMPLATE EXCEPTIONS")
print("=" * 70)

ldhc_config = {
    "url_pattern": "{landing_page}/england-{month_name}-{year}",
    "exceptions": {
        "2024-01": "{landing_page}/january-2024"  # First month had no 'england-' prefix
    }
}

print("\nLDHC URL Generation:")
print(f"  Default pattern: {ldhc_config['url_pattern']}")
print(f"  Exception for 2024-01: {ldhc_config['exceptions']['2024-01']}")
print("\n  Generated URLs:")
print("    2024-01 → .../january-2024 (exception applied)")
print("    2024-02 → .../england-february-2024 (default pattern)")
print("    2024-03 → .../england-march-2024 (default pattern)")

pcn_config = {
    "url_pattern": "{landing_page}/{day}-{month_name}-{year}",
    "day_calculation": "last_day_of_month"  # Special handling
}

print("\nPCN Workforce URL Generation:")
print(f"  Pattern: {pcn_config['url_pattern']}")
print(f"  Day calculation: {pcn_config['day_calculation']}")
print("\n  Generated URLs:")
print("    2025-03 → .../31-march-2025 (31 days in March)")
print("    2025-04 → .../30-april-2025 (30 days in April)")
print("    2025-02 → .../28-february-2025 (28 days in Feb)")


# ============================================================================
# EDGE CASE 5: Graceful 404 Handling
# ============================================================================
print("\n" + "=" * 70)
print("EDGE CASE 5: GRACEFUL 404 HANDLING")
print("=" * 70)

print("""
Problem: Schedule generates all months, but source may have gaps.
Example: out_of_area_mental_health has only Jan-Mar 2024.

Current behavior:
  - Generate 2024-01 through 2026-01 (25 periods)
  - Try each URL
  - 2024-04 returns 404
  - Mark as 'failed' ❌

Proposed behavior:
  - Generate 2024-01 through 2026-01 (25 periods)
  - Try each URL
  - 2024-04 returns 404
  - Check: Is this a known gap? (consecutive 404s after last success)
  - If yes: Mark as 'not_available', stop trying future periods ✓
  - If no: Mark as 'failed', retry later

Detection logic:
  1. Track last successful period per source
  2. If 404 and period > last_success + 3 months:
     → Likely discontinued, mark 'not_available'
  3. If 404 and period <= last_success + 3 months:
     → Might be temporary, mark 'failed' for retry
""")


# ============================================================================
# FINAL DESIGN RECOMMENDATION
# ============================================================================
print("\n" + "=" * 70)
print("FINAL DESIGN RECOMMENDATION")
print("=" * 70)

final_design = """
publications:

  # =========================================================================
  # PATTERN A: Monthly with schedule (NHS Digital standard)
  # =========================================================================
  gp_appointments:
    name: "Appointments in General Practice"
    source: nhs_digital
    frequency: monthly
    landing_page: https://digital.nhs.uk/.../appointments-in-general-practice

    periods:
      mode: schedule
      start: "2024-01"
      end: current
      publication_lag_weeks: 6    # Don't try periods < 6 weeks old

    url:
      mode: template
      pattern: "{landing_page}/{month_name}-{year}"

  # =========================================================================
  # PATTERN B: Quarterly with specific months (ADHD)
  # =========================================================================
  adhd:
    name: "ADHD Management Information"
    source: nhs_digital
    frequency: quarterly
    landing_page: https://digital.nhs.uk/.../mi-adhd

    periods:
      mode: schedule
      start: "2024-05"
      end: current
      months: [5, 8, 11]           # Only May, Aug, Nov
      publication_lag_weeks: 6

    url:
      mode: template
      pattern: "{landing_page}/{month_name}-{year}"

  # =========================================================================
  # PATTERN C: Fiscal quarters (Bed Occupancy)
  # =========================================================================
  bed_overnight:
    name: "Bed Availability - Overnight"
    source: nhs_england
    frequency: quarterly
    landing_page: https://www.england.nhs.uk/.../bed-data-overnight/

    periods:
      mode: schedule
      type: fiscal_quarter         # FYyy-QN format
      start_fy: 2025               # FY2024-25 starts Apr 2024
      end: current
      publication_lag_weeks: 8

    url:
      mode: explicit               # NHS England has hash codes

  # =========================================================================
  # PATTERN D: Publication offset (SHMI)
  # =========================================================================
  shmi:
    name: "Summary Hospital-level Mortality Indicator"
    source: nhs_digital
    frequency: quarterly           # Published quarterly, rolling 12-month data
    landing_page: https://digital.nhs.uk/.../shmi

    periods:
      mode: schedule
      start: "2024-08"
      end: current
      publication_offset_months: 5  # Data Aug → Published Jan (+5)

    url:
      mode: template
      pattern: "{landing_page}/{pub_year}-{pub_month}"  # Uses publication date

  # =========================================================================
  # PATTERN E: Template with exceptions (LDHC)
  # =========================================================================
  ldhc_scheme:
    name: "Learning Disabilities Health Check Scheme"
    source: nhs_digital
    frequency: monthly
    landing_page: https://digital.nhs.uk/.../learning-disabilities-health-check-scheme

    periods:
      mode: schedule
      start: "2024-01"
      end: current
      publication_lag_weeks: 6

    url:
      mode: template
      pattern: "{landing_page}/england-{month_name}-{year}"
      exceptions:
        "2024-01": "{landing_page}/january-2024"  # No 'england-' prefix

  # =========================================================================
  # PATTERN F: Explicit only (NHS England with hash codes)
  # =========================================================================
  ae_waiting_times:
    name: "A&E Waiting Times and Activity"
    source: nhs_england
    frequency: monthly
    landing_page: https://www.england.nhs.uk/.../ae-waiting-times/

    periods:
      mode: manual                 # Can't auto-generate, URLs have hashes

    url:
      mode: explicit
      notes: "URLs contain 5-char hash codes. Requires manual update or scraper."

    urls:
      - period: "2025-12"
        url: https://...December-2025-AE-by-provider-Sa9Xc.xls
"""

print(final_design)

print("\n" + "=" * 70)
print("STATE.JSON STRUCTURE")
print("=" * 70)

state_structure = """
{
  "metadata": {
    "last_run": "2026-01-17T10:00:00",
    "version": "2.0"
  },

  "sources": {
    "adhd": {
      "last_successful_period": "2025-11",
      "status": "active",
      "periods": {
        "2024-05": {
          "status": "processed",
          "completed_at": "2026-01-10T10:00:00",
          "rows_loaded": 5000,
          "version": 1,
          "file_hash": "abc123..."
        },
        "2025-11": {
          "status": "processed",
          "completed_at": "2026-01-17T10:00:00",
          "rows_loaded": 5500,
          "version": 1,
          "file_hash": "def456..."
        }
      }
    },

    "out_of_area_mental_health": {
      "last_successful_period": "2024-03",
      "status": "discontinued",           # Auto-detected from 404 pattern
      "discontinued_after": "2024-03",
      "periods": {
        "2024-01": {"status": "processed", ...},
        "2024-02": {"status": "processed", ...},
        "2024-03": {"status": "processed", ...},
        "2024-04": {"status": "not_available", "reason": "404 - likely discontinued"}
      }
    }
  }
}
"""

print(state_structure)
