#!/usr/bin/env python3
"""
Simulation: Period Discovery System

Simulates how schedule-based period discovery would work for different sources.
Identifies edge cases before implementation.
"""

from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Optional, Tuple
import calendar

TODAY = date(2026, 1, 17)  # Simulation date

# Month name mapping
MONTH_NAMES = {
    1: 'january', 2: 'february', 3: 'march', 4: 'april',
    5: 'may', 6: 'june', 7: 'july', 8: 'august',
    9: 'september', 10: 'october', 11: 'november', 12: 'december'
}


def parse_period(period: str) -> Tuple[int, int]:
    """Parse YYYY-MM to (year, month)."""
    parts = period.split('-')
    return int(parts[0]), int(parts[1])


def generate_schedule_periods(
    start: str,
    end: str,  # "current" or "YYYY-MM"
    months: Optional[List[int]] = None,  # None = all months
    frequency: str = "monthly"
) -> List[str]:
    """Generate periods based on schedule configuration."""

    start_year, start_month = parse_period(start)
    start_date = date(start_year, start_month, 1)

    if end == "current":
        end_date = TODAY
    else:
        end_year, end_month = parse_period(end)
        end_date = date(end_year, end_month, 1)

    periods = []
    current = start_date

    while current <= end_date:
        # Check if this month is in the allowed list
        if months is None or current.month in months:
            periods.append(f"{current.year}-{current.month:02d}")

        # Move to next month
        current = current + relativedelta(months=1)

    return periods


def simulate_url_fetch(period: str, url_pattern: str, landing_page: str) -> Dict:
    """Simulate fetching a URL - would it work?"""

    year, month = parse_period(period)
    month_name = MONTH_NAMES[month]

    # Generate URL
    url = url_pattern.replace("{landing_page}", landing_page)
    url = url.replace("{month_name}", month_name)
    url = url.replace("{year}", str(year))

    # Simulate: Is this period likely published yet?
    # NHS typically publishes ~3-6 weeks after period end
    period_end = date(year, month, calendar.monthrange(year, month)[1])
    expected_publish = period_end + relativedelta(weeks=4)

    if expected_publish > TODAY:
        return {
            "period": period,
            "url": url,
            "status": "NOT_YET_PUBLISHED",
            "expected": expected_publish.isoformat(),
            "note": f"Data for {month_name.title()} {year} likely not published until ~{expected_publish}"
        }
    else:
        return {
            "period": period,
            "url": url,
            "status": "LIKELY_AVAILABLE",
            "note": None
        }


def simulate_source(name: str, config: Dict) -> Dict:
    """Simulate period discovery for a source."""

    print(f"\n{'='*70}")
    print(f"SIMULATING: {name}")
    print(f"{'='*70}")

    # Generate periods
    periods = generate_schedule_periods(
        start=config["start"],
        end=config["end"],
        months=config.get("months"),
        frequency=config.get("frequency", "monthly")
    )

    print(f"\nSchedule Config:")
    print(f"  start: {config['start']}")
    print(f"  end: {config['end']}")
    print(f"  months: {config.get('months', 'all')}")
    print(f"  frequency: {config.get('frequency', 'monthly')}")

    print(f"\nGenerated {len(periods)} periods:")
    print(f"  First: {periods[0] if periods else 'none'}")
    print(f"  Last:  {periods[-1] if periods else 'none'}")

    # Simulate URL fetches
    results = []
    not_published = []

    for period in periods:
        result = simulate_url_fetch(
            period,
            config["url_pattern"],
            config["landing_page"]
        )
        results.append(result)
        if result["status"] == "NOT_YET_PUBLISHED":
            not_published.append(result)

    print(f"\nURL Simulation:")
    print(f"  Likely available: {len(periods) - len(not_published)}")
    print(f"  Not yet published: {len(not_published)}")

    if not_published:
        print(f"\n  ⚠️  Periods not yet published:")
        for r in not_published[:3]:
            print(f"      {r['period']}: expected ~{r['expected']}")

    return {
        "name": name,
        "periods": periods,
        "available": len(periods) - len(not_published),
        "not_published": not_published
    }


# ============================================================================
# SIMULATION SCENARIOS
# ============================================================================

