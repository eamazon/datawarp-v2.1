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
import warnings
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

# Suppress noisy warnings globally (google.generativeai deprecation, pandas SQLAlchemy)
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', message='.*pandas only supports SQLAlchemy.*')

from datawarp.pipeline import generate_manifest, enrich_manifest, export_publication_to_parquet
from datawarp.pipeline.canonicalize import canonicalize_manifest
from datawarp.loader.batch import load_from_manifest
from datawarp.supervisor.events import EventStore, EventType, EventLevel, create_event
from datawarp.cli.display import ProgressDisplay, PeriodResult, SourceResult
from datawarp.utils.url_resolver import resolve_urls, get_all_periods


PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_FILE = PROJECT_ROOT / "config" / "publications.yaml"
STATE_FILE = PROJECT_ROOT / "state" / "state.json"
MANIFESTS_DIR = PROJECT_ROOT / "manifests" / "backfill"
LOGS_DIR = PROJECT_ROOT / "logs"


def load_config(config_path: Path = None) -> dict:
    """Load publications config with intelligent error handling."""
    config_file = config_path if config_path else CONFIG_FILE

    if not config_file.exists():
        print()
        print("❌ CONFIG FILE NOT FOUND")
        print()
        print(f"Looking for: {config_file}")
        print()
        print("💡 Fix:")
        print(f"  • Create the file at {config_file}")
        print(f"  • Or use --config to specify a different path")
        print()
        sys.exit(1)

    # INTELLIGENT: Catch YAML parsing errors with helpful message
    try:
        return yaml.safe_load(config_file.read_text())
    except yaml.YAMLError as e:
        print()
        print("❌ INVALID CONFIG FILE")
        print()
        print(f"The YAML file has syntax errors:")

        # Extract useful error info
        if hasattr(e, 'problem_mark'):
            mark = e.problem_mark
            print(f"  Line {mark.line + 1}, column {mark.column + 1}: {e.problem}")
        else:
            print(f"  {str(e)}")

        print()
        print(f"File: {config_file}")
        print()
        print("💡 Fix:")
        print("  • Check YAML syntax (indentation, colons, quotes)")
        print("  • Common issues:")
        print("    - Missing space after colon (key:value should be key: value)")
        print("    - Incorrect indentation (use 2 spaces, not tabs)")
        print("    - Unclosed quotes or brackets")
        print("  • Validate at: https://www.yamllint.com/")
        print()
        sys.exit(1)


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


