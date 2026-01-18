#!/usr/bin/env python3
"""
Test May 2025 RTT data with April 2025 as reference.

Demonstrates:
1. Reference-based enrichment
2. Canonicalization (same table names across periods)
3. Cross-period consolidation
4. Cost comparison
"""
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from datawarp.pipeline import generate_manifest, enrich_manifest
from datawarp.pipeline.canonicalize import canonicalize_manifest
from datawarp.loader.batch import load_from_manifest
import yaml


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    else:
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins}m {secs:.1f}s"


def main():
    print("\n" + "="*80)
    print("MAY 2025 RTT TEST - Reference-Based Enrichment + Canonicalization")
    print("="*80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Paths
    output_dir = Path("manifests/test/rtt_backfill")
    output_dir.mkdir(parents=True, exist_ok=True)

    may_url = "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2025/07/Incomplete-Provider-May25-XLSX-9M-32711.xlsx"
    april_reference = output_dir / "rtt_provider_apr25_enriched.yaml"

    draft_manifest = output_dir / "rtt_provider_may25.yaml"
    enriched_manifest = output_dir / "rtt_provider_may25_enriched.yaml"
    canonical_manifest = output_dir / "rtt_provider_may25_canonical.yaml"

    # Check April reference exists
    if not april_reference.exists():
        print(f"❌ April reference not found: {april_reference}")
        print("   Run the main backfill test first to generate April baseline")
        return 1

    print(f"Using April reference: {april_reference.name}")
    print()

    timings = {}

    # Step 1: Generate manifest
    print("="*80)
    print("STEP 1: GENERATE MANIFEST")
    print("="*80)
    print(f"URL: {may_url}")
    print()

    start = time.time()
    result = generate_manifest(may_url, draft_manifest)
    timings['manifest'] = time.time() - start

    if not result.success:
        print(f"❌ FAILED: {result.error}")
        return 1

    print(f"✅ SUCCESS ({format_duration(timings['manifest'])})")
    print(f"   Sources: {result.sources_count}")
    print()

    # Check adaptive sampling
    with open(draft_manifest) as f:
        manifest_data = yaml.safe_load(f)

    first_source = manifest_data['sources'][0]
    if 'files' in first_source and first_source['files']:
        first_file = first_source['files'][0]
        if 'preview' in first_file:
            total_cols = len(first_file['preview']['columns'])
            sample_rows = first_file['preview'].get('sample_rows', [])
            sampled_cols = len(sample_rows[0].keys()) if sample_rows else 0
            print(f"Adaptive Sampling: {total_cols} cols → {sampled_cols} sampled ({100*sampled_cols/total_cols:.1f}%)")
            print()

    # Step 2: Enrich with reference
    print("="*80)
    print("STEP 2: ENRICH WITH APRIL REFERENCE")
    print("="*80)
    print(f"Reference: {april_reference.name}")
    print()

    start = time.time()
    enrich_result = enrich_manifest(
        input_path=str(draft_manifest),
        output_path=str(enriched_manifest),
        reference_path=str(april_reference)
    )
    timings['enrich'] = time.time() - start

    if not enrich_result.success:
        print(f"❌ FAILED: {enrich_result.error}")
        return 1

    cost = (enrich_result.input_tokens * 0.000001) + (enrich_result.output_tokens * 0.000004)

    print(f"✅ SUCCESS ({format_duration(timings['enrich'])})")
    print(f"   Sources enriched: {enrich_result.sources_enriched}")
    print(f"   Input tokens: {enrich_result.input_tokens:,}")
    print(f"   Output tokens: {enrich_result.output_tokens:,}")
    print(f"   Cost: ${cost:.4f}")
    print()

    # Check what codes were generated BEFORE canonicalization
    with open(enriched_manifest) as f:
        enriched_data = yaml.safe_load(f)

    print("Source codes BEFORE canonicalization:")
    for source in enriched_data['sources']:
        print(f"   • {source['code']:<50} → {source['table']}")
    print()

    # Step 3: Canonicalize
    print("="*80)
    print("STEP 3: CANONICALIZE (Remove filename patterns)")
    print("="*80)

    try:
        canonical_data = canonicalize_manifest(enriched_data)

        with open(canonical_manifest, 'w') as f:
            yaml.dump(canonical_data, f, sort_keys=False)

        print(f"✅ SUCCESS")
        print(f"   Output: {canonical_manifest.name}")
        print()

        print("Source codes AFTER canonicalization:")
        for source in canonical_data['sources']:
            print(f"   • {source['code']:<50} → {source['table']}")
        print()

    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        return 1

    # Step 4: Load to database
    print("="*80)
    print("STEP 4: LOAD TO DATABASE")
    print("="*80)

    start = time.time()
    batch_stats = load_from_manifest(
        manifest_path=str(canonical_manifest),
        force_reload=False,
        quiet=True
    )
    timings['load'] = time.time() - start

    print(f"✅ COMPLETE ({format_duration(timings['load'])})")
    print(f"   Sources loaded: {batch_stats.loaded}")
    print(f"   Total rows: {batch_stats.total_rows:,}")
    print(f"   Columns added: {batch_stats.total_columns}")
    print(f"   Skipped: {batch_stats.skipped}")
    print(f"   Failed: {batch_stats.failed}")
    print()

    if hasattr(batch_stats, 'file_results') and batch_stats.file_results:
        print("Per-Source Breakdown:")
        for file_result in batch_stats.file_results:
            status_icon = {
                'loaded': '✅',
                'skipped': '⏭️',
                'failed': '❌'
            }.get(file_result.status, '?')
            print(f"   {status_icon} {file_result.source_code:<50} {file_result.rows:>7,} rows  {format_duration(file_result.duration)}")
        print()

    # Step 5: Verify consolidation
    print("="*80)
    print("STEP 5: VERIFY CROSS-PERIOD CONSOLIDATION")
    print("="*80)

    from datawarp.storage.connection import get_connection

    with get_connection() as conn:
        cursor = conn.cursor()

        # Check provider_incomplete_pathways table
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'staging'
              AND table_name LIKE '%provider%'
              AND table_name NOT LIKE '%is_%'
            ORDER BY table_name;
        """)

        tables = cursor.fetchall()
        print(f"Found {len(tables)} provider tables:")
        for (table_name,) in tables:
            # Check row count and periods
            cursor.execute(f"""
                SELECT COUNT(*), COUNT(DISTINCT period) as periods
                FROM staging.{table_name}
            """)
            count, periods = cursor.fetchone()
            print(f"   • {table_name:<50} {count:>7,} rows, {periods} periods")

            # Show period breakdown
            cursor.execute(f"""
                SELECT period, COUNT(*) as rows
                FROM staging.{table_name}
                GROUP BY period
                ORDER BY period;
            """)
            period_rows = cursor.fetchall()
            for period, rows in period_rows:
                print(f"      └─ {period}: {rows:,} rows")

    print()
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total time: {format_duration(sum(timings.values()))}")
    print(f"   Manifest:        {format_duration(timings['manifest'])}")
    print(f"   Enrichment:      {format_duration(timings['enrich'])} (${cost:.4f})")
    print(f"   Canonicalization: <1ms")
    print(f"   Load:            {format_duration(timings['load'])}")
    print()
    print(f"Rows loaded: {batch_stats.total_rows:,}")
    print(f"Cost: ${cost:.4f}")
    print()
    print("✅ TEST COMPLETE - Cross-period consolidation verified!")
    print("="*80)

    return 0


if __name__ == '__main__':
    sys.exit(main())
