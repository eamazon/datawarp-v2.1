"""Test the enhanced list_datasets endpoint with database stats."""

import sys
from pathlib import Path

# Add parent directory to path to import server module
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.server import handle_list_datasets, MCPRequest


def test_list_datasets_without_stats():
    """Test list_datasets without database stats (baseline)."""
    print("=" * 60)
    print("TEST 1: list_datasets WITHOUT database stats")
    print("=" * 60)

    params = {'limit': 3}
    response = handle_list_datasets(params)

    if response.error:
        print(f"❌ Error: {response.error}")
        return False

    result = response.result
    print(f"✅ Found {result['total_found']} datasets")
    print(f"   Includes DB stats: {result.get('includes_db_stats', False)}")
    print(f"   First dataset: {result['datasets'][0]['code']}")
    print()

    return True


def test_list_datasets_with_stats():
    """Test list_datasets WITH database stats."""
    print("=" * 60)
    print("TEST 2: list_datasets WITH database stats")
    print("=" * 60)

    params = {'limit': 3, 'include_stats': True}
    response = handle_list_datasets(params)

    if response.error:
        print(f"❌ Error: {response.error}")
        return False

    result = response.result
    print(f"✅ Found {result['total_found']} datasets")
    print(f"   Includes DB stats: {result.get('includes_db_stats', False)}")
    print()

    # Show first dataset with stats
    if result['datasets']:
        first = result['datasets'][0]
        print(f"📊 First dataset: {first['code']}")
        print(f"   Catalog rows: {first['rows']:,}")
        print(f"   Catalog columns: {first['columns']}")

        if 'db_stats' in first:
            db = first['db_stats']
            print(f"   DB rows: {db['row_count']:,}")
            print(f"   DB size: {db['size_mb']:.2f} MB")
            print(f"   Last loaded: {db['last_loaded']}")
            print(f"   Load count: {db['load_count']}")
            print(f"   Table exists: {db['exists']}")
        else:
            print("   ⚠️  No database stats returned")
    print()

    return True


def test_filter_with_stats():
    """Test filtering datasets and getting stats."""
    print("=" * 60)
    print("TEST 3: Filter by keyword + database stats")
    print("=" * 60)

    params = {
        'keyword': 'adhd',
        'limit': 5,
        'include_stats': True
    }
    response = handle_list_datasets(params)

    if response.error:
        print(f"❌ Error: {response.error}")
        return False

    result = response.result
    print(f"✅ Found {result['total_found']} ADHD datasets")
    print()

    # Show all matching datasets with stats
    for dataset in result['datasets']:
        print(f"📊 {dataset['code']}")
        if 'db_stats' in dataset:
            db = dataset['db_stats']
            print(f"   Rows: {db['row_count']:,} | Size: {db['size_mb']:.2f} MB | Loads: {db['load_count']}")
        print()

    return True


if __name__ == "__main__":
    print("\n🧪 Testing Enhanced MCP Server - Database Stats Integration\n")

    results = []
    results.append(("Without stats", test_list_datasets_without_stats()))
    results.append(("With stats", test_list_datasets_with_stats()))
    results.append(("Filter + stats", test_filter_with_stats()))

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    all_passed = all(r[1] for r in results)
    print()
    if all_passed:
        print("🎉 All tests passed!")
    else:
        print("⚠️  Some tests failed")
        sys.exit(1)
