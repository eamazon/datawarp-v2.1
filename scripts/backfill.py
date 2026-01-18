#!/usr/bin/env python3
"""
DataWarp Backfill Script (v2.3 - Database as Single Source of Truth)

Simple system to process historical NHS data and monitor for new releases.
Reads config/publications.yaml, processes pending URLs.
Database (tbl_manifest_files) tracks what's been loaded - no separate state file.

Usage:
    python scripts/backfill.py                                    # Process all pending
    python scripts/backfill.py --config config/test.yaml          # Use custom config
    python scripts/backfill.py --pub adhd                         # Process one publication
    python scripts/backfill.py --pub adhd --period 2025-04        # Process one period
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
# Note: state.json removed in v2.3 - database is single source of truth
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


def validate_config(config: dict, pub_filter: str = None) -> list:
    """Validate config and return list of errors.

    Catches common issues BEFORE processing starts:
    - Missing URLs in explicit mode
    - Invalid period formats
    - Truncated entries
    - Missing required fields
    """
    errors = []
    warnings = []

    publications = config.get("publications", {})
    if not publications:
        errors.append("No publications defined in config")
        return errors

    for pub_code, pub_config in publications.items():
        # Skip if filtering to specific publication
        if pub_filter and pub_code != pub_filter:
            continue

        # Check required fields
        if not pub_config.get("name"):
            warnings.append(f"{pub_code}: Missing 'name' field")

        # Validate explicit URLs mode
        if "urls" in pub_config:
            for i, entry in enumerate(pub_config["urls"]):
                period = entry.get("period")
                url = entry.get("url")

                # Check for missing period
                if not period:
                    errors.append(f"{pub_code}: Entry {i+1} missing 'period' field")
                    continue

                # Check for missing/None URL (the bug we hit!)
                if url is None:
                    errors.append(f"{pub_code}: Period {period} has no URL (None)")
                elif not url:
                    errors.append(f"{pub_code}: Period {period} has empty URL")
                elif not url.startswith(("http://", "https://")):
                    errors.append(f"{pub_code}: Period {period} has invalid URL: {url[:50]}...")

                # Validate period format
                if period and not _is_valid_period(period):
                    warnings.append(f"{pub_code}: Period '{period}' has unusual format")

        # Validate template mode
        elif pub_config.get("url_template") or pub_config.get("discovery_mode") == "template":
            if not pub_config.get("landing_page"):
                errors.append(f"{pub_code}: Template mode requires 'landing_page'")

            periods = pub_config.get("periods", [])
            if isinstance(periods, list) and not periods:
                warnings.append(f"{pub_code}: No periods defined")

    return errors, warnings


def _is_valid_period(period: str) -> bool:
    """Check if period has valid format."""
    import re
    # Monthly: 2025-04, 2025-11
    if re.match(r"^\d{4}-\d{2}$", period):
        return True
    # Fiscal quarter: FY25-Q1, FY2025-Q2
    if re.match(r"^FY\d{2,4}-Q[1-4]$", period):
        return True
    # Fiscal year: FY2024-25, FY25-26
    if re.match(r"^FY\d{2,4}-\d{2}$", period):
        return True
    # Annual: 2025
    if re.match(r"^\d{4}$", period):
        return True
    return False


def is_period_loaded(pub_code: str, period: str) -> bool:
    """Check if a period has data loaded in database.

    Uses tbl_manifest_files as single source of truth.
    No more state.json - database IS the state.
    """
    from datawarp.storage.connection import get_connection
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            # Check if ANY source for this publication/period is loaded
            cursor.execute("""
                SELECT COUNT(*) FROM datawarp.tbl_manifest_files
                WHERE period = %s AND status = 'loaded'
                AND source_code LIKE %s
            """, (period, f"%{pub_code.split('_')[-1]}%"))
            count = cursor.fetchone()[0]
            return count > 0
    except Exception:
        return False


def get_loaded_periods(pub_code: str) -> set:
    """Get all loaded periods for a publication from database."""
    from datawarp.storage.connection import get_connection
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT period FROM datawarp.tbl_manifest_files
                WHERE status = 'loaded'
            """)
            return {row[0] for row in cursor.fetchall()}
    except Exception:
        return set()


# Import period utilities - single source of truth for period parsing
import sys
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from datawarp.utils.period import (
    get_fiscal_year_april,
    is_first_of_fiscal_year,
    format_period_display,
    period_to_dates
)


def extract_period_from_manifest(path: Path) -> str:
    """Extract period from manifest filename for sorting.

    Examples:
        nhs_england_rtt_2025-04_enriched.yaml -> 2025-04
        adhd_2025-11_canonical.yaml -> 2025-11
    """
    import re
    name = path.stem  # Remove .yaml
    # Match YYYY-MM pattern
    match = re.search(r'(\d{4}-\d{2})', name)
    if match:
        return match.group(1)
    return "0000-00"  # Fallback for sorting


