#!/usr/bin/env python3
"""DataWarp Parquet Export CLI (v2.2 - Thin Wrapper).

Thin CLI wrapper around datawarp.pipeline.export_* library functions.

Usage:
    python export_to_parquet.py SOURCE_CODE output/
    python export_to_parquet.py --publication adhd output/
    python export_to_parquet.py --all output/
"""
import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from datawarp.pipeline import export_source_to_parquet, export_publication_to_parquet
from datawarp.storage.connection import get_connection


def main():
    parser = argparse.ArgumentParser(
        description='Export DataWarp staging tables to Parquet with metadata'
    )
    parser.add_argument('source', nargs='?', help='Canonical source code to export')
    parser.add_argument('output_dir', nargs='?', default='output',
                        help='Output directory (default: output/)')
    parser.add_argument('--all', action='store_true',
                        help='Export all sources')
    parser.add_argument('--publication', help='Export all sources from a publication (e.g., adhd)')

    args = parser.parse_args()

    if not any([args.source, args.all, args.publication]):
        parser.print_help()
        sys.exit(1)

    # Determine which sources to export
    sources_to_export = []

    if args.all:
        # Export all sources
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT code FROM datawarp.tbl_data_sources")
            sources_to_export = [row[0] for row in cur.fetchall()]
        print(f"Exporting all {len(sources_to_export)} sources...")

    elif args.publication:
        # Use library function for publication export
        print(f"Exporting sources for publication '{args.publication}'...")
        results = export_publication_to_parquet(
            publication=args.publication,
            output_dir=args.output_dir,
            event_store=None,  # CLI doesn't use EventStore
            period=None
        )

        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        print("=" * 60)
        print(f"Exported {len(successful)} sources successfully")
        if failed:
            print(f"Failed to export {len(failed)} sources")

        total_rows = sum(r.row_count for r in successful)
        total_size = sum(r.parquet_size_mb for r in successful)

        print(f"Total rows: {total_rows:,}")
        print(f"Total size: {total_size:.2f} MB")
        print(f"Output directory: {Path(args.output_dir).absolute()}")

        sys.exit(0 if not failed else 1)

    else:
        sources_to_export = [args.source]

    # Export each source individually
    results = []
    for source_code in sources_to_export:
        result = export_source_to_parquet(
            canonical_code=source_code,
            output_dir=args.output_dir,
            event_store=None,  # CLI doesn't use EventStore
            publication=None,
            period=None
        )
        results.append(result)

        if result.success:
            print(f"  {source_code}: {result.row_count:,} rows, {result.parquet_size_mb:.2f} MB")
        else:
            print(f"  {source_code}: FAILED - {result.error}", file=sys.stderr)

    # Summary
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    print("=" * 60)
    print(f"Exported {len(successful)} sources successfully")
    if failed:
        print(f"Failed to export {len(failed)} sources")

    total_rows = sum(r.row_count for r in successful)
    total_size = sum(r.parquet_size_mb for r in successful)

    print(f"Total rows: {total_rows:,}")
    print(f"Total size: {total_size:.2f} MB")
    print(f"Output directory: {Path(args.output_dir).absolute()}")

    sys.exit(0 if not failed else 1)


if __name__ == '__main__':
    main()
