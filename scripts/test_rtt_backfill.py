#!/usr/bin/env python3
"""
RTT Provider Backfill Test with Detailed Timing Monitoring

Tests intelligent adaptive sampling on RTT provider data with comprehensive
timing metrics for every function.
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


# RTT Provider URLs (incomplete pathways by provider)
RTT_URLS = {
    "apr25": "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2025/06/Incomplete-Provider-Apr25-XLSX-9M-77252.xlsx",
    "may25": "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2025/07/Incomplete-Provider-May25-XLSX-9M-32711.xlsx",
    "jun25": "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2025/08/Incomplete-Provider-Jun25-XLSX-9M-94367.xlsx",
}


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


def test_rtt_period(period: str, url: str, output_dir: Path, reference_path: str = None) -> dict:
    """Test a single RTT period with detailed timing."""
    print(f"\n{'='*80}")
    print(f"RTT PROVIDER: {period.upper()}")
    print(f"{'='*80}")
    print(f"URL: {url}")
    if reference_path:
        ref_name = Path(reference_path).name
        print(f"Reference: {ref_name}")
    else:
        print(f"Reference: None (fresh baseline)")
    print()

    timings = {}
    metrics = {
        'period': period,
        'url': url,
        'success': False
    }

    # Paths
    draft_manifest = output_dir / f"rtt_provider_{period}.yaml"
    enriched_manifest = output_dir / f"rtt_provider_{period}_enriched.yaml"

    # Step 1: Generate manifest
    print("1. Generating manifest...")
    print(f"   Output: {draft_manifest.name}")

    start = time.time()
    result = generate_manifest(url, draft_manifest)
    timings['manifest_generation'] = time.time() - start

    if not result.success:
        print(f"   ❌ FAILED: {result.error}")
        print(f"   Time: {format_duration(timings['manifest_generation'])}")
        metrics['error'] = result.error
        metrics['timings'] = timings
        return metrics

    print(f"   ✅ SUCCESS")
    print(f"   Time: {format_duration(timings['manifest_generation'])}")
    print(f"   Sources: {result.sources_count}")
    metrics['sources_generated'] = result.sources_count

    # Check adaptive sampling activation
    import yaml
    with open(draft_manifest) as f:
        manifest_data = yaml.safe_load(f)

    first_source = manifest_data['sources'][0]
    if 'files' in first_source and first_source['files']:
        first_file = first_source['files'][0]
        if 'preview' in first_file:
            total_cols = len(first_file['preview']['columns'])
            sample_rows = first_file['preview'].get('sample_rows', [])
            sampled_cols = len(sample_rows[0].keys()) if sample_rows else 0

            print(f"   Columns: {total_cols} total, {sampled_cols} sampled ({100*sampled_cols/total_cols:.1f}%)")
            metrics['total_columns'] = total_cols
            metrics['sampled_columns'] = sampled_cols
            metrics['sampling_reduction'] = 100 * (1 - sampled_cols/total_cols)

    # Step 2: Enrich manifest
    print("\n2. Enriching manifest...")
    print(f"   Output: {enriched_manifest.name}")
    if reference_path:
        print(f"   Using reference: {Path(reference_path).name}")

    start = time.time()
    enrich_result = enrich_manifest(
        input_path=str(draft_manifest),
        output_path=str(enriched_manifest),
        reference_path=reference_path
    )
    timings['enrichment'] = time.time() - start

    if not enrich_result.success:
        print(f"   ❌ FAILED: {enrich_result.error}")
        print(f"   Time: {format_duration(timings['enrichment'])}")
        metrics['error'] = enrich_result.error
        metrics['timings'] = timings
        return metrics

    print(f"   ✅ SUCCESS")
    print(f"   Time: {format_duration(timings['enrichment'])}")
    print(f"   Sources enriched: {enrich_result.sources_enriched}")
    print(f"   Input tokens: {enrich_result.input_tokens:,}")
    print(f"   Output tokens: {enrich_result.output_tokens:,}")

    # Calculate cost (Gemini 2.0 Flash pricing: $0.001/1M input, $0.004/1M output)
    cost = (enrich_result.input_tokens * 0.000001) + (enrich_result.output_tokens * 0.000004)
    print(f"   Cost: ${cost:.4f}")

    metrics['sources_enriched'] = enrich_result.sources_enriched
    metrics['input_tokens'] = enrich_result.input_tokens
    metrics['output_tokens'] = enrich_result.output_tokens
    metrics['cost'] = cost

    # Step 2.5: Canonicalize codes (remove date/filename patterns)
    print("\n2.5. Canonicalizing source codes...")
    canonical_manifest = output_dir / f"rtt_provider_{period}_canonical.yaml"

    try:
        with open(enriched_manifest) as f:
            manifest_data = yaml.safe_load(f)

        canonical_data = canonicalize_manifest(manifest_data)

        with open(canonical_manifest, 'w') as f:
            yaml.dump(canonical_data, f, sort_keys=False)

        print(f"   ✅ SUCCESS")
        print(f"   Output: {canonical_manifest.name}")

        # Use canonical manifest for loading
        enriched_manifest = canonical_manifest

    except Exception as e:
        print(f"   ⚠️  WARNING: {str(e)}")
        print(f"   Continuing with enriched manifest")

    # Step 3: Load to database
    print("\n3. Loading to database...")

    start = time.time()
    batch_stats = load_from_manifest(
        manifest_path=str(enriched_manifest),
        force_reload=False,
        quiet=True
    )
    timings['database_load'] = time.time() - start

    print(f"   ✅ COMPLETE")
    print(f"   Time: {format_duration(timings['database_load'])}")
    print(f"   Sources loaded: {batch_stats.loaded}")
    print(f"   Total rows: {batch_stats.total_rows:,}")
    print(f"   Columns added: {batch_stats.total_columns}")
    print(f"   Skipped: {batch_stats.skipped}")
    print(f"   Failed: {batch_stats.failed}")

    metrics['sources_loaded'] = batch_stats.loaded
    metrics['total_rows'] = batch_stats.total_rows
    metrics['columns_added'] = batch_stats.total_columns
    metrics['sources_skipped'] = batch_stats.skipped
    metrics['sources_failed'] = batch_stats.failed

    # Step 4: Per-source breakdown
    if hasattr(batch_stats, 'file_results') and batch_stats.file_results:
        print("\n4. Per-Source Breakdown:")
        print(f"   {'Source':<40} {'Rows':>10} {'Time':>10} {'Status':<10}")
        print(f"   {'-'*75}")

        source_details = []
        for file_result in batch_stats.file_results:
            status_icon = {
                'loaded': '✅',
                'skipped': '⏭️',
                'failed': '❌'
            }.get(file_result.status, '?')

            print(f"   {file_result.source_code[:40]:<40} "
                  f"{file_result.rows:>10,} "
                  f"{format_duration(file_result.duration):>10} "
                  f"{status_icon} {file_result.status:<10}")

            source_details.append({
                'source_code': file_result.source_code,
                'rows': file_result.rows,
                'duration': file_result.duration,
                'status': file_result.status,
                'new_columns': file_result.new_cols
            })

        metrics['source_details'] = source_details

    # Total timing
    timings['total'] = sum(timings.values())
    metrics['timings'] = timings
    metrics['success'] = True

    print(f"\n{'='*80}")
    print("TIMING SUMMARY")
    print(f"{'='*80}")
    print(f"  Manifest generation: {format_duration(timings['manifest_generation']):>12}")
    print(f"  Enrichment:          {format_duration(timings['enrichment']):>12}")
    print(f"  Database load:       {format_duration(timings['database_load']):>12}")
    print(f"  {'-'*80}")
    print(f"  Total:               {format_duration(timings['total']):>12}")
    print(f"{'='*80}")

    return metrics


def main():
    """Run RTT provider backfill test."""
    print("\n" + "="*80)
    print("RTT PROVIDER BACKFILL TEST")
    print("Intelligent Adaptive Sampling + Detailed Timing Monitoring")
    print("="*80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Create output directory
    output_dir = Path("manifests/test/rtt_backfill")
    output_dir.mkdir(parents=True, exist_ok=True)

    all_metrics = []
    successful = 0
    failed = 0

    # Process each period with automatic reference detection
    for period, url in RTT_URLS.items():
        # Determine reference (April is baseline, others use April)
        if period == "apr25":
            reference_path = None  # Fresh baseline
        else:
            # Use April as reference
            april_enriched = output_dir / "rtt_provider_apr25_enriched.yaml"
            if april_enriched.exists():
                reference_path = str(april_enriched)
            else:
                print(f"\n⚠️  April baseline not found, loading {period} fresh")
                reference_path = None

        try:
            metrics = test_rtt_period(period, url, output_dir, reference_path)
            all_metrics.append(metrics)

            if metrics['success']:
                successful += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ EXCEPTION: {str(e)}")
            import traceback
            traceback.print_exc()
            failed += 1
            all_metrics.append({
                'period': period,
                'url': url,
                'success': False,
                'error': str(e)
            })

    # Final summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    print(f"Periods tested: {len(RTT_URLS)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print()

    if successful > 0:
        # Aggregate metrics
        total_rows = sum(m.get('total_rows', 0) for m in all_metrics if m['success'])
        total_sources = sum(m.get('sources_loaded', 0) for m in all_metrics if m['success'])
        total_cost = sum(m.get('cost', 0) for m in all_metrics if m['success'])
        avg_sampling_reduction = sum(m.get('sampling_reduction', 0) for m in all_metrics if m['success']) / successful

        print(f"Total rows loaded: {total_rows:,}")
        print(f"Total sources loaded: {total_sources}")
        print(f"Total cost: ${total_cost:.4f}")
        print(f"Average sampling reduction: {avg_sampling_reduction:.1f}%")
        print()

        # Compare baseline vs reference-based enrichment
        baseline_metrics = [m for m in all_metrics if m['success'] and m['period'] == 'apr25']
        reference_metrics = [m for m in all_metrics if m['success'] and m['period'] != 'apr25']

        if baseline_metrics and reference_metrics:
            print("Baseline vs Reference-Based Comparison:")
            baseline = baseline_metrics[0]
            avg_ref_cost = sum(m.get('cost', 0) for m in reference_metrics) / len(reference_metrics)
            avg_ref_tokens = sum(m.get('input_tokens', 0) for m in reference_metrics) / len(reference_metrics)
            avg_ref_time = sum(m['timings']['enrichment'] for m in reference_metrics) / len(reference_metrics)

            print(f"  April (baseline):    ${baseline.get('cost', 0):.4f}, {baseline.get('input_tokens', 0):,} tokens, {format_duration(baseline['timings']['enrichment'])}")
            print(f"  May+ (reference):    ${avg_ref_cost:.4f}, {int(avg_ref_tokens):,} tokens, {format_duration(avg_ref_time)}")
            print(f"  Savings per month:   ${baseline.get('cost', 0) - avg_ref_cost:.4f} ({100*(baseline.get('cost', 0) - avg_ref_cost)/baseline.get('cost', 0):.1f}%)")
            print()

        # Timing breakdown
        print("Average Timings:")
        avg_manifest = sum(m['timings']['manifest_generation'] for m in all_metrics if m['success']) / successful
        avg_enrich = sum(m['timings']['enrichment'] for m in all_metrics if m['success']) / successful
        avg_load = sum(m['timings']['database_load'] for m in all_metrics if m['success']) / successful
        avg_total = sum(m['timings']['total'] for m in all_metrics if m['success']) / successful

        print(f"  Manifest generation: {format_duration(avg_manifest)}")
        print(f"  Enrichment:          {format_duration(avg_enrich)}")
        print(f"  Database load:       {format_duration(avg_load)}")
        print(f"  Total:               {format_duration(avg_total)}")

    print("="*80)
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
