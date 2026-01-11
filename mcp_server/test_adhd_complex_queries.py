#!/usr/bin/env python3
"""
Test real complex ADHD queries that the user wants to run.
This validates the enhanced query tool with production-like queries.
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from mcp_server.backends.duckdb_parquet import DuckDBBackend


def main():
    print("\n" + "="*70)
    print("COMPLEX ADHD QUERIES - REAL WORLD VALIDATION")
    print("="*70)

    backend = DuckDBBackend({'base_path': 'output/'})
    test_file = 'output/adhd_summary_new_referrals_age.parquet'

    # Query 1: Month-over-month growth rates
    print("\n" + "-"*70)
    print("QUERY 1: Month-over-Month Growth Rates by Age Group")
    print("-"*70)

    sql = '''
        WITH unpivoted AS (
            SELECT
                date_val,
                'age_0_to_4' as age_group,
                age_0_to_4 as referrals
            FROM data
            WHERE SUBSTRING(date_val, 9, 2) = '01'  -- First of month only

            UNION ALL

            SELECT
                date_val,
                'age_5_to_17' as age_group,
                age_5_to_17 as referrals
            FROM data
            WHERE SUBSTRING(date_val, 9, 2) = '01'

            UNION ALL

            SELECT
                date_val,
                'age_18_to_24' as age_group,
                age_18_to_24 as referrals
            FROM data
            WHERE SUBSTRING(date_val, 9, 2) = '01'

            UNION ALL

            SELECT
                date_val,
                'age_25+' as age_group,
                age_25 as referrals
            FROM data
            WHERE SUBSTRING(date_val, 9, 2) = '01'
        ),
        with_prev AS (
            SELECT
                date_val,
                age_group,
                referrals,
                LAG(referrals) OVER (PARTITION BY age_group ORDER BY date_val) as prev_month
            FROM unpivoted
        )
        SELECT
            age_group,
            date_val,
            referrals,
            prev_month,
            CASE
                WHEN prev_month IS NOT NULL AND prev_month > 0
                THEN ROUND(((referrals - prev_month) * 100.0 / prev_month), 2)
                ELSE NULL
            END as growth_rate_pct
        FROM with_prev
        ORDER BY age_group, date_val
    '''

    results = backend.execute(test_file, sql)
    print(f"\n✅ Returned {len(results)} rows")

    # Show sample results for each age group
    print("\nSample MoM Growth Rates:")
    for age_group in ['age_0_to_4', 'age_5_to_17', 'age_18_to_24', 'age_25+']:
        group_results = [r for r in results if r['age_group'] == age_group and r['growth_rate_pct'] is not None]
        if group_results:
            sample = group_results[0]
            print(f"  {age_group:12s}: {sample['date_val']} had {sample['growth_rate_pct']:+6.2f}% growth")

    # Query 2: Seasonal patterns
    print("\n" + "-"*70)
    print("QUERY 2: Seasonal Pattern Analysis (Average by Month)")
    print("-"*70)

    sql = '''
        SELECT
            SUBSTRING(date_val, 6, 2) as month,
            COUNT(*) as periods,
            AVG(total) as avg_referrals,
            MIN(total) as min_referrals,
            MAX(total) as max_referrals,
            ROUND(STDDEV(total), 2) as std_dev
        FROM data
        WHERE SUBSTRING(date_val, 9, 2) = '01'  -- First of month only
        GROUP BY month
        ORDER BY month
    '''

    results = backend.execute(test_file, sql)
    print(f"\n✅ Returned {len(results)} months")

    print("\nMonthly Patterns:")
    month_names = {
        '01': 'January', '02': 'February', '03': 'March', '04': 'April',
        '05': 'May', '06': 'June', '07': 'July', '08': 'August',
        '09': 'September', '10': 'October', '11': 'November', '12': 'December'
    }
    for row in results:
        month_name = month_names.get(row['month'], row['month'])
        std_dev_str = f"{row['std_dev']:6.2f}" if row['std_dev'] is not None else "N/A   "
        print(f"  {month_name:10s}: Avg: {row['avg_referrals']:6.0f}  " +
              f"(Min: {row['min_referrals']:5.0f}, Max: {row['max_referrals']:5.0f}, " +
              f"StdDev: {std_dev_str})")

    # Query 3: Age group comparison
    print("\n" + "-"*70)
    print("QUERY 3: Age Group Distribution and Trends")
    print("-"*70)

    sql = '''
        SELECT
            'age_0_to_4' as age_group,
            SUM(age_0_to_4) as total,
            AVG(age_0_to_4) as avg_per_month,
            MIN(age_0_to_4) as min_month,
            MAX(age_0_to_4) as max_month
        FROM data
        WHERE SUBSTRING(date_val, 9, 2) = '01'

        UNION ALL

        SELECT
            'age_5_to_17',
            SUM(age_5_to_17),
            AVG(age_5_to_17),
            MIN(age_5_to_17),
            MAX(age_5_to_17)
        FROM data
        WHERE SUBSTRING(date_val, 9, 2) = '01'

        UNION ALL

        SELECT
            'age_18_to_24',
            SUM(age_18_to_24),
            AVG(age_18_to_24),
            MIN(age_18_to_24),
            MAX(age_18_to_24)
        FROM data
        WHERE SUBSTRING(date_val, 9, 2) = '01'

        UNION ALL

        SELECT
            'age_25+',
            SUM(age_25),
            AVG(age_25),
            MIN(age_25),
            MAX(age_25)
        FROM data
        WHERE SUBSTRING(date_val, 9, 2) = '01'

        ORDER BY total DESC
    '''

    results = backend.execute(test_file, sql)
    print(f"\n✅ Returned {len(results)} age groups")

    total_all = sum(r['total'] for r in results)
    print("\nAge Group Analysis:")
    for row in results:
        pct = (row['total'] / total_all * 100)
        print(f"  {row['age_group']:12s}: {row['total']:7.0f} total ({pct:5.1f}%)  " +
              f"Avg: {row['avg_per_month']:6.0f}/month  " +
              f"Range: {row['min_month']:5.0f}-{row['max_month']:5.0f}")

    # Query 4: Recent trends (last 3 months)
    print("\n" + "-"*70)
    print("QUERY 4: Recent Trends (Last 3 Months)")
    print("-"*70)

    sql = '''
        SELECT
            date_val,
            total,
            age_5_to_17,
            ROUND(age_5_to_17 * 100.0 / NULLIF(total, 0), 1) as pct_children
        FROM data
        WHERE SUBSTRING(date_val, 9, 2) = '01'
        ORDER BY date_val DESC
        LIMIT 3
    '''

    results = backend.execute(test_file, sql)
    print(f"\n✅ Most recent periods:")

    for row in results:
        print(f"  {row['date_val']}: {row['total']:5.0f} total  " +
              f"({row['age_5_to_17']:5.0f} children, {row['pct_children']:.1f}%)")

    print("\n" + "="*70)
    print("🎉 ALL COMPLEX ADHD QUERIES EXECUTED SUCCESSFULLY!")
    print("="*70)
    print("\nKey Capabilities Demonstrated:")
    print("  ✅ Month-over-month growth rate calculation with LAG()")
    print("  ✅ Seasonal pattern analysis with GROUP BY month")
    print("  ✅ Age group comparison with UNION ALL")
    print("  ✅ Date filtering (first-of-month snapshots)")
    print("  ✅ Statistical aggregations (AVG, MIN, MAX, STDDEV)")
    print("  ✅ Window functions for time-series analysis")
    print("\nThese queries are now available through Claude Desktop!")


if __name__ == "__main__":
    main()
