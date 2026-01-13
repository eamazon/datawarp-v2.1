#!/usr/bin/env python3
"""DataWarp Cleanup Utility - Find and remove orphaned data.

This script identifies and optionally removes:
1. Database sources without tables
2. Load history records for deleted sources
3. Parquet files without registered sources
4. Manifest files for unloaded sources

Usage:
    python scripts/cleanup_orphans.py              # Dry run (report only)
    python scripts/cleanup_orphans.py --execute    # Actually clean up
    python scripts/cleanup_orphans.py --verbose    # Show details

Examples:
    # See what would be cleaned up
    python scripts/cleanup_orphans.py

    # Actually perform cleanup
    python scripts/cleanup_orphans.py --execute

    # Full details
    python scripts/cleanup_orphans.py --verbose --execute
"""

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
MANIFESTS_DIR = PROJECT_ROOT / "manifests"


def get_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', 5432),
        database=os.getenv('POSTGRES_DB', 'databot_dev'),
        user=os.getenv('POSTGRES_USER', 'databot_dev_user'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )


def find_sources_without_tables(conn, verbose=False):
    """Find registered sources that have no corresponding table."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT s.id, s.code, s.table_name, s.schema_name, s.created_at, s.last_load_at
            FROM datawarp.tbl_data_sources s
            LEFT JOIN information_schema.tables t
              ON t.table_schema = s.schema_name
              AND t.table_name = s.table_name
            WHERE t.table_name IS NULL
            ORDER BY s.created_at DESC
        """)
        orphans = cur.fetchall()

    if verbose and orphans:
        print("\n  Sources without tables:")
        for o in orphans:
            print(f"    - {o['code']} (expected: {o['schema_name']}.{o['table_name']})")

    return orphans


def find_load_history_orphans(conn, verbose=False):
    """Find load_history records referencing non-existent sources."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT lh.id, lh.source_id, lh.file_url, lh.rows_loaded, lh.loaded_at
            FROM datawarp.tbl_load_history lh
            LEFT JOIN datawarp.tbl_data_sources s ON lh.source_id = s.id
            WHERE s.id IS NULL
            ORDER BY lh.loaded_at DESC
        """)
        orphans = cur.fetchall()

    if verbose and orphans:
        print("\n  Load history orphans:")
        for o in orphans[:10]:  # Show first 10
            print(f"    - ID {o['id']}: source_id={o['source_id']}, {o['rows_loaded']} rows")
        if len(orphans) > 10:
            print(f"    ... and {len(orphans) - 10} more")

    return orphans


def find_manifest_file_orphans(conn, verbose=False):
    """Find manifest_files records for non-existent sources."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT mf.id, mf.manifest_name, mf.source_code, mf.file_url, mf.status
            FROM datawarp.tbl_manifest_files mf
            LEFT JOIN datawarp.tbl_data_sources s ON mf.source_code = s.code
            WHERE s.id IS NULL
            ORDER BY mf.created_at DESC
        """)
        orphans = cur.fetchall()

    if verbose and orphans:
        print("\n  Manifest file orphans:")
        for o in orphans[:10]:
            print(f"    - {o['source_code']} in {o['manifest_name']} ({o['status']})")
        if len(orphans) > 10:
            print(f"    ... and {len(orphans) - 10} more")

    return orphans


def find_parquet_orphans(conn, verbose=False):
    """Find parquet files without registered sources."""
    # Get all registered source codes
    with conn.cursor() as cur:
        cur.execute("SELECT code FROM datawarp.tbl_data_sources")
        registered_codes = {row[0] for row in cur.fetchall()}

    # Find parquet files
    orphans = []
    for parquet_file in OUTPUT_DIR.glob("*.parquet"):
        if parquet_file.name == "catalog.parquet":
            continue  # Skip catalog

        source_code = parquet_file.stem
        if source_code not in registered_codes:
            orphans.append({
                'path': parquet_file,
                'source_code': source_code,
                'size_kb': parquet_file.stat().st_size / 1024,
                'md_exists': (OUTPUT_DIR / f"{source_code}.md").exists()
            })

    if verbose and orphans:
        print("\n  Parquet file orphans:")
        for o in orphans[:10]:
            print(f"    - {o['source_code']}.parquet ({o['size_kb']:.1f} KB)")
        if len(orphans) > 10:
            print(f"    ... and {len(orphans) - 10} more")

    return orphans


