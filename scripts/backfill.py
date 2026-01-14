#!/usr/bin/env python3
"""
DataWarp Backfill Script (v2.2 with EventStore)

Simple system to process historical NHS data and monitor for new releases.
Reads config/publications.yaml, processes pending URLs, tracks state in state/state.json.

Usage:
    python scripts/backfill.py                                    # Process all pending
    python scripts/backfill.py --config config/test.yaml          # Use custom config
    python scripts/backfill.py --pub adhd                         # Process one publication
    python scripts/backfill.py --dry-run                          # Show what would be processed
    python scripts/backfill.py --status                           # Show current status
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from datawarp.pipeline import generate_manifest, enrich_manifest, export_publication_to_parquet
from datawarp.pipeline.canonicalize import canonicalize_manifest
from datawarp.loader.batch import load_from_manifest
from datawarp.supervisor.events import EventStore, EventType, EventLevel, create_event
from datawarp.cli.display import ProgressDisplay, PeriodResult, SourceResult


PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_FILE = PROJECT_ROOT / "config" / "publications.yaml"
STATE_FILE = PROJECT_ROOT / "state" / "state.json"
MANIFESTS_DIR = PROJECT_ROOT / "manifests" / "backfill"
LOGS_DIR = PROJECT_ROOT / "logs"


def load_config(config_path: Path = None) -> dict:
    """Load publications config."""
    config_file = config_path if config_path else CONFIG_FILE
    if not config_file.exists():
        print(f"Config file not found: {config_file}")
        sys.exit(1)
    return yaml.safe_load(config_file.read_text())


def load_state() -> dict:
    """Load processing state."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"processed": {}, "failed": {}}


