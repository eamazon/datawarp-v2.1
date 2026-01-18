"""Reset DataWarp v2 database - run SQL schema files."""

import os
import sys
import argparse
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def run_sql_file(filepath, conn):
    """Execute SQL file."""
    print(f"   📄 Running {filepath.name}...")
    with open(filepath, 'r') as f:
        sql = f.read()
        # Remove psql-specific commands (not supported by psycopg2)
        sql = sql.replace('\\echo', '--')
        
        cur = conn.cursor()
        try:
            cur.execute(sql)
            conn.commit()
            print(f"   ✓ {filepath.name} completed")
        except Exception as e:
            print(f"   ❌ Error in {filepath.name}: {e}")
            conn.rollback()
            raise
        finally:
            cur.close()


def get_db_connection():
    """Create database connection."""
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        dbname=os.getenv('POSTGRES_DB', 'datawarp'),
        user=os.getenv('POSTGRES_USER', 'datawarp'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )


def delete_publication_data(publication_pattern: str, dry_run: bool = False):
    """Delete all data for a specific publication.

    Args:
        publication_pattern: Publication code or SQL pattern (e.g., 'adhd' or 'rtt%')
        dry_run: If True, show what would be deleted without deleting
    """
    conn = get_db_connection()
    conn.autocommit = True
    cur = conn.cursor()

    try:
        print(f"🔍 Finding data for publication pattern: {publication_pattern}")

        # 1. Find staging tables
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'staging'
              AND table_name LIKE %s
            ORDER BY table_name
        """, (f'%{publication_pattern}%',))

        staging_tables = [row[0] for row in cur.fetchall()]

        # 2. Find data sources
        cur.execute("""
            SELECT code, name, table_name
            FROM datawarp.tbl_data_sources
            WHERE code LIKE %s OR table_name LIKE %s
            ORDER BY code
        """, (f'%{publication_pattern}%', f'%{publication_pattern}%'))

        data_sources = cur.fetchall()

        # 3. Find manifest files
        cur.execute("""
            SELECT COUNT(*)
            FROM datawarp.tbl_manifest_files
            WHERE source_code LIKE %s
        """, (f'%{publication_pattern}%',))

        manifest_count = cur.fetchone()[0]

        # 4. Find load history
        cur.execute("""
            SELECT COUNT(*)
            FROM datawarp.tbl_load_history lh
            JOIN datawarp.tbl_data_sources ds ON lh.source_id = ds.id
            WHERE ds.code LIKE %s
        """, (f'%{publication_pattern}%',))

        load_history_count = cur.fetchone()[0]

        # Display summary
        print(f"\n📊 Found:")
        print(f"   - {len(staging_tables)} staging tables")
        print(f"   - {len(data_sources)} data sources")
        print(f"   - {manifest_count} manifest records")
        print(f"   - {load_history_count} load history records")

        if staging_tables:
            print(f"\n📋 Staging tables to delete:")
            for table in staging_tables:
                print(f"   - staging.{table}")

        if data_sources:
            print(f"\n📋 Data sources to delete:")
            for code, name, table_name in data_sources:
                print(f"   - {code} ({name}) → {table_name}")

        if not staging_tables and not data_sources:
            print(f"\n✓ No data found for pattern: {publication_pattern}")
            return

        if dry_run:
            print(f"\n🔍 DRY RUN - No changes made")
            return

        # Confirm deletion
        print(f"\n⚠️  This will DELETE all data for this publication!")
        response = input("Continue? (yes/no): ")

        if response.lower() not in ('yes', 'y'):
            print("Cancelled.")
            return

        # Delete in correct order (respecting foreign keys)
        print(f"\n🗑️  Deleting data...")

        # Delete staging tables
        for table in staging_tables:
            print(f"   Dropping staging.{table}...")
            cur.execute(f"DROP TABLE IF EXISTS staging.{table} CASCADE")

        # Delete column metadata (references data sources)
        cur.execute("""
            SELECT COUNT(*)
            FROM datawarp.tbl_column_metadata
            WHERE canonical_source_code LIKE %s
        """, (f'%{publication_pattern}%',))
        column_metadata_count = cur.fetchone()[0]

        if column_metadata_count > 0:
            print(f"   Deleting {column_metadata_count} column metadata records...")
            cur.execute("""
                DELETE FROM datawarp.tbl_column_metadata
                WHERE canonical_source_code LIKE %s
            """, (f'%{publication_pattern}%',))

        # Delete load history (references data sources)
        if load_history_count > 0:
            print(f"   Deleting {load_history_count} load history records...")
            cur.execute("""
                DELETE FROM datawarp.tbl_load_history
                WHERE source_id IN (
                    SELECT id FROM datawarp.tbl_data_sources
                    WHERE code LIKE %s
                )
            """, (f'%{publication_pattern}%',))

        # Delete manifest files
        if manifest_count > 0:
            print(f"   Deleting {manifest_count} manifest records...")
            cur.execute("""
                DELETE FROM datawarp.tbl_manifest_files
                WHERE source_code LIKE %s
            """, (f'%{publication_pattern}%',))

        # Delete data sources
        if data_sources:
            print(f"   Deleting {len(data_sources)} data sources...")
            cur.execute("""
                DELETE FROM datawarp.tbl_data_sources
                WHERE code LIKE %s
            """, (f'%{publication_pattern}%',))

        print(f"\n✅ Publication data deleted successfully!")
        print(f"\nTo reload this publication:")
        print(f"   python scripts/backfill.py --pub {publication_pattern.replace('%', '')}")

    except Exception as e:
        print(f"\n❌ Deletion failed: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def reset_database():
    """Drop all DataWarp tables and recreate from SQL files."""
    
    # Find SQL files
    script_dir = Path(__file__).parent
    schema_dir = script_dir / 'schema'
    
    if not schema_dir.exists():
        print(f"❌ Schema directory not found: {schema_dir}")
        print(f"   Create it with: mkdir -p {schema_dir}")
        return
    
    # Connect to database
    conn = get_db_connection()
    conn.autocommit = True
    
    try:
        print("🗑️  Dropping existing tables...")
        run_sql_file(schema_dir / '99_drop_all.sql', conn)
        
        print("\n🏗️  Creating schemas...")
        run_sql_file(schema_dir / '01_create_schemas.sql', conn)
        
        print("\n📋 Creating tables...")
        run_sql_file(schema_dir / '02_create_tables.sql', conn)
        
        print("\n🔍 Creating indexes...")
        run_sql_file(schema_dir / '03_create_indexes.sql', conn)

        print("\n📊 Creating Phase 1 registry tables (canonicalization)...")
        run_sql_file(schema_dir / '04_create_registry_tables.sql', conn)

        print("\n📊 Creating manifest tracking...")
        run_sql_file(schema_dir / '04_manifest_tracking.sql', conn)

        print("\n🎯 Creating enrichment observability...")
        run_sql_file(schema_dir / '05_enrichment_observability.sql', conn)

        print("\n📊 Creating metadata tables (Track A)...")
        run_sql_file(schema_dir / '05_create_metadata_tables.sql', conn)

        print("\n🌍 Configuring UK date format support...")
        cur = conn.cursor()
        dbname = os.getenv('POSTGRES_DB', 'datawarp')
        cur.execute(f"ALTER DATABASE {dbname} SET DateStyle='DMY,ISO';")
        cur.close()
        print("   ✓ DateStyle set to DMY,ISO (supports DD/MM/YYYY)")

        # INTELLIGENT: Clear state file too (obvious when resetting database)
        print("\n🗑️  Clearing state file...")
        state_file = script_dir.parent / 'state' / 'state.json'
        if state_file.exists():
            state_file.unlink()
            print(f"   ✓ Removed {state_file}")
        else:
            print("   ℹ️  No state file to clear")

        print("\n✅ Database reset complete!")
        print("\nSchemas:")
        print("  - datawarp (registry tables)")
        print("  - staging (data tables)")
        print("\nRegistry tables:")
        print("  - datawarp.tbl_data_sources")
        print("  - datawarp.tbl_load_events (legacy)")
        print("  - datawarp.tbl_load_history (Phase 4)")
        print("  - datawarp.tbl_pipeline_log (observability)")
        print("  - datawarp.tbl_manifest_files (batch loading)")
        print("  - datawarp.tbl_enrichment_runs (LLM observability)")
        print("  - datawarp.tbl_enrichment_api_calls (LLM metrics)")

        
    except Exception as e:
        print(f"\n❌ Reset failed: {e}")
        return
    finally:
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Reset DataWarp database or delete specific publication data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Reset entire database
  python scripts/reset_db.py

  # Delete RTT publication data only (dry run)
  python scripts/reset_db.py --delete rtt --dry-run

  # Delete RTT publication data
  python scripts/reset_db.py --delete rtt

  # Delete all publications matching pattern
  python scripts/reset_db.py --delete "adhd%"
        """
    )
    parser.add_argument(
        '--delete',
        metavar='PATTERN',
        help='Delete specific publication data (e.g., "rtt" or "adhd%%"). Use --dry-run to preview.'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )

    args = parser.parse_args()

    if args.delete:
        # Delete specific publication
        delete_publication_data(args.delete, dry_run=args.dry_run)
    else:
        # Reset entire database
        print("⚠️  WARNING: This will DELETE ALL DATA in DataWarp v2!")
        response = input("Continue? (yes/no): ")

        if response.lower() in ('yes', 'y'):
            reset_database()
        else:
            print("Cancelled.")