def find_staging_table_orphans(conn, verbose=False):
    """Find staging tables without registered sources."""
    # Get registered table names
    with conn.cursor() as cur:
        cur.execute("SELECT table_name FROM datawarp.tbl_data_sources WHERE schema_name = 'staging'")
        registered_tables = {row[0] for row in cur.fetchall()}

    # Get actual staging tables
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT table_name,
                   pg_size_pretty(pg_total_relation_size('staging.' || table_name)) as size
            FROM information_schema.tables
            WHERE table_schema = 'staging'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        all_tables = cur.fetchall()

    orphans = [t for t in all_tables if t['table_name'] not in registered_tables]

    if verbose and orphans:
        print("\n  Staging table orphans:")
        for o in orphans[:10]:
            print(f"    - staging.{o['table_name']} ({o['size']})")
        if len(orphans) > 10:
            print(f"    ... and {len(orphans) - 10} more")

    return orphans


def cleanup_sources_without_tables(conn, orphans, dry_run=True):
    """Remove source registrations that have no tables."""
    if not orphans:
        return 0

    if dry_run:
        print(f"  Would delete {len(orphans)} source registrations")
        return 0

    deleted = 0
    with conn.cursor() as cur:
        for o in orphans:
            cur.execute("DELETE FROM datawarp.tbl_data_sources WHERE id = %s", (o['id'],))
            deleted += 1
        conn.commit()

    print(f"  Deleted {deleted} source registrations")
    return deleted


def cleanup_load_history_orphans(conn, orphans, dry_run=True):
    """Remove load_history records for non-existent sources."""
    if not orphans:
        return 0

    if dry_run:
        print(f"  Would delete {len(orphans)} load_history records")
        return 0

    with conn.cursor() as cur:
        ids = [o['id'] for o in orphans]
        cur.execute("DELETE FROM datawarp.tbl_load_history WHERE id = ANY(%s)", (ids,))
        deleted = cur.rowcount
        conn.commit()

    print(f"  Deleted {deleted} load_history records")
    return deleted


def cleanup_manifest_file_orphans(conn, orphans, dry_run=True):
    """Remove manifest_files records for non-existent sources."""
    if not orphans:
        return 0

    if dry_run:
        print(f"  Would delete {len(orphans)} manifest_files records")
        return 0

    with conn.cursor() as cur:
        ids = [o['id'] for o in orphans]
        cur.execute("DELETE FROM datawarp.tbl_manifest_files WHERE id = ANY(%s)", (ids,))
        deleted = cur.rowcount
        conn.commit()

    print(f"  Deleted {deleted} manifest_files records")
    return deleted


def cleanup_parquet_orphans(orphans, dry_run=True):
    """Remove parquet files without registered sources."""
    if not orphans:
        return 0

    if dry_run:
        total_kb = sum(o['size_kb'] for o in orphans)
        print(f"  Would delete {len(orphans)} parquet files ({total_kb:.1f} KB)")
        return 0

    deleted = 0
    for o in orphans:
        o['path'].unlink()
        # Also remove .md file if exists
        md_path = OUTPUT_DIR / f"{o['source_code']}.md"
        if md_path.exists():
            md_path.unlink()
        deleted += 1

    print(f"  Deleted {deleted} parquet files (and associated .md files)")
    return deleted


def cleanup_staging_table_orphans(conn, orphans, dry_run=True):
    """Drop staging tables without registered sources."""
    if not orphans:
        return 0

    if dry_run:
        print(f"  Would drop {len(orphans)} staging tables")
        return 0

    dropped = 0
    with conn.cursor() as cur:
        for o in orphans:
            cur.execute(f"DROP TABLE IF EXISTS staging.{o['table_name']} CASCADE")
            dropped += 1
        conn.commit()

    print(f"  Dropped {dropped} staging tables")
    return dropped