def save_state(state: dict):
    """Save processing state."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


def is_processed(state: dict, pub_code: str, period: str) -> bool:
    """Check if a period has already been processed."""
    key = f"{pub_code}/{period}"
    return key in state.get("processed", {})


def mark_processed(state: dict, pub_code: str, period: str, rows: int = 0):
    """Mark a period as processed."""
    key = f"{pub_code}/{period}"
    state.setdefault("processed", {})[key] = {
        "completed_at": datetime.now().isoformat(),
        "rows_loaded": rows
    }
    save_state(state)


def mark_failed(state: dict, pub_code: str, period: str, error: str):
    """Mark a period as failed."""
    key = f"{pub_code}/{period}"
    state.setdefault("failed", {})[key] = {
        "failed_at": datetime.now().isoformat(),
        "error": error
    }
    save_state(state)


def get_fiscal_year_april(period: str) -> str:
    """Get the April period for the fiscal year.

    NHS fiscal year runs April-March.
    Examples:
        nov25 → apr25 (FY 2025/26)
        mar26 → apr25 (FY 2025/26)
        apr26 → apr26 (FY 2026/27, new baseline)
    """
    # Parse period (e.g., "nov25" → month=11, year=25)
    month_str = period[:3]
    year_str = period[3:]

    months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
              'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
    month_num = months.index(month_str) + 1

    # If month is Jan-Mar, fiscal year started previous April
    if month_num <= 3:
        # Decrement year for April
        year_int = int(year_str)
        april_year = year_int - 1
        return f"apr{april_year:02d}"
    else:
        # Fiscal year starts this April
        return f"apr{year_str}"


def find_reference_manifest(pub_code: str, period: str, manual_reference: str = None) -> str:
    """Find the best reference manifest for a period.

    Priority:
    1. Manual reference (if provided via --reference flag)
    2. April reference for this fiscal year (e.g., adhd_apr25_enriched.yaml)
    3. Most recent enriched manifest
    4. None (fresh LLM enrichment)

    Args:
        pub_code: Publication code (e.g., "adhd")
        period: Period being loaded (e.g., "nov25")
        manual_reference: Manually specified reference path

    Returns:
        Path to reference manifest or None
    """
    # Manual override
    if manual_reference:
        ref_path = Path(manual_reference)
        if ref_path.exists():
            return str(ref_path)
        print(f"⚠️  Specified reference not found: {manual_reference}")
        return None

    # Special case: April is always baseline (never references)
    if period.startswith('apr'):
        return None

    # Look for April reference first
    april_period = get_fiscal_year_april(period)
    production_dir = PROJECT_ROOT / "manifests" / "production" / pub_code
    backfill_dir = MANIFESTS_DIR / pub_code

    # Check production directory for April
    april_prod = production_dir / f"{pub_code}_{april_period}_enriched.yaml"
    if april_prod.exists():
        return str(april_prod)

    # Check backfill directory for April
    april_backfill = backfill_dir / f"{pub_code}_{april_period}_enriched.yaml"
    if april_backfill.exists():
        return str(april_backfill)

    # Fall back to most recent enriched manifest
    enriched_manifests = []

    # Check production directory
    if production_dir.exists():
        enriched_manifests.extend(production_dir.glob(f"{pub_code}_*_enriched.yaml"))

    # Check backfill directory
    if backfill_dir.exists():
        enriched_manifests.extend(backfill_dir.glob(f"{pub_code}_*_enriched.yaml"))

    if enriched_manifests:
        # Use most recent (by modification time)
        most_recent = max(enriched_manifests, key=lambda p: p.stat().st_mtime)
        return str(most_recent)

    # No reference found
    return None


def process_period(
    pub_code: str,
    pub_config: dict,
    period: str,
    url: str,
    event_store: EventStore,
    dry_run: bool = False,
    force: bool = False,
    manual_reference: str = None,
    no_reference: bool = False,
    display: Optional['ProgressDisplay'] = None
) -> tuple[bool, dict]:
    """Process a single period for a publication."""
    from datetime import datetime
    from datawarp.cli.display import SourceResult, PeriodResult

    stage_timings = {}  # Track timing for each stage
    warnings = []  # Collect warnings

    # Start period progress
    if display:
        display.start_period(period)

    event_store.emit(create_event(
        EventType.PERIOD_STARTED,
        event_store.run_id,
        message=f"Processing {pub_code}/{period}",
        publication=pub_code,
        period=period,
        url=url
    ))

    if dry_run:
        event_store.emit(create_event(
            EventType.PERIOD_COMPLETED,
            event_store.run_id,
            message="Dry run completed",
            publication=pub_code,
            period=period
        ))
        return True

    # Create manifest directory
    manifest_dir = MANIFESTS_DIR / pub_code
    manifest_dir.mkdir(parents=True, exist_ok=True)

    draft_manifest = manifest_dir / f"{pub_code}_{period}.yaml"
    enriched_manifest = manifest_dir / f"{pub_code}_{period}_enriched.yaml"

    # Step 1: Generate manifest (using library)
    if display:
        display.update_progress("manifest")

    stage_start = datetime.now()
    result = generate_manifest(url, draft_manifest, event_store)
    stage_timings['manifest'] = (datetime.now() - stage_start).total_seconds()

    if not result.success:
        event_store.emit(create_event(
            EventType.PERIOD_FAILED,
            event_store.run_id,
            message=f"Manifest generation failed: {result.error}",
            publication=pub_code,
            period=period,
            level=EventLevel.ERROR,
            error=result.error
        ))
        return False, {}

    # Step 2: Enrich manifest (using library)
    event_store.emit(create_event(
        EventType.STAGE_STARTED,
        event_store.run_id,
        message="Enriching manifest",
        publication=pub_code,
        period=period,
        stage="enrich"
    ))

    # Determine reference manifest using fiscal-year-aware logic
    if no_reference:
        reference = None
        if not display:
            print(f"  → Fresh LLM enrichment (--no-reference flag)")
    else:
        reference = find_reference_manifest(pub_code, period, manual_reference)
        if reference:
            ref_name = Path(reference).name
            if period.startswith('apr'):
                if not display:
                    print(f"  → April baseline - fresh LLM enrichment")
                reference = None
            else:
                april_fy = get_fiscal_year_april(period)
                if f"_{april_fy}_" in reference:
                    if not display:
                        print(f"  → Using fiscal year {april_fy} baseline: {ref_name}")
                else:
                    if not display:
                        print(f"  → Using temporary reference: {ref_name} (April baseline not yet loaded)")
        else:
            if not display:
                print(f"  → No reference found - fresh LLM enrichment")

    if display:
        display.update_progress("enrich")

    stage_start = datetime.now()
    enrich_result = enrich_manifest(
        input_path=str(draft_manifest),
        output_path=str(enriched_manifest),
        reference_path=reference,
        event_store=event_store,
        publication=pub_code,
        period=period
    )
    stage_timings['enrich'] = (datetime.now() - stage_start).total_seconds()

    if not enrich_result.success:
        event_store.emit(create_event(
            EventType.STAGE_FAILED,
            event_store.run_id,
            message=f"Enrichment failed: {enrich_result.error}",
            publication=pub_code,
            period=period,
            stage="enrich",
            level=EventLevel.ERROR,
            error=enrich_result.error
        ))
        return False, {}

    event_store.emit(create_event(
        EventType.STAGE_COMPLETED,
        event_store.run_id,
        message=f"Enrichment completed: {enrich_result.sources_enriched} sources",
        publication=pub_code,
        period=period,
        stage="enrich"
    ))

    # Step 2.5: Canonicalize codes (remove date patterns)
    event_store.emit(create_event(
        EventType.STAGE_STARTED,
        event_store.run_id,
        message="Canonicalizing source codes",
        publication=pub_code,
        period=period,
        stage="canonicalize"
    ))

    try:
        with open(enriched_manifest) as f:
            manifest_data = yaml.safe_load(f)

        # Apply canonicalization
        canonical_manifest_data = canonicalize_manifest(manifest_data)

        # Save canonical manifest
        canonical_manifest = manifest_dir / f"{pub_code}_{period}_canonical.yaml"
        with open(canonical_manifest, 'w') as f:
            yaml.dump(canonical_manifest_data, f, sort_keys=False)

        # Update enriched_manifest path to use canonical version
        enriched_manifest = canonical_manifest

        event_store.emit(create_event(
            EventType.STAGE_COMPLETED,
            event_store.run_id,
            message=f"Canonicalization completed",
            publication=pub_code,
            period=period,
            stage="canonicalize"
        ))
    except Exception as e:
        event_store.emit(create_event(
            EventType.WARNING,
            event_store.run_id,
            message=f"Canonicalization failed (non-fatal): {str(e)}",
            publication=pub_code,
            period=period,
            stage="canonicalize",
            level=EventLevel.WARNING,
            error=str(e)
        ))
        # Continue with enriched manifest if canonicalization fails

    # Step 3: Load to database (using batch.py for full database tracking)
    if display:
        display.update_progress("load")

    event_store.emit(create_event(
        EventType.STAGE_STARTED,
        event_store.run_id,
        message="Loading to database",
        publication=pub_code,
        period=period,
        stage="load"
    ))

    try:
        # Use batch.load_from_manifest() which has ALL database tracking:
        # - check_manifest_file_status() for idempotent loading
        # - record_manifest_file() for tbl_manifest_files tracking
        # - store_column_metadata() for tbl_column_metadata
        # - Detailed error tracking with context
        stage_start = datetime.now()
        batch_stats = load_from_manifest(
            manifest_path=str(enriched_manifest),
            force_reload=force,
            quiet=(display is not None)  # Suppress batch.py output when using progress display
        )
        stage_timings['load'] = (datetime.now() - stage_start).total_seconds()

        # Convert file_results to SourceResult for display
        sources = []
        if display and hasattr(batch_stats, 'file_results'):
            for file_result in batch_stats.file_results:
                # Map status
                if file_result.status == 'loaded':
                    status = 'success'
                elif file_result.status == 'failed':
                    status = 'error'
                else:
                    status = 'warning'

                sources.append(SourceResult(
                    name=file_result.source_code,
                    rows=file_result.rows,
                    columns_added=file_result.new_cols,
                    status=status,
                    warning=file_result.error if status == 'warning' else None,
                    duration_ms=int(file_result.duration * 1000)
                ))

        # Map batch stats to EventStore events
        if batch_stats.failed > 0 and batch_stats.loaded == 0:
            # Complete failure - no sources loaded
            event_store.emit(create_event(
                EventType.STAGE_FAILED,
                event_store.run_id,
                message=f"Load failed: {batch_stats.failed} files failed, 0 loaded",
                publication=pub_code,
                period=period,
                stage="load",
                level=EventLevel.ERROR,
                context={'failed': batch_stats.failed, 'errors': batch_stats.errors[:3]}
            ))
            return False, {}
        elif batch_stats.failed > 0:
            # Partial success - some files failed
            event_store.emit(create_event(
                EventType.WARNING,
                event_store.run_id,
                message=f"Load completed with failures: {batch_stats.loaded} loaded, {batch_stats.failed} failed",
                publication=pub_code,
                period=period,
                stage="load",
                level=EventLevel.WARNING,
                context={'loaded': batch_stats.loaded, 'failed': batch_stats.failed, 'total_rows': batch_stats.total_rows}
            ))
        else:
            # Complete success
            event_store.emit(create_event(
                EventType.STAGE_COMPLETED,
                event_store.run_id,
                message=f"Load completed: {batch_stats.loaded} sources, {batch_stats.total_rows:,} rows",
                publication=pub_code,
                period=period,
                stage="load",
                context={'sources_loaded': batch_stats.loaded, 'total_rows': batch_stats.total_rows, 'skipped': batch_stats.skipped}
            ))

    except Exception as e:
        event_store.emit(create_event(
            EventType.STAGE_FAILED,
            event_store.run_id,
            message=f"Load failed: {str(e)}",
            publication=pub_code,
            period=period,
            stage="load",
            level=EventLevel.ERROR,
            error=str(e)
        ))
        return False, {}

    # Step 4: Export to parquet (using library)
    if display:
        display.update_progress("export")

    event_store.emit(create_event(
        EventType.STAGE_STARTED,
        event_store.run_id,
        message="Exporting to Parquet",
        publication=pub_code,
        period=period,
        stage="export"
    ))

    try:
        output_dir = PROJECT_ROOT / "output"
        export_results = export_publication_to_parquet(
            publication=pub_code,
            output_dir=str(output_dir),
            event_store=event_store,
            period=period
        )

        successful_exports = [r for r in export_results if r.success]
        failed_exports = [r for r in export_results if not r.success]

        if failed_exports:
            event_store.emit(create_event(
                EventType.WARNING,
                event_store.run_id,
                message=f"Export completed with {len(failed_exports)} failures (non-fatal)",
                publication=pub_code,
                period=period,
                stage="export",
                level=EventLevel.WARNING,
                context={'successful': len(successful_exports), 'failed': len(failed_exports)}
            ))
        else:
            event_store.emit(create_event(
                EventType.STAGE_COMPLETED,
                event_store.run_id,
                message=f"Export completed: {len(successful_exports)} files",
                publication=pub_code,
                period=period,
                stage="export"
            ))

    except Exception as e:
        event_store.emit(create_event(
            EventType.WARNING,
            event_store.run_id,
            message=f"Export failed (non-fatal): {str(e)}",
            publication=pub_code,
            period=period,
            stage="export",
            level=EventLevel.WARNING,
            error=str(e)
        ))
        # Don't fail the whole process for export issues

    event_store.emit(create_event(
        EventType.PERIOD_COMPLETED,
        event_store.run_id,
        message=f"Successfully processed {pub_code}/{period}",
        publication=pub_code,
        period=period
    ))

    # Return success and stats
    period_stats = {
        'pub_code': pub_code,
        'period': period,
        'rows': batch_stats.total_rows if 'batch_stats' in locals() else 0,
        'sources': batch_stats.loaded if 'batch_stats' in locals() else 0,
        'columns': batch_stats.total_columns if 'batch_stats' in locals() else 0
    }

    # Build and display period completion
    if display:
        period_result = PeriodResult(
            publication=pub_code,
            period=period,
            stage_timings=stage_timings,
            sources=sources if 'sources' in locals() else [],
            status='success',
            warnings=warnings  # Collected warnings
        )
        display.complete_period(period_result)

    return True, period_stats


def show_status(config: dict, state: dict):
    """Show current processing status."""
    print("\n" + "=" * 60)
    print("DataWarp Backfill Status")
    print("=" * 60)

    total_urls = 0
    processed_count = 0
    pending_count = 0
    failed_count = 0

    for pub_code, pub_config in config.get("publications", {}).items():
        urls = pub_config.get("urls", [])
        if not urls:
            continue

        pub_processed = 0
        pub_pending = 0
        pub_failed = 0

        for release in urls:
            period = release["period"]
            key = f"{pub_code}/{period}"
            total_urls += 1

            if key in state.get("processed", {}):
                pub_processed += 1
                processed_count += 1
            elif key in state.get("failed", {}):
                pub_failed += 1
                failed_count += 1
            else:
                pub_pending += 1
                pending_count += 1

        # Progress bar
        total = pub_processed + pub_pending + pub_failed
        if total > 0:
            pct = pub_processed / total * 100
            bar_len = 20
            filled = int(bar_len * pub_processed / total)
            bar = "█" * filled + "░" * (bar_len - filled)
            status = "✓" if pub_pending == 0 and pub_failed == 0 else "..."
            print(f"\n{pub_config['name'][:40]:<40}")
            print(f"  {bar} {pub_processed}/{total} {status}")
            if pub_failed > 0:
                print(f"  ⚠ {pub_failed} failed")

    print("\n" + "-" * 60)
    print(f"Total URLs:     {total_urls}")
    print(f"Processed:      {processed_count}")
    print(f"Pending:        {pending_count}")
    print(f"Failed:         {failed_count}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Process NHS publication backlog",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/backfill.py                  # Process all pending
  python scripts/backfill.py --pub adhd       # Process one publication
  python scripts/backfill.py --dry-run        # Show what would run
  python scripts/backfill.py --status         # Show progress
  python scripts/backfill.py --quiet          # Minimal output (only warnings/errors)
        """
    )
    parser.add_argument("--config", help="Path to config file (default: config/publications.yaml)")
    parser.add_argument("--pub", help="Process only this publication")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed")
    parser.add_argument("--status", action="store_true", help="Show current status")
    parser.add_argument("--retry-failed", action="store_true", help="Retry failed items")
    parser.add_argument("--force", action="store_true", help="Force reload even if already processed")
    parser.add_argument("--reference", help="Manual reference manifest path (overrides fiscal year logic)")
    parser.add_argument("--no-reference", action="store_true", help="Force fresh LLM enrichment (ignore all references)")
    parser.add_argument("--quiet", action="store_true", help="Suppress INFO logs (only show warnings/errors and loading progress)")

    args = parser.parse_args()

    # Suppress library warnings in quiet mode
    if args.quiet:
        import warnings
        warnings.filterwarnings('ignore', category=FutureWarning)
        warnings.filterwarnings('ignore', category=UserWarning)
        warnings.filterwarnings('ignore', message='pandas only supports SQLAlchemy')

        # Suppress DEBUG logs from batch loader
        import logging
        logging.getLogger('datawarp.loader.batch').setLevel(logging.WARNING)

    # Load config file
    config_path = Path(args.config) if args.config else None
    config = load_config(config_path)
    state = load_state()

    if args.status:
        show_status(config, state)
        return

    # Create EventStore and Display
    run_id = f"backfill_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Initialize progress display for selected publication
    display = None
    if args.pub:
        pub_name = config.get("publications", {}).get(args.pub, {}).get("name", args.pub.upper())
        display = ProgressDisplay(pub_name)
        display.print_header()

    # Force quiet mode when using progress display
    use_quiet = args.quiet or (display is not None)
    with EventStore(run_id, LOGS_DIR, quiet=use_quiet) as event_store:

        event_store.emit(create_event(
            EventType.RUN_STARTED,
            run_id,
            message="DataWarp Backfill Started",
            config_file=str(CONFIG_FILE),
            mode="DRY_RUN" if args.dry_run else "EXECUTE"
        ))

        # Process each publication
        processed = 0
        skipped = 0
        failed = 0
        total_rows = 0
        total_sources = 0
        total_columns = 0
        processed_details = []  # Track what was processed

        for pub_code, pub_config in config.get("publications", {}).items():
            # Filter by publication if specified
            if args.pub and pub_code != args.pub:
                continue

            urls = pub_config.get("urls", [])
            if not urls:
                continue

            for release in urls:
                period = release["period"]
                url = release["url"]
                enabled = release.get("enabled", True)  # Default to True if not specified
                key = f"{pub_code}/{period}"

                # Skip if disabled (enabled=false in YAML)
                if not enabled:
                    event_store.emit(create_event(
                        EventType.WARNING,
                        run_id,
                        message=f"Skipping {period} - disabled in config (enabled: false)",
                        publication=pub_code,
                        period=period,
                        level=EventLevel.DEBUG
                    ))
                    skipped += 1
                    continue

                # Skip if already processed (unless --force)
                if is_processed(state, pub_code, period) and not args.force:
                    event_store.emit(create_event(
                        EventType.WARNING,
                        run_id,
                        message=f"Skipping {period} - already processed",
                        publication=pub_code,
                        period=period,
                        level=EventLevel.DEBUG
                    ))
                    skipped += 1
                    continue

                # Skip failed unless --retry-failed
                if key in state.get("failed", {}) and not args.retry_failed:
                    event_store.emit(create_event(
                        EventType.WARNING,
                        run_id,
                        message=f"Skipping {period} - previously failed",
                        publication=pub_code,
                        period=period,
                        level=EventLevel.DEBUG
                    ))
                    skipped += 1
                    continue

                # Process this period
                success, period_stats = process_period(
                    pub_code,
                    pub_config,
                    period,
                    url,
                    event_store,
                    args.dry_run,
                    args.force,
                    args.reference,
                    args.no_reference,
                    display  # Pass display for tree output
                )

                if success:
                    if not args.dry_run:
                        mark_processed(state, pub_code, period)
                    processed += 1
                    # Aggregate stats
                    total_rows += period_stats.get('rows', 0)
                    total_sources += period_stats.get('sources', 0)
                    total_columns += period_stats.get('columns', 0)
                    processed_details.append(period_stats)
                else:
                    if not args.dry_run:
                        mark_failed(state, pub_code, period, "See log for details")
                    failed += 1

        # Summary
        event_store.emit(create_event(
            EventType.RUN_COMPLETED,
            run_id,
            message=f"Backfill completed: {processed} processed, {skipped} skipped, {failed} failed",
            processed=processed,
            skipped=skipped,
            failed=failed
        ))

        # Print comprehensive summary using balanced display
        if display:
            # Periods were already added during processing
            display.print_summary()
        else:
            # Fallback to old summary for multi-pub runs
            print("\n" + "=" * 80)
            print("BACKFILL SUMMARY")
            print("=" * 80)
            print(f"{'Processed:':<20} {processed} publication periods")
            print(f"{'Skipped:':<20} {skipped}")
            print(f"{'Failed:':<20} {failed}")
            print()
            print(f"{'Total Sources:':<20} {total_sources} tables loaded")
            print(f"{'Total Rows:':<20} {total_rows:,}")
            print(f"{'Total Columns:':<20} {total_columns} new columns added")

            if processed_details:
                print()
                print("Processed Details:")
                print("-" * 80)
                for detail in processed_details:
                    pub = detail.get('pub_code', 'unknown')
                    period = detail.get('period', 'unknown')
                    rows = detail.get('rows', 0)
                    sources = detail.get('sources', 0)
                    cols = detail.get('columns', 0)
                    print(f"  {pub}/{period:<15} {sources:>2} sources, {rows:>7,} rows, {cols:>3} cols")
            print("=" * 80)


if __name__ == "__main__":
    main()
