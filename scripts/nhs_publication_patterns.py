#!/usr/bin/env python3
"""
NHS Publication Pattern Analysis
=================================

This script documents the different NHS publication structures discovered
across various sources and proposes an agentic solution for handling them.

Author: DataWarp Agent
Date: 2026-01-09
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class PublisherType(Enum):
    """Two distinct NHS data publishers with different page structures"""
    NHS_DIGITAL = "digital.nhs.uk"      # Structured, metadata-rich
    NHS_ENGLAND = "england.nhs.uk"      # Free-form, varied layouts


class PublicationPattern(Enum):
    """Discovered publication patterns"""
    PERIOD_BASED = "period_based"           # One URL per period (GP Practice)
    YEARLY_AGGREGATED = "yearly_aggregated" # All periods on one year page (A&E)
    TIME_SERIES = "time_series"             # Rolling cumulative files (Dementia)
    MIXED = "mixed"                         # Combination of above


@dataclass
class PublicationMetadata:
    """What we can extract from a publication landing page"""
    title: str
    description: str
    geographic_coverage: Optional[str] = None
    publication_frequency: Optional[str] = None  # monthly, quarterly, annual
    data_source: Optional[str] = None
    key_facts: dict = field(default_factory=dict)
    methodology_notes: str = ""
    data_quality_url: Optional[str] = None
    metadata_url: Optional[str] = None  # Field definitions if available
    contact_email: Optional[str] = None


@dataclass 
class ResourceFile:
    """A downloadable file from a publication"""
    filename: str
    url: str
    size: str
    file_type: str  # XLS, CSV, ZIP, PDF
    description: str
    period: Optional[str] = None  # e.g., "November 2025"
    is_timeseries: bool = False
    revision_note: Optional[str] = None


# ============================================================================
# DISCOVERED PATTERNS
# ============================================================================

PUBLICATION_PATTERNS = {
    # -------------------------------------------------------------------------
    # PATTERN 1: NHS DIGITAL - Period-Based (GP Practice, ADHD, PCN Workforce)
    # -------------------------------------------------------------------------
    # URL: digital.nhs.uk/data-and-information/publications/statistical/{pub-name}/{period}
    # 
    # Structure:
    # - One page per publication period (august-2025, september-2025, etc.)
    # - Each page has: Summary, Key Facts, Resources, Related Links
    # - Central /metadata page with field definitions for ALL periods
    # - Central /data-quality-statement page
    # - Files are self-contained per period (ZIP/CSV/XLSX)
    # - File set MAY VARY between periods (quarterly LSOA files)
    #
    # Example: GP Practice Registrations
    #   /patients-registered-at-a-gp-practice/
    #   ├── august-2025/          (7 files - non-quarterly)
    #   ├── july-2025/            (9 files - quarterly, includes LSOA)
    #   ├── metadata/             (central field definitions)
    #   └── data-quality-statement/
    #
    "gp_practice": {
        "publisher": PublisherType.NHS_DIGITAL,
        "pattern": PublicationPattern.PERIOD_BASED,
        "base_url": "https://digital.nhs.uk/data-and-information/publications/statistical/patients-registered-at-a-gp-practice",
        "has_central_metadata": True,
        "has_key_facts": True,
        "file_set_stable": False,  # Quarterly months have extra LSOA files
        "schema_stable": True,     # CSV structure same across periods
        "period_url_pattern": "{base_url}/{month}-{year}",
        "notes": "File count varies: 9 in quarterly months (Jan/Apr/Jul/Oct), 7 otherwise"
    },

    "adhd_referrals": {
        "publisher": PublisherType.NHS_DIGITAL,
        "pattern": PublicationPattern.PERIOD_BASED,
        "base_url": "https://digital.nhs.uk/data-and-information/publications/statistical/mental-health-services-monthly-statistics",
        "has_central_metadata": False,
        "has_key_facts": False,
        "file_set_stable": False,  # New sheets appear in Excel files over time
        "schema_stable": False,    # Column shifts detected (empty col A in Nov)
        "period_url_pattern": "{base_url}/performance-{month}-{year}",
        "notes": "STRUCTURE EVOLVES: Aug had 13 sheets, Nov has 23. Column A shift detected."
    },

    "pcn_workforce": {
        "publisher": PublisherType.NHS_DIGITAL,
        "pattern": PublicationPattern.TIME_SERIES,
        "base_url": "https://digital.nhs.uk/data-and-information/publications/statistical/primary-care-network-workforce",
        "has_central_metadata": False,
        "file_set_stable": True,
        "schema_stable": False,    # Columns grow each month (date columns added)
        "notes": "Date-as-columns pattern: Oct has 50 cols, Nov has 51 (adds new month)"
    },

    # -------------------------------------------------------------------------
    # PATTERN 2: NHS ENGLAND - Yearly Aggregated (A&E Waiting Times)
    # -------------------------------------------------------------------------
    # URL: england.nhs.uk/statistics/statistical-work-areas/{topic}/
    #      england.nhs.uk/statistics/statistical-work-areas/{topic}/{topic}-{year}/
    #
    # Structure:
    # - Landing page has overview, guidance docs, time series files
    # - Yearly pages aggregate all monthly files for that financial year
    # - Files listed chronologically on yearly page (Nov, Oct, Sep, ...)
    # - Multiple file types per month (XLS, CSV, plus ECDS supplementary)
    # - Files may have revision notes ("revised 13.11.25")
    # - Quarterly aggregates bundled with monthly data
    #
    # Example: A&E Attendances
    #   /ae-waiting-times-and-activity/
    #   ├── (overview, guidance, time series files)
    #   ├── ae-attendances-and-emergency-admissions-2025-26/
    #   │   ├── November 2025: [Monthly XLS, CSV, ECDS Activity, ECDS Perf]
    #   │   ├── October 2025: [Monthly XLS, CSV, ECDS files]
    #   │   ├── Q2 2025-26: [Quarterly aggregate]
    #   │   └── ...April 2025
    #   ├── ae-attendances-and-emergency-admissions-2024-25/
    #   └── /data-quality/
    #       /developments/
    #
    "ae_waiting_times": {
        "publisher": PublisherType.NHS_ENGLAND,
        "pattern": PublicationPattern.YEARLY_AGGREGATED,
        "base_url": "https://www.england.nhs.uk/statistics/statistical-work-areas/ae-waiting-times-and-activity",
        "has_central_metadata": False,  # No structured field definitions
        "has_key_facts": False,
        "has_data_quality_page": True,  # /data-quality/
        "has_developments_page": True,  # /developments/
        "file_set_stable": True,        # Same file types each month
        "schema_stable": True,
        "year_url_pattern": "{base_url}/ae-attendances-and-emergency-admissions-{year}/",
        "notes": """
            Multi-file per period: Monthly XLS/CSV + ECDS Activity + ECDS Performance
            Time series files at top level (not per-period)
            Contact: england.aedata@nhs.net
        """
    },

    # -------------------------------------------------------------------------
    # PATTERN 3: NHS DIGITAL - Mixed (Dementia 65+)
    # -------------------------------------------------------------------------
    # Single file that gets updated each month with rolling date columns
    #
    "dementia_65": {
        "publisher": PublisherType.NHS_DIGITAL,
        "pattern": PublicationPattern.TIME_SERIES,
        "base_url": "https://digital.nhs.uk/data-and-information/publications/statistical/recorded-dementia-diagnoses",
        "file_set_stable": True,
        "schema_stable": False,  # Columns roll: [Aug-25, Jul-25] becomes [Sep-25, Aug-25]
        "notes": "Rolling date columns - latest 2 months shown, older months drop off"
    },

    # -------------------------------------------------------------------------
    # PATTERN 4: NHS ENGLAND - Monthly Snapshots (Mixed-Sex Accommodation)
    # -------------------------------------------------------------------------
    # Clean long-format time series - best case scenario
    #
    "msa_breaches": {
        "publisher": PublisherType.NHS_ENGLAND,
        "pattern": PublicationPattern.TIME_SERIES,
        "base_url": "https://www.england.nhs.uk/statistics/statistical-work-areas/mixed-sex-accommodation",
        "file_set_stable": True,
        "schema_stable": True,  # Long format with date column, rows appended
        "notes": "Ideal pattern: Long format, date column, new periods = new rows"
    },
}


# ============================================================================
# AGENTIC SOLUTION ARCHITECTURE
# ============================================================================

"""
PROPOSED AGENTIC APPROACH:
==========================

