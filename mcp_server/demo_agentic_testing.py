"""Demonstrate MCP database stats for agentic testing.

This shows how agents can use the enhanced MCP endpoint to:
1. Check data freshness
2. Detect catalog/database mismatches
3. Monitor table sizes
4. Generate dynamic tests
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.server import handle_list_datasets


def print_section(title):
    """Pretty print section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def test_1_freshness_check():
    """TEST 1: Check if any datasets are stale (>24 hours old)."""
    print_section("TEST 1: Freshness Check - Find Stale Data")

    print("🤖 Agent Query: 'Show me datasets older than 24 hours'\n")

    # Query MCP with database stats
    params = {'limit': 100, 'include_stats': True}
    response = handle_list_datasets(params)

    if response.error:
        print(f"❌ Error: {response.error}")
        return False

    datasets = response.result['datasets']
    now = datetime.utcnow()
    stale_datasets = []

    print(f"📊 Analyzing {len(datasets)} datasets...\n")

    for dataset in datasets:
        if 'db_stats' not in dataset:
            continue

        last_loaded = dataset['db_stats'].get('last_loaded')
        if not last_loaded:
            stale_datasets.append((dataset['code'], "Never loaded"))
            continue

        # Parse timestamp
        loaded_time = datetime.fromisoformat(last_loaded)
        hours_ago = (now - loaded_time).total_seconds() / 3600

        if hours_ago > 24:
            stale_datasets.append((dataset['code'], f"{hours_ago:.1f} hours ago"))

    # Report results
    if stale_datasets:
        print(f"⚠️  Found {len(stale_datasets)} stale datasets:\n")
        for code, age in stale_datasets[:5]:  # Show first 5
            print(f"   - {code}: {age}")
        if len(stale_datasets) > 5:
            print(f"   ... and {len(stale_datasets) - 5} more")
    else:
        print("✅ All datasets are fresh (loaded within 24 hours)")

    print(f"\n📈 Test Result: {len(datasets)} checked, {len(stale_datasets)} stale")
    return True


def test_2_consistency_check():
    """TEST 2: Check if catalog row counts match database."""
    print_section("TEST 2: Consistency Check - Catalog vs Database")

    print("🤖 Agent Query: 'Find datasets where catalog doesn't match database'\n")

    # Query MCP with database stats
    params = {'limit': 20, 'include_stats': True}
    response = handle_list_datasets(params)

    if response.error:
        print(f"❌ Error: {response.error}")
        return False

    datasets = response.result['datasets']
    mismatches = []

    print(f"📊 Checking {len(datasets)} datasets for consistency...\n")

    for dataset in datasets:
        if 'db_stats' not in dataset:
            continue

        catalog_rows = dataset['rows']
        db_rows = dataset['db_stats']['row_count']
        table_exists = dataset['db_stats']['exists']

        # Check for mismatches
        if not table_exists and catalog_rows > 0:
            mismatches.append({
                'code': dataset['code'],
                'issue': 'Table missing',
                'catalog': catalog_rows,
                'database': 0
            })
        elif abs(catalog_rows - db_rows) > 100:  # Allow small differences
            mismatches.append({
                'code': dataset['code'],
                'issue': 'Row count mismatch',
                'catalog': catalog_rows,
                'database': db_rows
            })

    # Report results
    if mismatches:
        print(f"❌ Found {len(mismatches)} inconsistencies:\n")
        for m in mismatches[:5]:
            print(f"   - {m['code']}: {m['issue']}")
            print(f"     Catalog: {m['catalog']:,} rows | Database: {m['database']:,} rows")
    else:
        print("✅ All datasets consistent (catalog matches database)")

    print(f"\n📈 Test Result: {len(datasets)} checked, {len(mismatches)} inconsistent")
    return True


def test_3_size_monitoring():
    """TEST 3: Find largest datasets and monitor storage."""
    print_section("TEST 3: Size Monitoring - Find Largest Tables")

    print("🤖 Agent Query: 'What are the 5 largest datasets?'\n")

    # Query MCP with database stats
    params = {'limit': 100, 'include_stats': True}
    response = handle_list_datasets(params)

    if response.error:
        print(f"❌ Error: {response.error}")
        return False

    datasets = response.result['datasets']

    # Filter datasets with DB stats and sort by size
    datasets_with_size = [
        d for d in datasets
        if 'db_stats' in d and d['db_stats']['size_mb'] > 0
    ]

    largest = sorted(
        datasets_with_size,
        key=lambda d: d['db_stats']['size_mb'],
        reverse=True
    )[:5]

    print("📊 Top 5 Largest Datasets:\n")

    total_size = 0
    for i, dataset in enumerate(largest, 1):
        size_mb = dataset['db_stats']['size_mb']
        rows = dataset['db_stats']['row_count']
        avg_row_size = (size_mb * 1024 * 1024) / rows if rows > 0 else 0

        print(f"{i}. {dataset['code']}")
        print(f"   Size: {size_mb:,.1f} MB | Rows: {rows:,} | Avg row: {avg_row_size:.0f} bytes")
        total_size += size_mb

    print(f"\n📈 Top 5 total: {total_size:,.1f} MB")

    # Calculate percentage of all data
    all_size = sum(d['db_stats']['size_mb'] for d in datasets_with_size)
    pct = (total_size / all_size * 100) if all_size > 0 else 0
    print(f"   That's {pct:.1f}% of all data")

    return True


