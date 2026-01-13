#!/usr/bin/env python3
"""Generate DataWarp manifest from ANY NHS publication URL (ZIP/XLSX/CSV).

Usage:
    python url_to_manifest.py <publication_url> <output_manifest.yaml>

Example:
    python url_to_manifest.py \\
        "https://digital.nhs.uk/.../april-2025" \\
        manifests/gp_apr_2025.yaml

NOTE: This is a thin CLI wrapper around datawarp.pipeline.manifest library (v2.2+)
"""

import sys
from pathlib import Path

from datawarp.pipeline import generate_manifest


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('url', help='Publication URL')
    parser.add_argument('output', help='Output manifest file')
    parser.add_argument('--skip-preview', action='store_true',
                       help='Skip downloading files for content previews')

    args = parser.parse_args()

    # Generate manifest using library
    result = generate_manifest(
        url=args.url,
        output_path=Path(args.output),
        event_store=None,  # CLI doesn't use EventStore (backfill.py does)
        skip_preview=args.skip_preview
    )

    if result.success:
        print(f"\n✅ Generated {result.sources_count} sources with {result.files_count} files", file=sys.stderr)
        print(f"📝 Written to {result.manifest_path}", file=sys.stderr)
        print(f"👀 Review and edit to remove unwanted sheets/sources", file=sys.stderr)
        print(f"🚀 Load: datawarp load-batch {result.manifest_path}", file=sys.stderr)
        sys.exit(0)
    else:
        print(f"❌ Failed: {result.error}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
