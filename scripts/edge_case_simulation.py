#!/usr/bin/env python3
"""
SIMULATION: to_schema_name() against real NHS data patterns
Testing edge cases from 8 publications to validate proposed solution.

Usage:
    python scripts/edge_case_simulation.py
"""
import re
import hashlib


def to_schema_name(header: str) -> str:
    """
    Proposed deterministic naming function.
    
    Converts any Excel header to a valid PostgreSQL column name.
    100% deterministic - no LLM involvement.
    """
    if not header or not header.strip():
        return None
    
    # Lowercase and clean
    name = header.lower().strip()
    
    # Replace any non-alphanumeric with underscore
    name = re.sub(r'[^a-z0-9]+', '_', name)
    
    # Strip leading/trailing underscores
    name = name.strip('_')
    
    # Collapse multiple underscores
    name = re.sub(r'_+', '_', name)
    
    # PostgreSQL columns can't start with a digit
    if name and name[0].isdigit():
        name = 'col_' + name
    
    # Truncate to 60 chars (PostgreSQL limit is 63)
    return name[:60] if name else None


def fingerprint(headers: list) -> str:
    """
    Generate fingerprint from headers.
    
    Used for cross-period source matching.
    Ignores order, ignores empty headers.
    """
    normalized = [to_schema_name(h) for h in headers if h]
    normalized = [n for n in normalized if n]
    sorted_names = sorted(normalized)
    return hashlib.md5("|".join(sorted_names).encode()).hexdigest()[:8]


