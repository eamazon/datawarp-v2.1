#!/usr/bin/env python3
"""
DataWarp Backfill Script

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
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_FILE = PROJECT_ROOT / "config" / "publications.yaml"
STATE_FILE = PROJECT_ROOT / "state" / "state.json"
MANIFESTS_DIR = PROJECT_ROOT / "manifests" / "backfill"
LOGS_DIR = PROJECT_ROOT / "logs"

# Setup logger
logger = logging.getLogger("backfill")


def setup_logging(verbose: bool = False):
    """Setup logging to console and file."""
    log_level = logging.DEBUG if verbose else logging.INFO

    # Create logs directory
    LOGS_DIR.mkdir(exist_ok=True)

    # Log file with date
    log_file = LOGS_DIR / f"backfill_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    # File handler (detailed)
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)

    # Console handler (cleaner)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)

    # Configure root logger
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info(f"Logging to: {log_file}")
    return log_file


def load_config(config_path: Path = None) -> dict:
    """Load publications config."""
    config_file = config_path if config_path else CONFIG_FILE
    if not config_file.exists():
        logger.error(f"Config file not found: {config_file}")
        sys.exit(1)
    logger.debug(f"Loading config from: {config_file}")
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


def run_command(cmd: list, desc: str) -> tuple[bool, str]:
    """Run a command and return success status and output."""
    logger.info(f"  Running: {desc}")
    logger.debug(f"  Command: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )
        if result.returncode != 0:
            logger.debug(f"  Command failed (exit {result.returncode})")
            return False, result.stderr or result.stdout
        logger.debug(f"  Command succeeded")
        return True, result.stdout
    except Exception as e:
        logger.error(f"  Exception running command: {e}")
        return False, str(e)


def process_period(pub_code: str, pub_config: dict, period: str, url: str, dry_run: bool = False) -> bool:
    """Process a single period for a publication."""

    logger.info(f"\n{'='*60}")
    logger.info(f"Processing: {pub_code}/{period}")
    logger.info(f"  URL: {url}")

    if dry_run:
        logger.info("  [DRY RUN] Would process this URL")
        return True

    # Create manifest directory
    manifest_dir = MANIFESTS_DIR / pub_code
    manifest_dir.mkdir(parents=True, exist_ok=True)

    draft_manifest = manifest_dir / f"{pub_code}_{period}.yaml"
    enriched_manifest = manifest_dir / f"{pub_code}_{period}_enriched.yaml"

    logger.debug(f"  Draft manifest: {draft_manifest}")
    logger.debug(f"  Enriched manifest: {enriched_manifest}")

    # Step 1: Generate manifest
    logger.info("  Step 1/4: Generating manifest...")
    success, output = run_command(
        ["python", "scripts/url_to_manifest.py", url, str(draft_manifest)],
        "url_to_manifest.py"
    )
    if not success:
        logger.error(f"  Manifest generation failed")
        logger.debug(f"  Error output: {output[:500]}")
        return False
    logger.info("  [OK] Manifest generated")

    # Step 2: Enrich manifest
    logger.info("  Step 2/4: Enriching manifest...")
    reference = pub_config.get("reference_manifest")
    if reference and Path(reference).exists():
        # Use reference enrichment
        logger.debug(f"  Using reference: {Path(reference).name}")
        success, output = run_command(
            ["python", "scripts/enrich_manifest.py", str(draft_manifest), str(enriched_manifest), "--reference", reference],
            f"enrich_manifest.py --reference {Path(reference).name}"
        )
    else:
        # First period: use LLM enrichment
        logger.debug("  First period - using LLM enrichment")
        success, output = run_command(
            ["python", "scripts/enrich_manifest.py", str(draft_manifest), str(enriched_manifest)],
            "enrich_manifest.py (LLM)"
        )
        # Set as reference for future periods
        if success and not pub_config.get("reference_manifest"):
            logger.info(f"  Setting {enriched_manifest.name} as reference for future {pub_code} periods")
            # Note: This doesn't update the YAML file, just for this run

    if not success:
        logger.error(f"  Enrichment failed")
        logger.debug(f"  Error output: {output[:500]}")
        return False
    logger.info("  [OK] Manifest enriched")

    # Step 3: Load to database
    logger.info("  Step 3/4: Loading to database...")
    success, output = run_command(
        ["datawarp", "load-batch", str(enriched_manifest)],
        "datawarp load-batch"
    )
    if not success:
        logger.error(f"  Database load failed")
        logger.debug(f"  Error output: {output[:500]}")
        return False

    # Parse output for row counts
    if "rows loaded" in output.lower():
        logger.info(f"  [OK] Data loaded to database")
    else:
        logger.info("  [OK] Database load complete")

    # Step 4: Export to parquet (only the publication we just loaded)
    logger.info("  Step 4/4: Exporting to Parquet...")
    success, output = run_command(
        ["python", "scripts/export_to_parquet.py", "--publication", pub_code],
        "export_to_parquet.py"
    )
    if not success:
        logger.warning(f"  Export failed (non-fatal)")
        logger.debug(f"  Error output: {output[:500]}")
        # Don't fail the whole process for export issues
    else:
        logger.info("  [OK] Exported to Parquet")

    logger.info(f"  [SUCCESS] {pub_code}/{period} processed")
    logger.info(f"{'='*60}\n")
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
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Setup logging
    log_file = setup_logging(verbose=args.verbose)

    # Load config file
    config_path = Path(args.config) if args.config else None
    config = load_config(config_path)
    state = load_state()

    if args.status:
        show_status(config, state)
        return

    logger.info("=" * 60)
    logger.info("DataWarp Backfill")
    logger.info("=" * 60)
    logger.info(f"Config: {CONFIG_FILE}")
    logger.info(f"State:  {STATE_FILE}")
    logger.info(f"Mode:   {'DRY RUN' if args.dry_run else 'EXECUTE'}")

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

        logger.info(f"\n--- {pub_config['name']} ({len(urls)} periods) ---")

        for release in urls:
            period = release["period"]
            url = release["url"]
            key = f"{pub_code}/{period}"

            # Skip if already processed (unless retrying failed)
            if is_processed(state, pub_code, period):
                logger.info(f"  [SKIP] {period} - already processed")
                skipped += 1
                continue

            # Skip failed unless --retry-failed
            if key in state.get("failed", {}) and not args.retry_failed:
                logger.info(f"  [SKIP] {period} - previously failed (use --retry-failed)")
                skipped += 1
                continue

            # Process this period
            success = process_period(pub_code, pub_config, period, url, args.dry_run)

            if success:
                if not args.dry_run:
                    mark_processed(state, pub_code, period)
                processed += 1
            else:
                if not args.dry_run:
                    mark_failed(state, pub_code, period, "See log for details")
                failed += 1

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Summary")
    logger.info("=" * 60)
    logger.info(f"Processed: {processed}")
    logger.info(f"Skipped:   {skipped}")
    logger.info(f"Failed:    {failed}")

    if not args.dry_run and processed > 0:
        logger.info(f"\nState saved to: {STATE_FILE}")
        logger.info(f"Log saved to: {log_file}")


if __name__ == "__main__":
    main()