# Import period utilities - single source of truth for period parsing
import sys
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from datawarp.utils.period import (
    get_fiscal_year_april,
    is_first_of_fiscal_year,
    format_period_display,
    period_to_dates
)


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
    if is_first_of_fiscal_year(period):
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
    display: Optional['ProgressDisplay'] = None,
    skip_enrichment: bool = False
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
        return True, {}

    # Create manifest directory
    manifest_dir = MANIFESTS_DIR / pub_code
    manifest_dir.mkdir(parents=True, exist_ok=True)

    draft_manifest = manifest_dir / f"{pub_code}_{period}.yaml"
    enriched_manifest = manifest_dir / f"{pub_code}_{period}_enriched.yaml"

    # Step 1: Generate manifest (using library)
    if display:
        display.update_progress("manifest")

    stage_start = datetime.now()
    # Skip preview generation if not enriching (6-7x faster for large files)
    result = generate_manifest(url, draft_manifest, event_store, skip_preview=skip_enrichment)
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

    # Step 2: Enrich manifest (skip if exceptional case)
    if skip_enrichment:
        # Skip enrichment - use draft manifest directly
        enriched_manifest = draft_manifest

        # Emit warning: skip_enrichment is exceptional, not standard practice
        reason = "from config (EXCEPTIONAL - 100+ repetitive columns)" if pub_config.get('skip_enrichment') else "from --skip-enrichment CLI flag"
        event_store.emit(create_event(
            EventType.WARNING,
            event_store.run_id,
            message=f"⚠️ Skipping enrichment {reason}",
            publication=pub_code,
            period=period,
            stage="enrich",
            level=EventLevel.WARNING
        ))
    else:
        # Full enrichment workflow
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
                if is_first_of_fiscal_year(period):
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
    # For state tracking, include BOTH loaded and skipped rows
    # (total_rows only counts newly loaded, but state needs full count)
    total_rows_including_skipped = 0
    if 'batch_stats' in locals():
        total_rows_including_skipped = batch_stats.total_rows  # Newly loaded rows
        # Add skipped rows from file_results
        for file_result in batch_stats.file_results:
            if file_result.status == 'skipped':
                total_rows_including_skipped += file_result.rows

    period_stats = {
        'pub_code': pub_code,
        'period': period,
        'rows': total_rows_including_skipped,
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
    """Show intelligent processing status with database verification."""
    print("\n" + "=" * 80)
    print("DataWarp Status Report")
    print("=" * 80)

    # Get database stats first
    from datawarp.storage.connection import get_connection
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Get staging tables
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = 'staging'
            """)
            table_count = cursor.fetchone()[0]

            # Get total rows
            cursor.execute("""
                SELECT
                    COUNT(*) as loads,
                    SUM(CASE WHEN status = 'loaded' THEN rows_loaded ELSE 0 END) as total_rows,
                    MAX(loaded_at) as last_load
                FROM datawarp.tbl_manifest_files
            """)
            loads, total_rows, last_load = cursor.fetchone()

            print()
            print("📊 Database Status:")
            print(f"  • {table_count} tables in staging schema")
            print(f"  • {total_rows:,} total rows loaded")
            print(f"  • Last load: {last_load.strftime('%Y-%m-%d %H:%M:%S') if last_load else 'Never'}")
            print()

    except Exception as e:
        print(f"\n⚠️  Could not connect to database: {e}\n")

    # Publication status
    total_urls = 0
    processed_count = 0
    pending_count = 0
    failed_count = 0

    print("📋 Publication Status:")
    print()

    for pub_code, pub_config in config.get("publications", {}).items():
        # Use url_resolver to get all periods
        periods = get_all_periods(pub_config)
        if not periods:
            continue

        pub_processed = 0
        pub_pending = 0
        pub_failed = 0
        pub_rows = 0

        for period in periods:
            key = f"{pub_code}/{period}"
            total_urls += 1

            if key in state.get("processed", {}):
                pub_processed += 1
                processed_count += 1
                pub_rows += state['processed'][key].get('rows_loaded', 0)
            elif key in state.get("failed", {}):
                pub_failed += 1
                failed_count += 1
            else:
                pub_pending += 1
                pending_count += 1

        # Progress bar
        total = pub_processed + pub_pending + pub_failed
        if total > 0:
            bar_len = 30
            filled = int(bar_len * pub_processed / total)
            bar = "█" * filled + "░" * (bar_len - filled)
            status = "✅" if pub_pending == 0 and pub_failed == 0 else "⏳"

            print(f"{pub_config['name'][:50]:<50}")
            print(f"  {bar} {pub_processed}/{total} {status}")

            if pub_rows > 0:
                print(f"  📈 {pub_rows:,} rows")

            if pub_failed > 0:
                print(f"  ❌ {pub_failed} failed")

            if pub_pending > 0:
                print(f"  ⏳ {pub_pending} pending")

            print()

    print("─" * 80)
    print(f"\n📈 Overall Progress:")
    print(f"  • Total periods: {total_urls}")
    print(f"  • ✅ Processed: {processed_count}")
    print(f"  • ⏳ Pending: {pending_count}")
    print(f"  • ❌ Failed: {failed_count}")
    print()

    # Intelligent suggestions
    if failed_count > 0:
        print("💡 Next steps:")
        print(f"  • Retry failures: python scripts/backfill.py --retry-failed")
        print(f"  • Check logs: tail -100 logs/backfill_*.log | grep ERROR")
        print()
    elif pending_count > 0:
        print("💡 Next steps:")
        print(f"  • Process pending: python scripts/backfill.py")
        print()
    else:
        print("✅ All publications up to date!")
        print()
        print("💡 Next steps:")
        print("  • Query data: psql -d databot_dev")
        print("  • Export to Parquet: python scripts/export_to_parquet.py --all")
        print()

    print("=" * 80)


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
    parser.add_argument("--skip-enrichment", action="store_true", help="EXCEPTIONAL: Skip enrichment for testing (normally set in config YAML, not CLI)")
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

    # INTELLIGENT UX: Validate publication exists before doing anything
    if args.pub and args.pub not in config.get("publications", {}):
        print()
        print("❌ PUBLICATION NOT FOUND")
        print()
        print(f"'{args.pub}' is not in {args.config}")
        print()
        print("Available publications:")
        for pub_code in sorted(config.get("publications", {}).keys()):
            pub_name = config["publications"][pub_code].get("name", pub_code)
            print(f"  • {pub_code:45} ({pub_name})")
        print()
        print("💡 Fix:")
        print("  • Check spelling")
        print(f"  • Or add to {args.config}")
        print()
        sys.exit(1)

    # Initialize progress display for selected publication
    display = None
    if args.pub:
        pub_name = config.get("publications", {}).get(args.pub, {}).get("name", args.pub.upper())
        display = ProgressDisplay(pub_name)
        display.print_header()

    # INTELLIGENT: Check if --retry-failed makes sense
    if args.retry_failed:
        failed_items = state.get("failed", {})
        if not failed_items:
            print()
            print("✅ NO FAILURES TO RETRY")
            print()
            print("All periods completed successfully.")
            print()
            print("💡 To reprocess anyway:")
            print("  • Use --force flag instead:")
            if args.pub:
                print(f"    python scripts/backfill.py --pub {args.pub} --force")
            else:
                print(f"    python scripts/backfill.py --force")
            print()
            sys.exit(0)
        else:
            print()
            print(f"🔄 RETRYING {len(failed_items)} FAILED PERIOD(S)")
            print()
            for key in list(failed_items.keys())[:5]:
                print(f"  • {key}")
            if len(failed_items) > 5:
                print(f"  ... and {len(failed_items) - 5} more")
            print()

    # Validate skip_enrichment usage (should be exceptional - max 2 publications)
    skip_enrichment_pubs = [
        pub_code for pub_code, pub_config in config.get("publications", {}).items()
        if pub_config.get('skip_enrichment', False)
    ]
    if len(skip_enrichment_pubs) > 2:
        print()
        print(f"⚠️  WARNING: {len(skip_enrichment_pubs)} publications have skip_enrichment=true")
        print(f"   This setting is EXCEPTIONAL and should be rare (max 1-2 publications)")
        print(f"   Publications: {', '.join(skip_enrichment_pubs)}")
        print()

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

        # Log skip_enrichment exceptions if any
        if skip_enrichment_pubs:
            event_store.emit(create_event(
                EventType.WARNING,
                run_id,
                message=f"⚠️ {len(skip_enrichment_pubs)} publication(s) using skip_enrichment (EXCEPTIONAL): {', '.join(skip_enrichment_pubs)}",
                level=EventLevel.WARNING,
                publications=skip_enrichment_pubs
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

            # Use url_resolver to iterate over periods (works with both template and explicit modes)
            try:
                url_pairs = list(resolve_urls(pub_config))
            except NotImplementedError as e:
                event_store.emit(create_event(
                    EventType.WARNING,
                    run_id,
                    message=f"Skipping {pub_code} - {str(e)}",
                    publication=pub_code,
                    level=EventLevel.WARNING
                ))
                continue

            if not url_pairs:
                continue

            for period, url in url_pairs:
                key = f"{pub_code}/{period}"

                # For explicit mode, check if disabled
                if pub_config.get('discovery_mode', 'explicit') == 'explicit':
                    # Find the matching URL entry to check enabled flag
                    url_entry = next((u for u in pub_config.get('urls', []) if u.get('period') == period), {})
                    enabled = url_entry.get("enabled", True)
                else:
                    enabled = True  # Template mode always enabled

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

                # Determine skip_enrichment: CLI flag overrides config setting
                skip_enrichment = args.skip_enrichment or pub_config.get('skip_enrichment', False)

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
                    display,  # Pass display for tree output
                    skip_enrichment
                )

                if success:
                    if not args.dry_run:
                        mark_processed(state, pub_code, period, period_stats.get('rows', 0))
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

        # INTELLIGENT UX: Explain what happened when no new data loaded
        if processed == 0 and skipped == 0 and failed == 0:
            print()
            print("ℹ️  NO PERIODS TO PROCESS")
            print()
            print("Possible reasons:")
            print("  • Publication has no periods in configured date range")
            print("  • Check 'start' and 'end' dates in config")
            print("  • Publication may not exist yet")
            print()
            print(f"💡 Tip: Run with --dry-run to see what periods would be processed")

        elif total_sources == 0 and total_rows == 0 and skipped > 0:
            # CRITICAL: Verify database actually has data before claiming success
            try:
                from datawarp.storage.connection import get_connection
                with get_connection() as conn:
                    cursor = conn.cursor()

                    # Get table count
                    cursor.execute("""
                        SELECT COUNT(*) FROM information_schema.tables
                        WHERE table_schema = 'staging'
                    """)
                    table_count = cursor.fetchone()[0]

                    # Get total rows
                    cursor.execute("""
                        SELECT SUM(rows_loaded) FROM datawarp.tbl_manifest_files
                        WHERE status = 'loaded'
                    """)
                    total_db_rows = cursor.fetchone()[0] or 0

                    # STATE vs DATABASE MISMATCH CHECK
                    if table_count == 0 or total_db_rows == 0:
                        print()
                        print("⚠️  STATE FILE MISMATCH DETECTED")
                        print()
                        print(f"State file says: {skipped} period(s) already loaded")
                        print(f"Database shows:  {table_count} tables, {total_db_rows:,} rows")
                        print()
                        print("🔍 Diagnosis:")
                        print("  • State file (state/state.json) thinks data is loaded")
                        print("  • But database is empty or incomplete")
                        print("  • This usually means database was reset without clearing state")
                        print()
                        print("💡 Solution:")
                        print("  • Option 1 (Recommended): Clear state and reload")
                        if args.pub:
                            print(f"    rm state/state.json && python scripts/backfill.py --pub {args.pub}")
                        else:
                            print(f"    rm state/state.json && python scripts/backfill.py")
                        print()
                        print("  • Option 2: Force reload (keeps state file)")
                        if args.pub:
                            print(f"    python scripts/backfill.py --pub {args.pub} --force")
                        else:
                            print(f"    python scripts/backfill.py --force")
                    else:
                        # Database verified - data actually exists
                        print()
                        print("✅ ALL DATA UP TO DATE")
                        print()
                        print(f"📋 {skipped} period(s) already loaded and current")
                        print()
                        print("Database status:")
                        print(f"  • {table_count} tables in staging schema")
                        print(f"  • {total_db_rows:,} total rows loaded")
                        print()
                        print("💡 Next steps:")
                        print("  • Query data: psql -d databot_dev -c \"SELECT * FROM staging.tbl_<name> LIMIT 10\"")
                        print("  • Export to Parquet: python scripts/export_to_parquet.py --publication <name>")
                        print("  • Reload anyway: Re-run with --force flag")

            except Exception as e:
                print()
                print("⚠️  COULD NOT VERIFY DATABASE")
                print()
                print(f"Error: {e}")
                print()
                print("State file says data is loaded, but cannot verify database.")
                print()
                print("💡 Check:")
                print("  • Is PostgreSQL running?")
                print("  • Check connection: psql -d databot_dev")
                if args.pub:
                    print(f"  • Or reload: python scripts/backfill.py --pub {args.pub} --force")
                else:
                    print(f"  • Or reload: python scripts/backfill.py --force")

        elif failed > 0:
            print()
            print("⚠️  SOME PERIODS FAILED")
            print()
            print("💡 Next steps:")
            print(f"  • Check logs: tail -100 logs/backfill_*.log | grep ERROR")
            print("  • Retry failures: python scripts/backfill.py --retry-failed")
            print("  • See state: cat state/state.json | python -m json.tool")


if __name__ == "__main__":
    main()
