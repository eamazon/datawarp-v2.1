#!/usr/bin/env python3
"""Validate loaded data in PostgreSQL staging tables.

Usage:
    python scripts/validate_loaded_data.py adhd_summary_open_referrals_age
    python scripts/validate_loaded_data.py --all
    python scripts/validate_loaded_data.py --publication adhd
"""
import sys
import os
import argparse
from pathlib import Path
from typing import List, Tuple, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from datawarp.storage.connection import get_connection


def validate_table(table_name: str, conn, strict: bool = False) -> Tuple[List[str], List[str]]:
    """Validate a single staging table."""

    errors = []
    warnings = []

    schema = 'staging'
    full_table = f"{schema}.{table_name}"
    cur = conn.cursor()

    # 1. Check table exists
    cur.execute(f"""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = '{schema}' AND table_name = '{table_name}'
        )
    """)
    table_check = cur

    if not table_check or not table_check[0]:
        errors.append(f"Table {full_table} does not exist")
        return errors, warnings

    # 2. Check table is not empty
    cur.execute(f"SELECT COUNT(*) FROM {full_table}")
    row_count_result = cur
    row_count = row_count_result[0] if row_count_result else 0

    if row_count == 0:
        errors.append(f"Table {full_table} is empty (0 rows)")
        return errors, warnings

    # 3. Get column information
    cur.execute(f"""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = '{schema}' AND table_name = '{table_name}'
        ORDER BY ordinal_position
    """)
    columns_result = cur

    columns = [
        {'name': row[0], 'type': row[1], 'nullable': row[2]}
        for row in columns_result
    ]

    if len(columns) == 0:
        errors.append(f"Table {full_table} has no columns")
        return errors, warnings

    # 4. Check for audit columns
    audit_columns = ['_load_id', '_loaded_at', '_period', '_manifest_file_id']
    missing_audit = [col for col in audit_columns if col not in [c['name'] for c in columns]]

    if missing_audit:
        warnings.append(f"Missing audit columns: {', '.join(missing_audit)}")

    # 5. Check for all-NULL columns (data quality issue)
    business_columns = [
        c['name'] for c in columns
        if not c['name'].startswith('_')  # Exclude audit columns
    ]

    for col_name in business_columns:
        cur.execute(f"""
            SELECT COUNT(*)
            FROM {full_table}
            WHERE "{col_name}" IS NULL
        """)

        null_count = null_count_result[0] if null_count_result else 0
        null_rate = (null_count / row_count * 100) if row_count > 0 else 0

        if null_count == row_count:
            warnings.append(f"Column '{col_name}' is 100% NULL ({row_count} rows)")
        elif null_rate > 50 and strict:
            warnings.append(f"Column '{col_name}' has high NULL rate: {null_rate:.1f}%")

    # 6. Check for metadata (if enriched source)
    # Try to find canonical source code from table name
    canonical_code = None

    # Check if metadata exists for this table
    cur.execute(f"""
        SELECT cs.canonical_source_code, COUNT(cm.column_name) as col_count
        FROM datawarp.tbl_canonical_sources cs
        LEFT JOIN datawarp.tbl_column_metadata cm
            ON cs.canonical_source_code = cm.canonical_source_code
        WHERE cs.staging_table_name = '{table_name}'
        GROUP BY cs.canonical_source_code
    """)

    if metadata_result:
        canonical_code, metadata_col_count = metadata_result

        if metadata_col_count == 0:
            warnings.append(f"No column metadata found for {canonical_code}")
        elif metadata_col_count < len(business_columns):
            warnings.append(
                f"Partial metadata coverage: {metadata_col_count}/{len(business_columns)} columns"
            )

    # 7. Check for cross-period data (multiple distinct _period values)
    if '_period' in [c['name'] for c in columns]:
        cur.execute(f"""
            SELECT COUNT(DISTINCT _period) as period_count,
                   MIN(_period) as earliest,
                   MAX(_period) as latest
            FROM {full_table}
            WHERE _period IS NOT NULL
        """)

        if period_result:
            period_count, earliest, latest = period_result
            if period_count > 1:
                # This is good - cross-period consolidation working
                pass  # No warning, this is expected
            elif strict:
                warnings.append(f"Only 1 period loaded: {earliest}")

    # 8. Check for reasonable row count (basic sanity)
    if row_count > 10_000_000:
        warnings.append(f"Very large table: {row_count:,} rows (performance concern)")

    return errors, warnings


def get_all_staging_tables(conn) -> List[str]:
    """Get all table names in staging schema."""

    result = conn.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'staging'
        ORDER BY table_name
    """)

    return [row[0] for row in result]


def get_tables_by_publication(conn, publication_prefix: str) -> List[str]:
    """Get staging tables matching publication prefix (e.g., 'adhd')."""

    result = conn.execute(f"""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'staging'
          AND table_name LIKE 'tbl_{publication_prefix}%'
        ORDER BY table_name
    """)

    return [row[0] for row in result]


def main():
    parser = argparse.ArgumentParser(description='Validate loaded data in PostgreSQL')
    parser.add_argument('table', nargs='?', help='Table name to validate (without schema prefix)')
    parser.add_argument('--all', action='store_true', help='Validate all staging tables')
    parser.add_argument('--publication', help='Validate all tables for a publication (e.g., adhd, gp_practice)')
    parser.add_argument('--strict', action='store_true', help='Enable strict validation (more warnings)')

    args = parser.parse_args()

    if not args.table and not args.all and not args.publication:
        parser.error('Must specify either table name, --all, or --publication')

    # Connect to database
    with get_connection() as conn:
        # Determine which tables to validate
        if args.all:
            tables = get_all_staging_tables(conn)
            print(f"Validating all {len(tables)} staging tables...")
        elif args.publication:
            tables = get_tables_by_publication(conn, args.publication)
            print(f"Validating {len(tables)} tables for publication '{args.publication}'...")
        else:
            # Single table - remove 'staging.' prefix if present
            table_name = args.table.replace('staging.', '').replace('tbl_', '')
            if not table_name.startswith('tbl_'):
                table_name = f'tbl_{table_name}'
            tables = [table_name]

        if not tables:
            print(f"❌ No tables found")
            sys.exit(1)

        total_errors = 0
        total_warnings = 0
        tables_validated = 0

        for table_name in tables:
            print(f"\n{'='*80}")
            print(f"Validating: staging.{table_name}")
            print(f"{'='*80}")

            errors, warnings = validate_table(table_name, conn, args.strict)

            if errors:
                print(f"\n❌ ERRORS ({len(errors)}):")
                for err in errors:
                    print(f"   - {err}")
                total_errors += len(errors)

            if warnings:
                print(f"\n⚠️  WARNINGS ({len(warnings)}):")
                for warn in warnings:
                    print(f"   - {warn}")
                total_warnings += len(warnings)

            if not errors and not warnings:
                print("\n✅ VALID: No errors or warnings")

            tables_validated += 1

        print(f"\n{'='*80}")
        print(f"SUMMARY:")
        print(f"  Tables validated: {tables_validated}")
        print(f"  Total errors: {total_errors}")
        print(f"  Total warnings: {total_warnings}")
        print(f"{'='*80}")

        # Exit code: 0 if no errors, 1 if errors found
        sys.exit(1 if total_errors > 0 else 0)


if __name__ == '__main__':
    main()