def find_reference_manifest(pub_code: str, period: str, manual_reference: str = None) -> str:
    """Find the best reference manifest for a period using ROLLING REFERENCE logic.

    ROLLING REFERENCE: The latest enriched manifest becomes the reference for
    subsequent periods. This allows the reference to grow as new sheets/columns
    are discovered.

    Priority:
    1. Manual reference (--reference CLI flag) - for overrides/rollbacks
    2. Latest enriched/canonical manifest for this publication (by period)
    3. None (triggers full LLM enrichment for first-ever run)

    EDGE CASES HANDLED:
    - First period ever: No reference exists → full LLM enrichment
    - New sheets in later period: Reference grows, next period inherits all
    - Manual override: --reference flag for rollback to known-good state
    - Corrupted reference: Validation in caller, fallback to LLM

    NOTE: We no longer special-case April as "always baseline". The rolling
    reference approach means any period can be baseline if it's the first.

    Args:
        pub_code: Publication code (e.g., "nhs_england_rtt_provider_incomplete")
        period: Period being loaded (e.g., "2025-05")
        manual_reference: Manually specified reference path (overrides auto-detection)

    Returns:
        Path to reference manifest, or None if no reference available
    """
    # Priority 1: Manual override (for rollbacks or specific reference selection)
    if manual_reference:
        ref_path = Path(manual_reference)
        if ref_path.exists():
            return str(ref_path)
        print(f"⚠️  Specified reference not found: {manual_reference}")
        return None

    # Priority 2: Find latest enriched manifest by PERIOD (not modification time)
    # This implements the "rolling reference" - each period inherits from previous
    production_dir = PROJECT_ROOT / "manifests" / "production" / pub_code
    backfill_dir = MANIFESTS_DIR / pub_code

    enriched_manifests = []

    # Collect all enriched and canonical manifests
    for directory in [production_dir, backfill_dir]:
        if directory.exists():
            enriched_manifests.extend(directory.glob(f"{pub_code}_*_enriched.yaml"))
            enriched_manifests.extend(directory.glob(f"{pub_code}_*_canonical.yaml"))

    if not enriched_manifests:
        # First ever run - no reference available
        return None

    # Filter: Only use manifests from periods BEFORE the current one
    # (can't reference future or current period)
    current_manifests = [
        m for m in enriched_manifests
        if extract_period_from_manifest(m) < period
    ]

    if not current_manifests:
        # No prior periods available (this is the first period)
        return None

    # Sort by period and return the most recent (latest period, not file mtime)
    latest = max(current_manifests, key=extract_period_from_manifest)
    return str(latest)


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

    # CRITICAL OPTIMIZATION: Determine reference BEFORE manifest generation
    # If reference exists, we can skip preview generation (saves ~60 seconds)
    reference = None
    if not skip_enrichment and not no_reference:
        reference = find_reference_manifest(pub_code, period, manual_reference)
        if reference:
            ref_name = Path(reference).name
            if is_first_of_fiscal_year(period):
                reference = None  # April baseline - fresh LLM enrichment

    # Step 1: Generate manifest (using library)
    if display:
        display.update_progress("manifest")

    stage_start = datetime.now()
    # Skip preview generation if:
    # 1. skip_enrichment is True (explicitly skipping enrichment)
    # 2. reference exists (will use reference matching, no LLM needed)
    skip_preview = skip_enrichment or (reference is not None)
    result = generate_manifest(url, draft_manifest, event_store, skip_preview=skip_preview)
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

        # Reference already determined above (for skip_preview optimization)
        if no_reference:
            reference = None

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


