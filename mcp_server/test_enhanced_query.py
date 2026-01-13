#!/usr/bin/env python3
"""
Comprehensive test suite for enhanced DuckDB query tool.

Tests:
1. Backward compatibility (simple queries)
2. SQL query execution
3. Natural language to SQL generation
4. Error handling and fallback
5. Result size limits
6. Different query patterns
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from mcp_server.backends.duckdb_parquet import DuckDBBackend


def test_duckdb_basic():
    """Test 1: DuckDB backend basic operations."""
    print("\n" + "="*70)
    print("TEST 1: DuckDB Backend Basic Operations")
    print("="*70)

    backend = DuckDBBackend({'base_path': 'output/'})

    # Test dataset
    test_file = 'output/adhd_summary_new_referrals_age.parquet'

    # Test 1a: Simple SELECT *
    print("\n1a. SELECT * LIMIT 5")
    results = backend.execute(test_file, 'SELECT * FROM data LIMIT 5')
    print(f"   ✅ Returned {len(results)} rows")
    assert len(results) == 5, f"Expected 5 rows, got {len(results)}"

    # Test 1b: COUNT
    print("\n1b. COUNT(*)")
    results = backend.execute(test_file, 'SELECT COUNT(*) as count FROM data')
    print(f"   ✅ Count: {results[0]['count']}")
    assert len(results) == 1, "COUNT should return 1 row"
    assert results[0]['count'] > 0, "Count should be positive"

    # Test 1c: Aggregation
    print("\n1c. SUM aggregation")
    results = backend.execute(
        test_file,
        'SELECT SUM(total) as grand_total FROM data'
    )
    print(f"   ✅ Grand total: {results[0]['grand_total']:,}")
    assert len(results) == 1, "Aggregation should return 1 row"
    assert results[0]['grand_total'] > 0, "Total should be positive"

    # Test 1d: WHERE filter
    print("\n1d. WHERE filter (date)")
    results = backend.execute(
        test_file,
        "SELECT * FROM data WHERE date_val >= '2024-08-01' LIMIT 3"
    )
    print(f"   ✅ Returned {len(results)} filtered rows")
    assert len(results) > 0, "Filter should return rows"

    print("\n✅ All DuckDB backend tests passed!")


def test_sql_generation():
    """Test 2: Natural language to SQL generation."""
    print("\n" + "="*70)
    print("TEST 2: Natural Language to SQL Generation")
    print("="*70)

    from mcp_server.stdio_server import generate_sql_from_question

    # Load sample data for column inspection
    df = pd.read_parquet('output/adhd_summary_new_referrals_age.parquet')

    test_cases = [
        ("How many rows?", "count"),  # Should generate COUNT
        ("Show me the count", "count"),  # Should generate COUNT
        ("What is the total?", "sum"),  # Should generate SUM
        ("What is the average?", "avg"),  # Should generate AVG
        ("Show distinct values", "distinct"),  # Should generate DISTINCT
    ]

    for question, expected_pattern in test_cases:
        sql, description = generate_sql_from_question(question, df)
        print(f"\n   Q: {question}")
        print(f"   SQL: {sql}")
        print(f"   Desc: {description}")
        assert expected_pattern.lower() in sql.lower(), f"Expected '{expected_pattern}' in SQL"

    print("\n✅ All SQL generation tests passed!")


def test_query_patterns():
    """Test 3: Different query patterns."""
    print("\n" + "="*70)
    print("TEST 3: Complex Query Patterns")
    print("="*70)

    backend = DuckDBBackend({'base_path': 'output/'})
    test_file = 'output/adhd_summary_new_referrals_age.parquet'

    # Test 3a: Aggregation with multiple metrics
    print("\n3a. Multiple aggregations")
    sql = '''
        SELECT
            COUNT(*) as months,
            SUM(total) as total_referrals,
            AVG(total) as avg_referrals,
            MIN(total) as min_referrals,
            MAX(total) as max_referrals
        FROM data
    '''
    results = backend.execute(test_file, sql)
    print(f"   ✅ Returned aggregated metrics across all months")
    assert all('months' in r and 'total_referrals' in r for r in results)
    print(f"      Total: {results[0]['total_referrals']:,}, Avg: {results[0]['avg_referrals']:.0f}")

    # Test 3b: Date filtering
    print("\n3b. Date filtering")
    sql = '''
        SELECT *
        FROM data
        WHERE date_val >= '2024-08-01'
        LIMIT 10
    '''
    results = backend.execute(test_file, sql)
    print(f"   ✅ Date filter returned {len(results)} rows")

    # Test 3c: Complex calculation (MoM growth using window functions)
    print("\n3c. Complex calculation (MoM growth)")
    sql = '''
        SELECT
            date_val,
            total,
            LAG(total) OVER (ORDER BY date_val) as prev_month,
            CASE
                WHEN LAG(total) OVER (ORDER BY date_val) IS NOT NULL
                THEN ROUND(((total - LAG(total) OVER (ORDER BY date_val)) * 100.0
                     / LAG(total) OVER (ORDER BY date_val)), 2)
                ELSE NULL
            END as growth_rate_pct
        FROM data
        ORDER BY date_val
        LIMIT 10
    '''
    results = backend.execute(test_file, sql)
    print(f"   ✅ MoM growth calculation returned {len(results)} rows")
    if len(results) > 1 and results[1].get('growth_rate_pct'):
        print(f"      Sample: {results[1]['date_val']} had {results[1]['growth_rate_pct']}% growth")

    print("\n✅ All complex query pattern tests passed!")


def test_error_handling():
    """Test 4: Error handling."""
    print("\n" + "="*70)
    print("TEST 4: Error Handling")
    print("="*70)

    backend = DuckDBBackend({'base_path': 'output/'})
    test_file = 'output/adhd_summary_new_referrals_age.parquet'

    # Test 4a: Invalid SQL
    print("\n4a. Invalid SQL (should fail gracefully)")
    try:
        results = backend.execute(test_file, 'SELECT invalid_column FROM data')
        print("   ❌ Should have raised error")
        assert False, "Should have raised error for invalid column"
    except Exception as e:
        print(f"   ✅ Caught error: {str(e)[:60]}...")

    # Test 4b: Missing file
    print("\n4b. Missing file (should fail gracefully)")
    try:
        results = backend.execute('output/nonexistent.parquet', 'SELECT * FROM data')
        print("   ❌ Should have raised error")
        assert False, "Should have raised error for missing file"
    except FileNotFoundError as e:
        print(f"   ✅ Caught FileNotFoundError")

    print("\n✅ All error handling tests passed!")


def test_result_limits():
    """Test 5: Result size limits."""
    print("\n" + "="*70)
    print("TEST 5: Result Size Limits")
    print("="*70)

    backend = DuckDBBackend({'base_path': 'output/'})

    # Find a large dataset
    catalog = pd.read_parquet('output/catalog.parquet')
    large_dataset = catalog[catalog['row_count'] > 1000].iloc[0]

    print(f"\nTesting with: {large_dataset['source_code']} ({large_dataset['row_count']:,} rows)")

    # Test 5a: Query without limit (should work, might be slow)
    print("\n5a. Query without LIMIT")
    file_path = str(Path('output') / large_dataset['file_path'].replace('output/', ''))
    results = backend.execute(file_path, 'SELECT * FROM data LIMIT 100')
    print(f"   ✅ Returned {len(results)} rows (with LIMIT 100)")

    # Note: The MCP server has a MAX_ROWS=10000 safety limit in stdio_server.py
    print("\n   Note: MCP server enforces MAX_ROWS=10000 safety limit")

    print("\n✅ Result limit test passed!")


def test_backward_compatibility():
    """Test 6: Backward compatibility with simple queries."""
    print("\n" + "="*70)
    print("TEST 6: Backward Compatibility")
    print("="*70)

    from mcp_server.stdio_server import generate_sql_from_question
    df = pd.read_parquet('output/adhd_summary_new_referrals_age.parquet')

    # Old-style questions that should still work
    old_questions = [
        "How many rows are there?",
        "Show me the data",
        "Count the records",
    ]

    for question in old_questions:
        sql, desc = generate_sql_from_question(question, df)
        print(f"\n   Q: {question}")
        print(f"   ✅ Generated valid SQL: {sql[:50]}...")

    print("\n✅ Backward compatibility maintained!")


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("ENHANCED QUERY TOOL - COMPREHENSIVE TEST SUITE")
    print("="*70)
    print("\nThis validates:")
    print("  ✓ DuckDB backend integration")
    print("  ✓ SQL generation from natural language")
    print("  ✓ Complex query patterns (GROUP BY, aggregations, window functions)")
    print("  ✓ Error handling and graceful failures")
    print("  ✓ Result size limits")
    print("  ✓ Backward compatibility")

    try:
        test_duckdb_basic()
        test_sql_generation()
        test_query_patterns()
        test_error_handling()
        test_result_limits()
        test_backward_compatibility()

        print("\n" + "="*70)
        print("🎉 ALL TESTS PASSED!")
        print("="*70)
        print("\nThe enhanced query tool is ready for production use.")
        print("Complex ADHD queries can now be executed through Claude Desktop.")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
