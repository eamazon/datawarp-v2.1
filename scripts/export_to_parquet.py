#!/usr/bin/env python3
"""Export DataWarp staging tables to Parquet format with metadata.

Exports entire staging tables (all periods) to single Parquet files with
companion .md metadata files for agent consumption.

Usage:
    python scripts/export_to_parquet.py SOURCE_CODE output/
    python scripts/export_to_parquet.py --all output/
    python scripts/export_to_parquet.py --publication adhd output/clinical/adhd/
"""
import sys
import os
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from datawarp.storage.connection import get_connection
from datawarp.storage import repository

load_dotenv()


def export_source_to_parquet(canonical_code: str, output_dir: str) -> dict:
    """Export a single source to Parquet + .md metadata.

    Args:
        canonical_code: Canonical source identifier
        output_dir: Output directory path

    Returns:
        Dict with export statistics
    """
    with get_connection() as conn:
        # 1. Get source info
        source = repository.get_source(canonical_code, conn)
        if not source:
            print(f"❌ Source '{canonical_code}' not found")
            return {'success': False, 'error': 'Source not found'}

        table_name = f"{source.schema_name}.{source.table_name}"

        # 2. Check if table exists
        cur = conn.cursor()
        cur.execute(f"""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
        """, (source.schema_name, source.table_name))

        if cur.fetchone()[0] == 0:
            print(f"❌ Table {table_name} does not exist")
            return {'success': False, 'error': 'Table not found'}

        # 3. Determine sort column for deterministic ordering
        # Check for common date/period columns, fallback to first column
        cur.execute(f"""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema || '.' || table_name = %s
            ORDER BY ordinal_position
            LIMIT 1
        """, (table_name,))
        first_column = cur.fetchone()
        sort_column = first_column[0] if first_column else None

        # 4. Read entire staging table (all periods) with deterministic sort
        print(f"📊 Exporting {table_name}...")
        if sort_column:
            df = pd.read_sql(f"SELECT * FROM {table_name} ORDER BY {sort_column}", conn)
        else:
            df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
        row_count = len(df)
        print(f"  → Read {row_count:,} rows from staging table (ordered by {sort_column})")

        # 5. Get ACTUAL column names from staging table
        cur.execute("""
            SELECT column_name, data_type, ordinal_position
            FROM information_schema.columns
            WHERE table_schema || '.' || table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        actual_columns = {row[0]: {'data_type': row[1], 'position': row[2]} for row in cur.fetchall()}

        # 6. Read enrichment metadata (semantic names)
        cur.execute("""
            SELECT column_name, original_name, description, data_type,
                   is_dimension, is_measure, query_keywords,
                   min_value, max_value, null_rate, distinct_count,
                   metadata_source, confidence
            FROM datawarp.tbl_column_metadata
            WHERE canonical_source_code = %s
        """, (canonical_code,))

        # Build metadata lookup by semantic name
        metadata_lookup = {}
        for row in cur.fetchall():
            metadata_lookup[row[0].lower()] = {
                'semantic_name': row[0],
                'original_name': row[1],
                'description': row[2],
                'data_type': row[3],
                'is_dimension': row[4],
                'is_measure': row[5],
                'query_keywords': row[6] or [],
                'min_value': row[7],
                'max_value': row[8],
                'null_rate': row[9],
                'distinct_count': row[10],
                'metadata_source': row[11],
                'confidence': float(row[12]) if row[12] else 0.70
            }

        # 7. Match actual columns with metadata (with fuzzy matching)
        def find_metadata_match(col_name: str, metadata_lookup: dict) -> dict:
            """Find best metadata match for a column name."""
            col_lower = col_name.lower()

            # Try exact match first
            if col_lower in metadata_lookup:
                return metadata_lookup[col_lower]

            # Try removing _val suffix from column name
            col_base = col_lower.replace('_val', '')
            if col_base in metadata_lookup:
                return metadata_lookup[col_base]

            # Try with common suffixes added
            for suffix in ['_referral_count', '_new_referral_count', '_age_referral_count', '_count', '_val']:
                if col_lower + suffix in metadata_lookup:
                    return metadata_lookup[col_lower + suffix]

            # Try removing common prefixes/suffixes from both sides
            for meta_key in metadata_lookup:
                # Strip various patterns
                stripped_meta = meta_key
                stripped_col = col_lower

                # Remove common suffixes
                for suffix in ['_referral_count', '_age_referral_count', '_new_referral_count', '_count', '_val']:
                    if stripped_meta.endswith(suffix):
                        stripped_meta = stripped_meta[:-len(suffix)]
                    if stripped_col.endswith(suffix):
                        stripped_col = stripped_col[:-len(suffix)]

                # Remove common prefixes
                for prefix in ['total_', 'unknown_']:
                    if stripped_meta.startswith(prefix):
                        stripped_meta = stripped_meta[len(prefix):]
                    if stripped_col.startswith(prefix):
                        stripped_col = stripped_col[len(prefix):]

                # Check if they match now
                if stripped_meta == stripped_col:
                    return metadata_lookup[meta_key]

                # Special case: age_25 vs age_25_plus
                if col_lower == 'age_25' and 'age_25_plus' in meta_key:
                    return metadata_lookup[meta_key]
                if col_lower.replace('_plus', '') in meta_key:
                    return metadata_lookup[meta_key]

            return None

        column_metadata = []
        for col_name in sorted(actual_columns.keys(), key=lambda x: actual_columns[x]['position']):
            # Try to find metadata match
            meta = find_metadata_match(col_name, metadata_lookup)

            # System column descriptions
            system_col_descriptions = {
                '_load_id': 'Unique identifier for the batch load that created this row',
                '_loaded_at': 'Timestamp when this row was loaded into DataWarp',
                '_period': 'Period identifier for this data (format: YYYY-MM)',
                '_manifest_file_id': 'Reference to the manifest file that sourced this data'
            }

            # Build column info
            col_info = {
                'column_name': col_name,  # Actual queryable name
                'original_name': meta.get('original_name') if meta else None,
                'description': meta.get('description') if meta else system_col_descriptions.get(col_name, 'System column'),
                'data_type': actual_columns[col_name]['data_type'],
                'is_dimension': meta.get('is_dimension', False) if meta else False,
                'is_measure': meta.get('is_measure', False) if meta else False,
                'query_keywords': meta.get('query_keywords', []) if meta else [],
                'min_value': meta.get('min_value') if meta else None,
                'max_value': meta.get('max_value') if meta else None,
                'null_rate': meta.get('null_rate') if meta else None,
                'distinct_count': meta.get('distinct_count') if meta else None,
                'metadata_source': meta.get('metadata_source', 'system') if meta else 'system',
                'confidence': meta.get('confidence', 1.00) if meta else 1.00
            }

            # Mark system columns
            if col_name.startswith('_'):
                col_info['is_system'] = True

            column_metadata.append(col_info)

        enriched_count = sum(1 for c in column_metadata if c['metadata_source'] == 'llm')
        print(f"  → Mapped {len(column_metadata)} columns ({enriched_count} with LLM metadata)")

        # 8. Read source-level metadata and enrich with actual table info
        # Get date range from actual data
        if sort_column:
            cur.execute(f"SELECT MIN({sort_column}), MAX({sort_column}) FROM {table_name}")
            date_range = cur.fetchone()
            first_date, last_date = date_range if date_range else (None, None)
        else:
            first_date, last_date = None, None

        # 9. Read source-level metadata from canonical registry
        cur.execute("""
            SELECT canonical_name, fingerprint, first_seen_period, last_seen_period,
                   total_loads, total_rows_loaded, description, metadata, domain
            FROM datawarp.tbl_canonical_sources
            WHERE canonical_code = %s
        """, (canonical_code,))

        source_meta_row = cur.fetchone()
        source_metadata = {}
        if source_meta_row:
            source_metadata = {
                'canonical_name': source_meta_row[0],
                'first_seen_period': source_meta_row[2],
                'last_seen_period': source_meta_row[3],
                'total_loads': source_meta_row[4],
                'total_rows_loaded': source_meta_row[5],
                'description': source_meta_row[6],
                'metadata': source_meta_row[7] or {},
                'domain': source_meta_row[8]
            }

        # Enrich with actual data from table
        source_metadata['actual_row_count'] = row_count
        source_metadata['actual_first_date'] = str(first_date) if first_date else None
        source_metadata['actual_last_date'] = str(last_date) if last_date else None

        # Default domain if missing
        if not source_metadata.get('domain'):
            # Infer from table name
            if 'adhd' in canonical_code.lower():
                source_metadata['domain'] = 'Clinical - Mental Health'
            else:
                source_metadata['domain'] = 'Unknown'

        # 10. Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # 11. Write Parquet file
        parquet_path = Path(output_dir) / f"{canonical_code}.parquet"
        df.to_parquet(parquet_path, index=False, engine='pyarrow', compression='snappy')
        file_size_mb = parquet_path.stat().st_size / 1024 / 1024
        print(f"  → Wrote {parquet_path} ({file_size_mb:.2f} MB)")

        # 12. Generate .md metadata file
        md_path = Path(output_dir) / f"{canonical_code}.md"
        md_content = generate_metadata_markdown(
            canonical_code=canonical_code,
            source_name=source.name,
            source_metadata=source_metadata,
            column_metadata=column_metadata,
            row_count=row_count
        )

        with open(md_path, 'w') as f:
            f.write(md_content)
        print(f"  → Wrote {md_path}")

        return {
            'success': True,
            'canonical_code': canonical_code,
            'row_count': row_count,
            'column_count': len(column_metadata),
            'parquet_size_mb': file_size_mb,
            'parquet_path': str(parquet_path),
            'metadata_path': str(md_path)
        }


def generate_metadata_markdown(canonical_code: str, source_name: str,
                                source_metadata: dict, column_metadata: list,
                                row_count: int) -> str:
    """Generate human-readable metadata markdown."""

    md = f"""# {source_name}

**Dataset:** `{canonical_code}`
**Domain:** {source_metadata.get('domain', 'Unknown')}
**Rows:** {row_count:,}
**Columns:** {len(column_metadata)}

---

## Purpose

{source_metadata.get('description', 'No description available.')}

---

## Coverage

- **Date Range:** {source_metadata.get('actual_first_date', 'N/A')} to {source_metadata.get('actual_last_date', 'N/A')}
- **Rows in Export:** {source_metadata.get('actual_row_count', row_count):,}
- **Load History:** {source_metadata.get('total_loads', 0)} loads, {source_metadata.get('total_rows_loaded', 0):,} total rows
- **Geographic Scope:** NHS Wales (All Health Boards)

---

## Columns

"""

    # Group columns by type
    dimensions = [c for c in column_metadata if c['is_dimension']]
    measures = [c for c in column_metadata if c['is_measure']]
    system_cols = [c for c in column_metadata if c.get('is_system', False)]
    other_cols = [c for c in column_metadata if not c['is_dimension'] and not c['is_measure'] and not c.get('is_system', False)]

    if dimensions:
        md += "### Dimensions (Grouping Columns)\n\n"
        for col in dimensions:
            md += format_column_markdown(col)

    if measures:
        md += "\n### Measures (Numeric Metrics)\n\n"
        for col in measures:
            md += format_column_markdown(col)

    if other_cols:
        md += "\n### Other Columns\n\n"
        for col in other_cols:
            md += format_column_markdown(col)

    if system_cols:
        md += "\n### System Columns (DataWarp Audit Trail)\n\n"
        md += "These columns are automatically added by DataWarp for data lineage and audit purposes.\n\n"
        for col in system_cols:
            md += format_column_markdown(col)

    # Add metadata info
    metadata = source_metadata.get('metadata', {})
    if metadata:
        md += "\n---\n\n## Additional Metadata\n\n"
        if 'record_type' in metadata:
            md += f"- **Record Type:** {metadata['record_type']}\n"
        if 'granularity' in metadata:
            md += f"- **Granularity:** {metadata['granularity']}\n"
        if 'tags' in metadata:
            md += f"- **Tags:** {', '.join(metadata['tags'])}\n"

    # Add generation timestamp
    md += f"\n---\n\n*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
    md += "*Source: DataWarp v2.1*\n"

    return md


def format_column_markdown(col: dict) -> str:
    """Format single column metadata as markdown."""
    md = f"#### `{col['column_name']}`\n\n"

    if col['original_name'] and col['original_name'] != col['column_name']:
        md += f"**Original Name:** {col['original_name']}  \n"

    md += f"**Type:** {col['data_type']}  \n"

    if col['description']:
        md += f"**Description:** {col['description']}  \n"

    # Add range if numeric
    if col['min_value'] is not None and col['max_value'] is not None:
        md += f"**Range:** {col['min_value']} to {col['max_value']}  \n"

    if col['null_rate'] is not None:
        md += f"**Null Rate:** {col['null_rate']:.1f}%  \n"

    if col['distinct_count'] is not None:
        md += f"**Distinct Values:** {col['distinct_count']:,}  \n"

    if col['query_keywords']:
        keywords = ', '.join(col['query_keywords'])
        md += f"**Search Terms:** {keywords}  \n"

    # Metadata quality indicator
    confidence = col.get('confidence', 0.70)
    source = col.get('metadata_source', 'llm')
    quality_icon = "✓" if confidence >= 0.90 else "~"
    md += f"**Metadata Quality:** {quality_icon} {source} (confidence: {confidence:.2f})  \n"

    md += "\n"
    return md


def main():
    import argparse

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
        print(f"📦 Exporting all {len(sources_to_export)} sources...")

    elif args.publication:
        # Export sources matching publication prefix
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT code FROM datawarp.tbl_data_sources WHERE code LIKE %s",
                (f"{args.publication}%",)
            )
            sources_to_export = [row[0] for row in cur.fetchall()]
        print(f"📦 Exporting {len(sources_to_export)} sources for publication '{args.publication}'...")

    else:
        sources_to_export = [args.source]

    # Export each source
    results = []
    for source_code in sources_to_export:
        result = export_source_to_parquet(source_code, args.output_dir)
        results.append(result)
        print()

    # Summary
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]

    print("=" * 60)
    print(f"✅ Exported {len(successful)} sources successfully")
    if failed:
        print(f"❌ Failed to export {len(failed)} sources")

    total_rows = sum(r.get('row_count', 0) for r in successful)
    total_size = sum(r.get('parquet_size_mb', 0) for r in successful)

    print(f"📊 Total rows: {total_rows:,}")
    print(f"💾 Total size: {total_size:.2f} MB")
    print(f"📁 Output directory: {Path(args.output_dir).absolute()}")


if __name__ == '__main__':
    main()