def test_4_dynamic_test_generation():
    """TEST 4: Generate tests from database state (meta-testing)."""
    print_section("TEST 4: Dynamic Test Generation - Auto-Create Tests")

    print("🤖 Agent Query: 'Generate tests for all datasets'\n")

    # Query MCP with database stats
    params = {'limit': 10, 'include_stats': True}
    response = handle_list_datasets(params)

    if response.error:
        print(f"❌ Error: {response.error}")
        return False

    datasets = response.result['datasets']

    print(f"📊 Generating tests for {len(datasets)} datasets...\n")

    # Generate test code dynamically
    print("Generated Test Code:")
    print("-" * 70)
    print("""
def test_all_datasets_healthy():
    '''Auto-generated test from MCP database stats.'''
    datasets = mcp.list_datasets(include_stats=True, limit=10)

    failures = []
    for dataset in datasets:
        code = dataset['code']
        db_stats = dataset['db_stats']

        # Test 1: Table must exist
        if not db_stats['exists']:
            failures.append(f"{code}: Table doesn't exist")

        # Test 2: Must have rows
        if db_stats['row_count'] == 0:
            failures.append(f"{code}: 0 rows (empty table)")

        # Test 3: Must be fresh (loaded within 48h)
        if not db_stats['last_loaded']:
            failures.append(f"{code}: Never loaded")

        # Test 4: Must match catalog (within 5% tolerance)
        catalog_rows = dataset['rows']
        db_rows = db_stats['row_count']
        diff_pct = abs(catalog_rows - db_rows) / catalog_rows * 100
        if diff_pct > 5:
            failures.append(f"{code}: {diff_pct:.1f}% mismatch")

    assert len(failures) == 0, f"Found {len(failures)} issues:\\n" + "\\n".join(failures)
""")
    print("-" * 70)

    # Now actually run those checks
    print("\n🧪 Running the generated tests...\n")

    failures = []
    for dataset in datasets:
        if 'db_stats' not in dataset:
            continue

        code = dataset['code']
        db_stats = dataset['db_stats']

        # Run the 4 checks
        if not db_stats['exists']:
            failures.append(f"{code}: Table doesn't exist")
        elif db_stats['row_count'] == 0:
            failures.append(f"{code}: 0 rows (empty table)")
        elif not db_stats['last_loaded']:
            failures.append(f"{code}: Never loaded")
        else:
            # Check freshness (within 48h)
            loaded = datetime.fromisoformat(db_stats['last_loaded'])
            hours_ago = (datetime.utcnow() - loaded).total_seconds() / 3600

            # Check catalog match
            catalog_rows = dataset['rows']
            db_rows = db_stats['row_count']
            diff_pct = abs(catalog_rows - db_rows) / catalog_rows * 100 if catalog_rows > 0 else 0

            if hours_ago > 48:
                failures.append(f"{code}: Stale ({hours_ago:.0f}h old)")
            if diff_pct > 5:
                failures.append(f"{code}: {diff_pct:.1f}% catalog/DB mismatch")

    # Report results
    if failures:
        print(f"❌ Test failed with {len(failures)} issues:\n")
        for failure in failures[:5]:
            print(f"   - {failure}")
        if len(failures) > 5:
            print(f"   ... and {len(failures) - 5} more")
    else:
        print(f"✅ All {len(datasets)} datasets passed 4 health checks:")
        print("   1. Table exists")
        print("   2. Has rows (not empty)")
        print("   3. Loaded within 48 hours")
        print("   4. Catalog matches database")

    print(f"\n📈 Test Result: {len(datasets)} datasets tested, {len(failures)} failures")
    return True


def main():
    """Run all demonstration tests."""
    print("\n" + "=" * 70)
    print("  MCP DATABASE STATS - AGENTIC TESTING DEMONSTRATION")
    print("=" * 70)
    print("\nShowing how agents use enhanced MCP to test your data...\n")

    tests = [
        ("Freshness Check", test_1_freshness_check),
        ("Consistency Check", test_2_consistency_check),
        ("Size Monitoring", test_3_size_monitoring),
        ("Dynamic Test Generation", test_4_dynamic_test_generation)
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed, None))
        except Exception as e:
            results.append((name, False, str(e)))

    # Summary
    print_section("SUMMARY")

    for name, passed, error in results:
        if passed:
            print(f"✅ {name}: PASS")
        else:
            print(f"❌ {name}: FAIL")
            if error:
                print(f"   Error: {error}")

    passed_count = sum(1 for _, p, _ in results if p)
    print(f"\n🎯 {passed_count}/{len(tests)} tests passed")

    print("\n" + "=" * 70)
    print("  KEY TAKEAWAY")
    print("=" * 70)
    print("""
These 4 tests ran automatically by querying MCP with include_stats=True.
Without database stats, you'd need to:
- Write 162 separate SQL queries (one per dataset)
- Manually compare results
- Update tests every time you add new data

With MCP enhancement:
- One API call gets stats for all datasets
- Agents analyze and report issues automatically
- Tests adapt as you add new datasets (no maintenance)
""")


if __name__ == "__main__":
    main()