The agent needs to handle heterogeneous NHS publication structures WITHOUT
relying on LLM for critical path decisions (like schema naming).

THREE-LAYER ARCHITECTURE:

┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 1: PAGE SCRAPER                                                       │
│ - Fetch publication landing page                                            │
│ - Extract: title, description, key facts (if present)                       │
│ - Identify publisher type (digital.nhs.uk vs england.nhs.uk)                │
│ - Discover related pages (metadata, data-quality)                           │
│ - List all downloadable resources with URLs                                 │
│ - Detect publication pattern (period-based, yearly, time-series)            │
│                                                                             │
│ OUTPUT: PublicationContext JSON                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 2: RESOURCE ANALYZER                                                  │
│ - Download sample file(s)                                                   │
│ - Detect file format (Excel sheets, CSV structure)                          │
│ - Extract header rows (handling skip_rows automatically)                    │
│ - Generate DETERMINISTIC column fingerprint                                 │
│ - Compare to known fingerprints (if cross-period)                           │
│ - Detect schema drift (column shifts, new columns, etc.)                    │
│                                                                             │
│ OUTPUT: ResourceSchema JSON (headers, types, fingerprint)                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 3: MANIFEST GENERATOR (LLM-assisted but not LLM-dependent)            │
│ - Generate YAML manifest with deterministic schema names                    │
│ - Use header text → snake_case for column names (NOT LLM)                   │
│ - Call LLM ONLY for enrichment metadata (descriptions, NHS codes)           │
│ - Store LLM outputs in tbl_column_metadata, NOT in DDL                      │
│ - Match to existing canonical if fingerprint known                          │
│                                                                             │
│ OUTPUT: YAML manifest ready for loading                                     │
└─────────────────────────────────────────────────────────────────────────────┘