def show_status(config: dict):
    """Show processing status from DATABASE (single source of truth)."""
    print("\n" + "=" * 80)
    print("DataWarp Status Report")
    print("=" * 80)

    from datawarp.storage.connection import get_connection

    # Get all loaded periods from database
    loaded_periods = set()
    total_rows = 0
    table_count = 0
    last_load = None

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Get staging tables
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = 'staging'
            """)
            table_count = cursor.fetchone()[0]

            # Get loaded periods and stats
            cursor.execute("""
                SELECT period, SUM(rows_loaded), MAX(loaded_at)
                FROM datawarp.tbl_manifest_files
                WHERE status = 'loaded'
                GROUP BY period
            """)
            for row in cursor.fetchall():
                loaded_periods.add(row[0])
                total_rows += row[1] or 0
                if row[2] and (last_load is None or row[2] > last_load):
                    last_load = row[2]

            print()
            print("📊 Database Status:")
            print(f"  • {table_count} tables in staging schema")
            print(f"  • {total_rows:,} total rows loaded")
            print(f"  • {len(loaded_periods)} periods loaded")
            print(f"  • Last load: {last_load.strftime('%Y-%m-%d %H:%M:%S') if last_load else 'Never'}")
            print()

    except Exception as e:
        print(f"\n⚠️  Could not connect to database: {e}\n")
        return

    # Publication status
    total_periods = 0
    processed_count = 0
    pending_count = 0

    print("📋 Publication Status:")
    print()

    for pub_code, pub_config in config.get("publications", {}).items():
        periods = get_all_periods(pub_config)
        if not periods:
            continue

        pub_processed = 0
        pub_pending = 0

        for period in periods:
            total_periods += 1
            if period in loaded_periods:
                pub_processed += 1
                processed_count += 1
            else:
                pub_pending += 1
                pending_count += 1

        # Progress bar
        total = pub_processed + pub_pending
        if total > 0:
            bar_len = 30
            filled = int(bar_len * pub_processed / total)
            bar = "█" * filled + "░" * (bar_len - filled)
            status = "✅" if pub_pending == 0 else "⏳"

            print(f"{pub_config['name'][:50]:<50}")
            print(f"  {bar} {pub_processed}/{total} {status}")

            if pub_pending > 0:
                print(f"  ⏳ {pub_pending} pending")

            print()

    print("─" * 80)
    print(f"\n📈 Overall Progress:")
    print(f"  • Total periods: {total_periods}")
    print(f"  • ✅ Processed: {processed_count}")
    print(f"  • ⏳ Pending: {pending_count}")
    print()

    if pending_count > 0:
        print("💡 Next steps:")
        print(f"  • Process pending: python scripts/backfill.py")
        print()
    else:
        print("✅ All publications up to date!")
        print()
        print("💡 Next steps:")
        print("  • Query data: psql -d datawarp2")
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
  python scripts/backfill.py --pub adhd                    # Process one publication
  python scripts/backfill.py --pub adhd --period 2025-04  # Process one period
  python scripts/backfill.py --dry-run                    # Show what would run
  python scripts/backfill.py --status         # Show progress
  python scripts/backfill.py --quiet          # Minimal output (only warnings/errors)
        """
    )
    parser.add_argument("--config", help="Path to config file (default: config/publications.yaml)")
    parser.add_argument("--pub", help="Process only this publication")
    parser.add_argument("--period", help="Process only this period (e.g., 2025-04, FY25-Q1)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed")
    parser.add_argument("--status", action="store_true", help="Show current status (from database)")
    parser.add_argument("--force", action="store_true", help="Force reload even if already in database")
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

    # VALIDATE CONFIG BEFORE DOING ANYTHING
    # Catches truncated URLs, missing fields, etc.
    errors, warnings = validate_config(config, args.pub if hasattr(args, 'pub') else None)

    if errors:
        print()
        print("❌ CONFIG VALIDATION FAILED")
        print()
        print("The following issues must be fixed before processing:")
        print()
        for error in errors:
            print(f"  ✗ {error}")
        print()
        if warnings:
            print("Warnings (non-blocking):")
            for warning in warnings:
                print(f"  ⚠ {warning}")
            print()
        print("💡 Fix the config file and try again")
        print()
        sys.exit(1)

    if warnings and not args.quiet:
        print()
        print("⚠️  Config warnings (non-blocking):")
        for warning in warnings:
            print(f"  • {warning}")
        print()

    if args.status:
        show_status(config)
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

    # Note: --retry-failed removed. Use --force to reload any period.
    # Database is single source of truth - no separate "failed" tracking needed.

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

                # Skip if --period specified and this isn't it
                if args.period and period != args.period:
                    continue

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

                # Skip if already loaded in database (unless --force)
                if is_period_loaded(pub_code, period) and not args.force:
                    event_store.emit(create_event(
                        EventType.WARNING,
                        run_id,
                        message=f"Skipping {period} - already in database",
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
                    processed += 1
                    # Aggregate stats
                    total_rows += period_stats.get('rows', 0)
                    total_sources += period_stats.get('sources', 0)
                    total_columns += period_stats.get('columns', 0)
                    processed_details.append(period_stats)
                else:
                    failed += 1
                # Note: No state.json tracking - database IS the state

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

        # INTELLIGENT UX: Explain what happened
        if processed == 0 and skipped == 0 and failed == 0:
            print()
            print("ℹ️  NO PERIODS TO PROCESS")
            print()
            print("Possible reasons:")
            print("  • Publication has no periods in configured date range")
            print("  • Check config file for period definitions")
            print()
            print(f"💡 Tip: Run with --dry-run to see what periods would be processed")

        elif skipped > 0 and processed == 0:
            # All periods already in database
            print()
            print("✅ ALL DATA UP TO DATE")
            print()
            print(f"📋 {skipped} period(s) already loaded in database")
            print()
            print("💡 Next steps:")
            print("  • Query data: psql -d datawarp2")
            print("  • Export to Parquet: python scripts/export_to_parquet.py --publication <name>")
            print("  • Reload anyway: Re-run with --force flag")

        elif failed > 0:
            print()
            print("⚠️  SOME PERIODS FAILED")
            print()
            print("💡 Next steps:")
            print(f"  • Check logs: tail -100 logs/backfill_*.log | grep ERROR")
            print("  • Force retry: python scripts/backfill.py --force")


if __name__ == "__main__":
    main()