def run_simulation():
    """Run all edge case tests."""
    
    print("=" * 80)
    print("SIMULATION: to_schema_name() EDGE CASE ANALYSIS")
    print("=" * 80)

    results = []

    # ========================================================================
    # TEST 1: GP Practice - Stable headers (SHOULD WORK)
    # ========================================================================
    print("\n📊 TEST 1: GP Practice Registrations")
    print("-" * 40)

    gp_july = ["PUBLICATION", "EXTRACT_DATE", "ORG_TYPE", "ORG_CODE", "AGE", "NUMBER_OF_PATIENTS"]
    gp_aug = ["PUBLICATION", "EXTRACT_DATE", "ORG_TYPE", "ORG_CODE", "AGE", "NUMBER_OF_PATIENTS"]

    print(f"July headers:  {gp_july}")
    print(f"August headers: {gp_aug}")
    print(f"July fingerprint:  {fingerprint(gp_july)}")
    print(f"August fingerprint: {fingerprint(gp_aug)}")
    match = fingerprint(gp_july) == fingerprint(gp_aug)
    print(f"Match: {'✅ YES' if match else '❌ NO'}")
    results.append(("GP Practice", match, "Stable headers"))

    # ========================================================================
    # TEST 2: ADHD - Column shift (EDGE CASE!)
    # ========================================================================
    print("\n📊 TEST 2: ADHD Referrals - COLUMN SHIFT")
    print("-" * 40)

    adhd_aug = ["Date", "Age 0 to 4", "Age 5 to 17", "Unknown", "Total"]
    adhd_nov = ["", "Date", "Age 0 to 4", "Age 5 to 17", "Unknown", "Total"]  # Empty col A!

    print(f"August headers: {adhd_aug}")
    print(f"November headers: {adhd_nov}")

    aug_schema = [to_schema_name(h) for h in adhd_aug]
    nov_schema = [to_schema_name(h) for h in adhd_nov]

    print(f"August schema:  {aug_schema}")
    print(f"November schema: {nov_schema}")
    print(f"August fingerprint:  {fingerprint(adhd_aug)}")
    print(f"November fingerprint: {fingerprint(adhd_nov)}")
    match = fingerprint(adhd_aug) == fingerprint(adhd_nov)
    print(f"Match: {'✅ YES' if match else '❌ NO'}")
    results.append(("ADHD Column Shift", match, "Empty column ignored"))

    # ========================================================================
    # TEST 3: PCN Workforce - Date columns grow (CRITICAL EDGE CASE!)
    # ========================================================================
    print("\n📊 TEST 3: PCN Workforce - DATE COLUMNS GROW")
    print("-" * 40)

    pcn_oct = ["Organisation", "Staff Type", "September 2025", "October 2025"]
    pcn_nov = ["Organisation", "Staff Type", "September 2025", "October 2025", "November 2025"]

    print(f"October headers: {pcn_oct}")
    print(f"November headers: {pcn_nov}")

    oct_schema = [to_schema_name(h) for h in pcn_oct]
    nov_schema = [to_schema_name(h) for h in pcn_nov]

    print(f"October schema:  {oct_schema}")
    print(f"November schema: {nov_schema}")
    print(f"October fingerprint:  {fingerprint(pcn_oct)}")
    print(f"November fingerprint: {fingerprint(pcn_nov)}")
    match = fingerprint(pcn_oct) == fingerprint(pcn_nov)
    print(f"Match: {'✅ YES' if match else '❌ NO'}")
    results.append(("PCN Workforce", match, "New date column each month"))

    # ========================================================================
    # TEST 4: Dementia 65+ - Rolling date columns (CRITICAL EDGE CASE!)
    # ========================================================================
    print("\n📊 TEST 4: Dementia 65+ - ROLLING DATE COLUMNS")
    print("-" * 40)

    dementia_aug = ["ICB", "Aug-25", "Jul-25", "Jun-25"]  # Latest 3 months
    dementia_sep = ["ICB", "Sep-25", "Aug-25", "Jul-25"]  # Dropped Jun, added Sep

    print(f"August headers: {dementia_aug}")
    print(f"September headers: {dementia_sep}")

    aug_schema = [to_schema_name(h) for h in dementia_aug]
    sep_schema = [to_schema_name(h) for h in dementia_sep]

    print(f"August schema:  {aug_schema}")
    print(f"September schema: {sep_schema}")
    print(f"August fingerprint:  {fingerprint(dementia_aug)}")
    print(f"September fingerprint: {fingerprint(dementia_sep)}")
    match = fingerprint(dementia_aug) == fingerprint(dementia_sep)
    print(f"Match: {'✅ YES' if match else '❌ NO'}")
    results.append(("Dementia Rolling", match, "Columns change each month"))

    # ========================================================================
    # TEST 5: A&E Waiting Times - Long format (SHOULD WORK)
    # ========================================================================
    print("\n📊 TEST 5: A&E Waiting Times - LONG FORMAT")
    print("-" * 40)

    ae_nov = ["Period", "Org Code", "Org Name", "Total Attendances", "Within 4 Hours"]
    ae_dec = ["Period", "Org Code", "Org Name", "Total Attendances", "Within 4 Hours"]

    print(f"November headers: {ae_nov}")
    print(f"December headers: {ae_dec}")
    print(f"November fingerprint:  {fingerprint(ae_nov)}")
    print(f"December fingerprint: {fingerprint(ae_dec)}")
    match = fingerprint(ae_nov) == fingerprint(ae_dec)
    print(f"Match: {'✅ YES' if match else '❌ NO'}")
    results.append(("A&E Waiting Times", match, "Long format is ideal"))

    # ========================================================================
    # TEST 6: Duplicate names after normalization (EDGE CASE!)
    # ========================================================================
    print("\n📊 TEST 6: DUPLICATE NAMES AFTER NORMALIZATION")
    print("-" * 40)

    headers = ["Age (0-4)", "Age 0 to 4", "Age 0-4", "Age: 0-4"]
    schemas = [to_schema_name(h) for h in headers]

    print(f"Original headers: {headers}")
    print(f"Normalized schemas: {schemas}")

    unique_schemas = set(schemas)
    print(f"Unique count: {len(unique_schemas)} / {len(schemas)}")
    has_collision = len(unique_schemas) < len(schemas)
    if has_collision:
        print("⚠️ COLLISION! Multiple headers map to same column name!")
    results.append(("Duplicate Detection", not has_collision, 
                   f"Collision detected: {has_collision}"))

    # ========================================================================
    # TEST 7: Multi-tier headers (EDGE CASE!)
    # ========================================================================
    print("\n📊 TEST 7: MULTI-TIER HEADERS")
    print("-" * 40)

    # NHS Excel often has hierarchical headers that get flattened
    flattened_headers = [
        "Wales_2024_April",
        "Wales_2024_May", 
        "Wales_2024_June",
        "England_2024_April"
    ]

    schemas = [to_schema_name(h) for h in flattened_headers]
    print(f"Flattened headers: {flattened_headers}")
    print(f"Normalized schemas: {schemas}")
    print("✅ Works IF extractor.py flattens correctly")
    results.append(("Multi-tier Headers", True, "Depends on extractor flattening"))

    # ========================================================================
    # TEST 8: Very long column names (EDGE CASE!)
    # ========================================================================
    print("\n📊 TEST 8: VERY LONG COLUMN NAMES")
    print("-" * 40)

    long_header = "Number of patients waiting more than 52 weeks for treatment following a referral to a consultant-led service"
    schema = to_schema_name(long_header)

    print(f"Original: {long_header}")
    print(f"Length: {len(long_header)} chars")
    print(f"Schema: {schema}")
    print(f"Schema length: {len(schema)} chars")
    
    is_truncated = len(schema) < len(long_header.lower().replace(' ', '_'))
    print(f"Truncated: {'⚠️ YES' if is_truncated else 'No'}")
    results.append(("Long Column Names", True, f"Truncated to {len(schema)} chars"))

    # ========================================================================
    # TEST 9: Date columns that are NOT part of header pattern
    # ========================================================================
    print("\n📊 TEST 9: SIMILAR BUT DIFFERENT PATTERNS")
    print("-" * 40)
    
    # These headers look similar but might collide
    similar_headers = [
        "Patients aged 0-17",
        "Patients aged 0 to 17", 
        "Patients Aged 0-17",
        "patients_aged_0_17"  # Already normalized by NHS
    ]
    
    schemas = [to_schema_name(h) for h in similar_headers]
    print(f"Similar headers: {similar_headers}")
    print(f"Normalized schemas: {schemas}")
    
    unique = len(set(schemas))
    print(f"Unique: {unique} / {len(schemas)}")
    print("⚠️ These ALL map to 'patients_aged_0_17' - COLLISION!" if unique == 1 else "")
    results.append(("Similar Patterns", unique > 1, f"{unique} unique out of {len(schemas)}"))

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "=" * 80)
    print("EDGE CASE SUMMARY")
    print("=" * 80)
    
    print("\n✅ WORKS:")
    for name, passed, note in results:
        if passed:
            print(f"   - {name}: {note}")
    
    print("\n❌ BREAKS:")
    for name, passed, note in results:
        if not passed:
            print(f"   - {name}: {note}")
    
    print("\n" + "=" * 80)
    print("CRITICAL FINDINGS")
    print("=" * 80)
    print("""
1. DATE-AS-COLUMNS PATTERN (PCN Workforce, Dementia 65+):
   - Each month adds/changes columns
   - Fingerprints will NEVER match across periods
   - SOLUTION: Detect pattern, unpivot to long format:
     [Org, "Oct 2025": 100, "Nov 2025": 200]
     → [Org, period, value]
        [Org, "Oct 2025", 100]
        [Org, "Nov 2025", 200]

2. COLUMN COLLISIONS:
   - Multiple Excel headers can normalize to same column
   - "Age (0-4)" == "Age 0-4" == "Age: 0-4"
   - SOLUTION: Detect during extraction, add suffix: age_0_4, age_0_4_1

3. EMPTY COLUMN HANDLING:
   - Column shifts (ADHD Nov) create empty headers
   - to_schema_name returns None for empty strings
   - Fingerprint correctly ignores these ✅

4. TRUNCATION COLLISIONS:
   - Very long headers get truncated to 60 chars
   - Two different long headers could collide
   - SOLUTION: Add hash suffix if truncated:
     "very_long_column_name_abc123" (60 chars)
""")

    return results


if __name__ == "__main__":
    run_simulation()