SCENARIOS = {
    # Scenario 1: Quarterly NHS Digital (ADHD)
    "adhd": {
        "start": "2024-05",
        "end": "current",
        "months": [5, 8, 11],  # May, Aug, Nov only
        "frequency": "quarterly",
        "url_pattern": "{landing_page}/{month_name}-{year}",
        "landing_page": "https://digital.nhs.uk/data-and-information/publications/statistical/mi-adhd"
    },

    # Scenario 2: Monthly NHS Digital (GP Appointments)
    "gp_appointments": {
        "start": "2024-01",
        "end": "current",
        "months": None,  # All months
        "frequency": "monthly",
        "url_pattern": "{landing_page}/{month_name}-{year}",
        "landing_page": "https://digital.nhs.uk/data-and-information/publications/statistical/appointments-in-general-practice"
    },

    # Scenario 3: Quarterly with irregular start (Online Consultation)
    "gp_online_consultation": {
        "start": "2025-03",  # Started March 2025
        "end": "current",
        "months": None,
        "frequency": "monthly",
        "url_pattern": "{landing_page}/{month_name}-{year}",
        "landing_page": "https://digital.nhs.uk/data-and-information/publications/statistical/submissions-via-online-consultation-systems-in-general-practice"
    },

    # Scenario 4: Source with known gaps (Out of Area MH - only has 3 months)
    "out_of_area_mental_health": {
        "start": "2024-01",
        "end": "current",
        "months": None,
        "frequency": "monthly",
        "url_pattern": "{landing_page}/{month_name}-{year}",
        "landing_page": "https://digital.nhs.uk/data-and-information/publications/statistical/out-of-area-placements-in-mental-health-services"
    },
}


def main():
    print("=" * 70)
    print("PERIOD DISCOVERY SIMULATION")
    print(f"Simulation Date: {TODAY}")
    print("=" * 70)

    all_results = []
    edge_cases = []

    for name, config in SCENARIOS.items():
        result = simulate_source(name, config)
        all_results.append(result)

        # Identify edge cases
        if result["not_published"]:
            edge_cases.append({
                "source": name,
                "issue": "FUTURE_PERIODS",
                "detail": f"{len(result['not_published'])} periods generated that aren't published yet"
            })

    # Summary
    print("\n" + "=" * 70)
    print("EDGE CASES IDENTIFIED")
    print("=" * 70)

    # Edge Case 1: Future periods
    print("\n1. FUTURE PERIODS (schedule generates unpublished data)")
    print("   Problem: Schedule generates periods for data not yet published")
    print("   Example: Today is Jan 17, but we generate Dec 2025, Jan 2026")
    print("   Solution: Apply 'publication_lag' offset (e.g., -6 weeks)")

    # Edge Case 2: 404 handling
    print("\n2. MISSING PERIODS (source has gaps)")
    print("   Problem: out_of_area_mental_health only has Jan-Mar 2024, but schedule generates all months")
    print("   Example: Schedule generates Apr 2024, but NHS never published it")
    print("   Solution: Graceful 404 handling, mark as 'not_available' not 'failed'")

    # Edge Case 3: SHMI offset
    print("\n3. PUBLICATION LAG (SHMI-style sources)")
    print("   Problem: SHMI data for Aug 2025 is published Jan 2026")
    print("   Example: period='2025-08' but url='/shmi/2026-01'")
    print("   Solution: Add 'publication_offset' config (+5 months for SHMI)")

    # Edge Case 4: Fiscal quarters
    print("\n4. FISCAL QUARTERS (Bed Occupancy, Cancelled Ops)")
    print("   Problem: Periods like FY25-Q1, FY25-Q2 don't fit YYYY-MM pattern")
    print("   Example: FY25-Q1 = Apr-Jun 2024, but schedule uses calendar months")
    print("   Solution: Add 'period_type: fiscal_quarter' with separate generator")

    # Edge Case 5: Revised data
    print("\n5. REVISED DATA (NHS updates published files)")
    print("   Problem: NHS publishes 'October-2025.xls' then 'October-2025-revised.xls'")
    print("   Example: We process original, miss the revision")
    print("   Solution: Track 'last_checked' timestamp, re-check periodically")

    # Edge Case 6: URL template exceptions
    print("\n6. URL TEMPLATE EXCEPTIONS (inconsistent patterns)")
    print("   Problem: LDHC uses '/january-2024' but '/england-february-2024'")
    print("   Problem: PCN Workforce uses '/31-march-2025' (day varies)")
    print("   Solution: Allow 'url_exceptions' list for specific periods")

    # Edge Case 7: Multiple files per period
    print("\n7. MULTIPLE FILES PER PERIOD (A&E has monthly + quarterly)")
    print("   Problem: Same period has multiple file types")
    print("   Example: Oct 2025 has both monthly data file and quarterly summary")
    print("   Solution: Support 'file_types' list in config")

    print("\n" + "=" * 70)
    print("RECOMMENDED DESIGN ADDITIONS")
    print("=" * 70)

    print("""
    periods:
      mode: schedule
      start: "2024-05"
      end: current
      months: [5, 8, 11]

      # NEW: Handle edge cases
      publication_lag_weeks: 6      # Don't generate periods < 6 weeks old
      publication_offset_months: 0  # SHMI uses +5
      period_type: monthly          # or: fiscal_quarter

      # NEW: Known exceptions
      skip_periods: ["2024-04"]     # Known gaps (404s)

    url:
      mode: template
      pattern: "{landing_page}/{month_name}-{year}"

      # NEW: Pattern exceptions
      exceptions:
        "2024-01": "{landing_page}/january-2024"  # No 'england-' prefix

    # NEW: Revision tracking
    check_revisions: true
    revision_check_days: 30         # Re-check for revisions after 30 days
    """)


if __name__ == "__main__":
    main()
