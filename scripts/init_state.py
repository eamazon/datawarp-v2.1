#!/usr/bin/env python3
"""
Initialize state.json from existing manifests.

Scans the manifests directory to find what's already been processed and creates
state/state.json so backfill.py knows what to skip.

Usage:
    python scripts/init_state.py              # Initialize from manifests
    python scripts/init_state.py --dry-run    # Show what would be saved
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
STATE_FILE = PROJECT_ROOT / "state" / "state.json"
MANIFESTS_DIR = PROJECT_ROOT / "manifests"


def extract_pub_period_from_manifest(manifest_path: Path) -> tuple[str, str] | None:
    """
    Extract publication and period from manifest filename.

    Examples:
        adhd_aug25_enriched.yaml -> (adhd, aug25)
        online_consultation_mar25_enriched.yaml -> (online_consultation, mar25)
        pcn_workforce_nov25_canonical.yaml -> (pcn_workforce, nov25)
    """
    name = manifest_path.stem  # Remove .yaml

    # Remove suffixes
    for suffix in ['_enriched', '_canonical', '_draft', '_llm_response']:
        name = name.replace(suffix, '')

    # Extract period (last part that matches mon25 pattern)
    period_match = re.search(r'_([a-z]{3}\d{2})$', name)
    if period_match:
        period = period_match.group(1)
        pub_code = name[:name.rfind('_')]
        return (pub_code, period)

    return None


def scan_manifests() -> list[tuple[str, str, Path]]:
    """Scan manifests directory for processed manifests."""
    results = []

    # Look for enriched or canonical manifests (these indicate processing was done)
    for pattern in ['**/*_enriched.yaml', '**/*_canonical.yaml']:
        for manifest in MANIFESTS_DIR.glob(pattern):
            result = extract_pub_period_from_manifest(manifest)
            if result:
                pub_code, period = result
                results.append((pub_code, period, manifest))

    return results


def main():
    parser = argparse.ArgumentParser(description="Initialize state from manifests")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be saved")
    args = parser.parse_args()

    print("=" * 60)
    print("Initialize State from Manifests")
    print("=" * 60)
    print(f"Scanning: {MANIFESTS_DIR}")

    manifests = scan_manifests()
    print(f"Found {len(manifests)} processed manifests")

    # Build state
    state = {
        "processed": {},
        "failed": {},
        "initialized_at": datetime.now().isoformat(),
        "initialized_from": "manifests"
    }

    for pub_code, period, manifest_path in manifests:
        key = f"{pub_code}/{period}"

        # Use the more recent manifest if duplicates
        if key not in state["processed"]:
            state["processed"][key] = {
                "manifest": str(manifest_path.relative_to(PROJECT_ROOT)),
                "completed_at": datetime.fromtimestamp(manifest_path.stat().st_mtime).isoformat(),
                "from_manifests": True
            }

    # Summary
    print(f"\nState entries: {len(state['processed'])}")

    by_pub = {}
    for key in state["processed"]:
        pub = key.split("/")[0]
        by_pub[pub] = by_pub.get(pub, 0) + 1

    print("\nBy publication:")
    for pub, count in sorted(by_pub.items()):
        print(f"  {pub}: {count} periods")

    # Show details
    print("\nProcessed periods:")
    for key in sorted(state["processed"].keys()):
        info = state["processed"][key]
        print(f"  {key}: {info['manifest']}")

    if args.dry_run:
        print("\n[DRY RUN] Would save to:", STATE_FILE)
    else:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2, default=str))
        print(f"\nState saved to: {STATE_FILE}")


if __name__ == "__main__":
    main()
