#!/usr/bin/env python3
"""Verify RTT provider data in database."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from datawarp.storage.connection import get_connection


def main():
    """Verify database data."""
    print("\n" + "="*80)
    print("DATABASE VERIFICATION")
    print("="*80)

    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Check staging tables
        print("\n1. Staging Tables:")
        cursor.execute("""
            SELECT
                table_name,
                pg_size_pretty(pg_total_relation_size('staging.' || table_name)) as size
            FROM information_schema.tables
            WHERE table_schema = 'staging'
            ORDER BY table_name;
        """)

        tables = cursor.fetchall()
        if not tables:
            print("   ❌ No tables found!")
            return 1

        for table_name, size in tables:
            print(f"   • {table_name:<50} {size:>10}")

        print(f"\n   Total tables: {len(tables)}")

        # 2. Check row counts
        print("\n2. Row Counts:")
        total_rows = 0
        for table_name, _ in tables:
            cursor.execute(f"SELECT COUNT(*) FROM staging.{table_name}")
            count = cursor.fetchone()[0]
            total_rows += count
            print(f"   • {table_name:<50} {count:>10,} rows")

        print(f"\n   Total rows: {total_rows:,}")

        # 3. Check columns for first table (verify adaptive sampling)
        if tables:
            first_table = tables[0][0]
            print(f"\n3. Column Structure ({first_table}):")

            cursor.execute(f"""
                SELECT column_name, data_type, character_maximum_length
                FROM information_schema.columns
                WHERE table_schema = 'staging' AND table_name = '{first_table}'
                ORDER BY ordinal_position;
            """)

            columns = cursor.fetchall()
            print(f"   Total columns: {len(columns)}")
            print(f"\n   First 10 columns:")
            for i, (col_name, data_type, max_length) in enumerate(columns[:10], 1):
                type_str = f"{data_type}({max_length})" if max_length else data_type
                print(f"   {i:2}. {col_name:<50} {type_str}")

            if len(columns) > 10:
                print(f"   ... and {len(columns) - 10} more")

        # 4. Check load history
        print("\n4. Load History:")
        cursor.execute("""
            SELECT
                source_code,
                rows_loaded,
                loaded_at
            FROM datawarp.tbl_manifest_files
            WHERE status = 'loaded'
            ORDER BY loaded_at DESC
            LIMIT 10;
        """)

        loads = cursor.fetchall()
        if loads:
            for source_code, rows_loaded, loaded_at in loads:
                print(f"   • {source_code:<50} {rows_loaded:>10,} rows at {loaded_at}")
        else:
            print("   No load history found")

        # 5. Verify intelligent sampling metadata
        print("\n5. Intelligent Sampling Evidence:")
        cursor.execute("""
            SELECT COUNT(DISTINCT column_name)
            FROM datawarp.tbl_column_metadata
            WHERE source_code LIKE 'provider_incomplete_pathways%'
        """)
        total_columns = cursor.fetchone()[0]
        print(f"   Total unique columns tracked: {total_columns}")

        print("\n" + "="*80)
        print("✅ VERIFICATION COMPLETE")
        print("="*80)

    return 0


if __name__ == '__main__':
    sys.exit(main())
