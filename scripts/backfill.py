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

import yaml

from datawarp.pipeline import generate_manifest, enrich_manifest, export_publication_to_parquet
from datawarp.pipeline.canonicalize import canonicalize_manifest
from datawarp.supervisor.events import EventStore, EventType, EventLevel, create_event


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


def process_period(
    pub_code: str,
    pub_config: dict,
    period: str,
    url: str,
    event_store: EventStore,
    dry_run: bool = False,
    force: bool = False
) -> bool:
    """Process a single period for a publication."""

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
    result = generate_manifest(url, draft_manifest, event_store)
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
        return False

    # Step 2: Enrich manifest (using library)
    event_store.emit(create_event(
        EventType.STAGE_STARTED,
        event_store.run_id,
        message="Enriching manifest",
        publication=pub_code,
        period=period,
        stage="enrich"
    ))

    reference = pub_config.get("reference_manifest")
    enrich_result = enrich_manifest(
        input_path=str(draft_manifest),
        output_path=str(enriched_manifest),
        reference_path=reference if reference and Path(reference).exists() else None,
        event_store=event_store,
        publication=pub_code,
        period=period
    )

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
        return False

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

    # Step 3: Load to database (using library)
    event_store.emit(create_event(
        EventType.STAGE_STARTED,
        event_store.run_id,
        message="Loading to database",
        publication=pub_code,
        period=period,
        stage="load"
    ))

    try:
        # Load manifest and process each source
        from datawarp.loader.pipeline import load_file
        from datawarp.storage.connection import get_connection
        from datawarp.storage import repository

        with open(enriched_manifest) as f:
            manifest_data = yaml.safe_load(f)

        sources_loaded = 0
        total_rows = 0

        for source in manifest_data.get('sources', []):
            if not source.get('enabled', True):
                continue

            # Auto-register source if not exists (same logic as batch.py)
            source_code = source['code']
            with get_connection() as conn:
                source_obj = repository.get_source(source_code, conn)

                if not source_obj:
                    # Auto-register from manifest
                    source_name = source.get('name', source_code)
                    table_name = source['table']
                    schema_name = source.get('schema', 'staging')
                    default_sheet = source.get('sheet')

                    event_store.emit(create_event(
                        EventType.WARNING,
                        event_store.run_id,
                        message=f"Auto-registering source: {source_code} → {schema_name}.{table_name}",
                        publication=pub_code,
                        period=period,
                        level=EventLevel.INFO,
                        context={'source_code': source_code, 'table': f"{schema_name}.{table_name}"}
                    ))

                    repository.create_source(
                        code=source_code,
                        name=source_name,
                        table_name=table_name,
                        schema_name=schema_name,
                        default_sheet=default_sheet,
                        conn=conn
                    )

            for file_info in source.get('files', []):
                # For ZIP files, use 'extract' field; for Excel, use 'sheet' field
                sheet_or_extract = file_info.get('sheet') or file_info.get('extract')

                result = load_file(
                    url=file_info['url'],
                    source_id=source['code'],
                    sheet_name=sheet_or_extract,
                    mode=file_info.get('mode', 'append'),
                    force=force,
                    period=period,
                    event_store=event_store,
                    publication=pub_code
                )

                if result.success:
                    sources_loaded += 1
                    total_rows += result.rows_loaded

                    # Store column metadata from manifest (for Parquet export)
                    if source.get('columns'):
                        try:
                            with get_connection() as conn:
                                stored_count = repository.store_column_metadata(
                                    canonical_source_code=source_code,
                                    columns=source['columns'],
                                    conn=conn
                                )
                                if stored_count > 0:
                                    event_store.emit(create_event(
                                        EventType.STAGE_COMPLETED,
                                        event_store.run_id,
                                        message=f"Stored metadata for {stored_count} columns",
                                        publication=pub_code,
                                        period=period,
                                        stage="metadata",
                                        level=EventLevel.DEBUG
                                    ))
                        except Exception as e:
                            event_store.emit(create_event(
                                EventType.WARNING,
                                event_store.run_id,
                                message=f"Failed to store column metadata: {str(e)}",
                                publication=pub_code,
                                period=period,
                                level=EventLevel.WARNING,
                                error=str(e)
                            ))
                else:
                    event_store.emit(create_event(
                        EventType.WARNING,
                        event_store.run_id,
                        message=f"Failed to load source {source['code']}: {result.error}",
                        publication=pub_code,
                        period=period,
                        level=EventLevel.WARNING,
                        error=result.error
                    ))

        event_store.emit(create_event(
            EventType.STAGE_COMPLETED,
            event_store.run_id,
            message=f"Load completed: {sources_loaded} sources, {total_rows:,} rows",
            publication=pub_code,
            period=period,
            stage="load",
            context={'sources_loaded': sources_loaded, 'total_rows': total_rows}
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
        return False

    # Step 4: Export to parquet (using library)
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
    return True


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
        """
    )
    parser.add_argument("--config", help="Path to config file (default: config/publications.yaml)")
    parser.add_argument("--pub", help="Process only this publication")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed")
    parser.add_argument("--status", action="store_true", help="Show current status")
    parser.add_argument("--retry-failed", action="store_true", help="Retry failed items")
    parser.add_argument("--force", action="store_true", help="Force reload even if already processed")

    args = parser.parse_args()

    # Load config file
    config_path = Path(args.config) if args.config else None
    config = load_config(config_path)
    state = load_state()

    if args.status:
        show_status(config, state)
        return

    # Create EventStore
    run_id = f"backfill_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    with EventStore(run_id, LOGS_DIR) as event_store:

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
                key = f"{pub_code}/{period}"

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
                success = process_period(pub_code, pub_config, period, url, event_store, args.dry_run, args.force)

                if success:
                    if not args.dry_run:
                        mark_processed(state, pub_code, period)
                    processed += 1
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


if __name__ == "__main__":
    main()