def get_database_stats(conn):
    """Get overall database statistics."""
    stats = {}

    with conn.cursor() as cur:
        # Source count
        cur.execute("SELECT COUNT(*) FROM datawarp.tbl_data_sources")
        stats['sources'] = cur.fetchone()[0]

        # Load history count
        cur.execute("SELECT COUNT(*) FROM datawarp.tbl_load_history")
        stats['load_history'] = cur.fetchone()[0]

        # Manifest files count
        cur.execute("SELECT COUNT(*) FROM datawarp.tbl_manifest_files")
        stats['manifest_files'] = cur.fetchone()[0]

        # Staging tables count
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'staging' AND table_type = 'BASE TABLE'
        """)
        stats['staging_tables'] = cur.fetchone()[0]

        # Total data size
        cur.execute("""
            SELECT pg_size_pretty(SUM(pg_total_relation_size('staging.' || table_name)))
            FROM information_schema.tables
            WHERE table_schema = 'staging' AND table_type = 'BASE TABLE'
        """)
        stats['data_size'] = cur.fetchone()[0] or '0 bytes'

    # Parquet files
    parquet_files = list(OUTPUT_DIR.glob("*.parquet"))
    stats['parquet_files'] = len(parquet_files)
    stats['parquet_size_mb'] = sum(f.stat().st_size for f in parquet_files) / (1024 * 1024)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Find and remove orphaned DataWarp data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/cleanup_orphans.py              # Dry run
  python scripts/cleanup_orphans.py --execute    # Actually cleanup
  python scripts/cleanup_orphans.py -v           # Verbose output
        """
    )
    parser.add_argument('--execute', action='store_true',
                        help='Actually perform cleanup (default: dry run)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Show detailed information')
    parser.add_argument('--skip-tables', action='store_true',
                        help='Skip dropping orphaned staging tables')
    parser.add_argument('--skip-parquet', action='store_true',
                        help='Skip deleting orphaned parquet files')

    args = parser.parse_args()
    dry_run = not args.execute

    print("=" * 60)
    print("DataWarp Orphan Cleanup")
    print("=" * 60)
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'EXECUTE (will delete data)'}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    try:
        conn = get_connection()
    except Exception as e:
        print(f"Error: Could not connect to database: {e}")
        sys.exit(1)

    # Get current stats
    print("Current State:")
    stats = get_database_stats(conn)
    print(f"  Sources registered: {stats['sources']}")
    print(f"  Load history records: {stats['load_history']}")
    print(f"  Manifest file records: {stats['manifest_files']}")
    print(f"  Staging tables: {stats['staging_tables']}")
    print(f"  Database size: {stats['data_size']}")
    print(f"  Parquet files: {stats['parquet_files']} ({stats['parquet_size_mb']:.1f} MB)")
    print()

    # Find orphans
    print("Finding orphans...")

    sources_orphans = find_sources_without_tables(conn, args.verbose)
    load_history_orphans = find_load_history_orphans(conn, args.verbose)
    manifest_file_orphans = find_manifest_file_orphans(conn, args.verbose)
    parquet_orphans = find_parquet_orphans(conn, args.verbose)
    staging_orphans = find_staging_table_orphans(conn, args.verbose)

    print()
    print("Orphan Summary:")
    print(f"  Sources without tables: {len(sources_orphans)}")
    print(f"  Load history orphans: {len(load_history_orphans)}")
    print(f"  Manifest file orphans: {len(manifest_file_orphans)}")
    print(f"  Parquet file orphans: {len(parquet_orphans)}")
    print(f"  Staging table orphans: {len(staging_orphans)}")
    print()

    total_orphans = (
        len(sources_orphans) +
        len(load_history_orphans) +
        len(manifest_file_orphans) +
        len(parquet_orphans) +
        len(staging_orphans)
    )

    if total_orphans == 0:
        print("No orphans found. Database is clean.")
        conn.close()
        return

    # Cleanup
    print("Cleanup Actions:")

    cleanup_sources_without_tables(conn, sources_orphans, dry_run)
    cleanup_load_history_orphans(conn, load_history_orphans, dry_run)
    cleanup_manifest_file_orphans(conn, manifest_file_orphans, dry_run)

    if not args.skip_parquet:
        cleanup_parquet_orphans(parquet_orphans, dry_run)
    else:
        print("  Skipping parquet cleanup (--skip-parquet)")

    if not args.skip_tables:
        cleanup_staging_table_orphans(conn, staging_orphans, dry_run)
    else:
        print("  Skipping table cleanup (--skip-tables)")

    print()

    if dry_run:
        print("This was a DRY RUN. No changes were made.")
        print("Run with --execute to actually perform cleanup.")
    else:
        print("Cleanup complete.")
        print()
        print("New State:")
        stats = get_database_stats(conn)
        print(f"  Sources registered: {stats['sources']}")
        print(f"  Staging tables: {stats['staging_tables']}")
        print(f"  Database size: {stats['data_size']}")
        print(f"  Parquet files: {stats['parquet_files']}")

    conn.close()


if __name__ == "__main__":
    main()
