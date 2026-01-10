#!/usr/bin/env python3
"""Rebuild catalog.parquet from all individual parquet files in output/.

This scans the output directory, reads metadata from each parquet file,
and builds a master catalog.parquet index for the MCP server.
"""
import pandas as pd
from pathlib import Path
import sys

def rebuild_catalog(output_dir="output"):
    """Rebuild catalog from all parquet files in directory."""
    output_path = Path(output_dir)

    catalog_entries = []

    for parquet_file in sorted(output_path.glob("*.parquet")):
        # Skip catalog.parquet itself
        if parquet_file.name == "catalog.parquet":
            continue

        try:
            # Read parquet file to get metadata
            df = pd.read_parquet(parquet_file)

            source_code = parquet_file.stem
            md_path = output_path / f"{source_code}.md"

            # Extract date range if possible
            date_cols = [col for col in df.columns if 'date' in col.lower() or 'period' in col.lower()]
            min_date = None
            max_date = None
            if date_cols:
                try:
                    dates = pd.to_datetime(df[date_cols[0]], errors='coerce').dropna()
                    if len(dates) > 0:
                        min_date = dates.min()
                        max_date = dates.max()
                except:
                    pass

            catalog_entries.append({
                'source_code': source_code,
                'domain': 'nhs',  # Could be extracted from manifest
                'description': f'DataWarp source: {source_code}',
                'row_count': len(df),
                'column_count': len(df.columns),
                'file_size_kb': round(parquet_file.stat().st_size / 1024, 2),
                'min_date': min_date,
                'max_date': max_date,
                'file_path': str(parquet_file),
                'md_path': str(md_path) if md_path.exists() else None
            })

            print(f"✓ {source_code:50} {len(df):>10,} rows")

        except Exception as e:
            print(f"✗ {parquet_file.name}: {e}")

    # Build catalog dataframe
    catalog_df = pd.DataFrame(catalog_entries)

    # Write catalog
    catalog_path = output_path / "catalog.parquet"
    catalog_df.to_parquet(catalog_path, index=False)

    print(f"\n✅ Catalog rebuilt: {len(catalog_entries)} sources")
    print(f"📁 Written to: {catalog_path}")
    print(f"📊 Total rows: {catalog_df['row_count'].sum():,}")

    return catalog_df

if __name__ == "__main__":
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "output"
    rebuild_catalog(output_dir)