KEY PRINCIPLE: "LLM for understanding, NOT for schema definition"

The critical fix is:
- Column names in PostgreSQL = deterministic function of Excel header text
- LLM provides human descriptions and NHS code mappings
- Cross-period matching via fingerprint (ordered column hash), not LLM similarity

Example transformation:
  Excel header:     "Age 0 to 4"
  PostgreSQL col:   "age_0_to_4"          ← deterministic: to_schema_name()
  LLM metadata:     {
                      "description": "Count of referrals for ages 0-4",
                      "nhs_code": null,
                      "data_type_hint": "integer"
                    }
"""


# ============================================================================
# IMPLEMENTATION FUNCTIONS (Stubs)
# ============================================================================

def detect_publisher_type(url: str) -> PublisherType:
    """Determine which NHS publisher based on URL domain"""
    if "digital.nhs.uk" in url:
        return PublisherType.NHS_DIGITAL
    elif "england.nhs.uk" in url:
        return PublisherType.NHS_ENGLAND
    else:
        raise ValueError(f"Unknown NHS publisher: {url}")


def to_schema_name(header: str) -> str:
    """
    DETERMINISTIC conversion of Excel header to PostgreSQL column name.
    This is the critical function that removes LLM from the schema path.
    """
    import re
    
    if not header or not header.strip():
        return None
    
    # Lowercase
    name = header.lower().strip()
    
    # Replace special chars with underscore
    name = re.sub(r'[^a-z0-9]+', '_', name)
    
    # Remove leading/trailing underscores
    name = name.strip('_')
    
    # Collapse multiple underscores
    name = re.sub(r'_+', '_', name)
    
    # Ensure doesn't start with digit
    if name and name[0].isdigit():
        name = 'col_' + name
    
    # Truncate if too long (PostgreSQL limit is 63)
    if len(name) > 60:
        name = name[:60]
    
    return name if name else None


def generate_column_fingerprint(headers: list[str]) -> str:
    """
    Generate a deterministic fingerprint from ordered column headers.
    Used for cross-period matching.
    """
    import hashlib
    
    # Normalize headers
    normalized = [to_schema_name(h) for h in headers if h]
    normalized = [n for n in normalized if n]
    
    # Hash the ordered list
    content = "|".join(normalized)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# ============================================================================
# SUMMARY TABLE
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("NHS PUBLICATION PATTERNS ANALYSIS")
    print("=" * 80)
    
    print("\n📊 DISCOVERED PATTERNS:\n")
    
    for pub_id, info in PUBLICATION_PATTERNS.items():
        print(f"  {pub_id}:")
        print(f"    Publisher: {info['publisher'].value}")
        print(f"    Pattern:   {info['pattern'].value}")
        print(f"    Schema Stable: {info.get('schema_stable', 'Unknown')}")
        if info.get('notes'):
            notes = info['notes'].strip().split('\n')[0][:60]
            print(f"    Notes: {notes}...")
        print()
    
    print("\n🔑 KEY INSIGHT:")
    print("-" * 80)
    print("""
    NHS publications have TWO fundamentally different structures:
    
    1. NHS DIGITAL (digital.nhs.uk):
       - Structured pages with Summary, Key Facts, Resources sections
       - Often has central /metadata page with field definitions
       - Period-based URLs (one page per month)
       - Better for automated parsing
    
    2. NHS ENGLAND (england.nhs.uk):
       - Free-form WordPress-style pages
       - Yearly aggregated pages with all months listed
       - Multiple file types per period (XLS, CSV, supplementary)
       - Requires more flexible scraping
    
    COMMON CHALLENGES:
    - File sets vary between periods (quarterly extras, format changes)
    - Schema drift (column shifts, date-columns growing)
    - Revision notes in filenames ("revised 13.11.25")
    - Some pages have metadata/data-quality links, others don't
    """)
    
    print("\n🎯 AGENTIC SOLUTION:")
    print("-" * 80)
    print("""
    DECOUPLE LLM FROM SCHEMA DEFINITION:
    
    1. Page scraping → Extract file URLs + any available metadata
    2. File analysis → Deterministic header extraction + fingerprinting
    3. Schema naming → to_schema_name(header) - NO LLM involvement
    4. LLM enrichment → Optional descriptions/codes stored in metadata table
    5. Cross-period → Match via fingerprint, not LLM similarity
    
    This ensures:
    - ADHD Aug and ADHD Nov get IDENTICAL column names
    - New periods auto-match to existing canonical schema
    - LLM failures don't break data loading
    """)
