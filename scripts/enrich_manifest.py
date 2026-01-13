#!/usr/bin/env python3
"""DataWarp Manifest Enrichment CLI (v2.2 - Thin Wrapper).

Thin CLI wrapper around datawarp.pipeline.enrich_manifest library.

Usage:
    python enrich_manifest.py input.yaml output.yaml
    python enrich_manifest.py input.yaml output.yaml --reference ref.yaml
    python enrich_manifest.py input.yaml output.yaml --dry-run
"""
import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from datawarp.pipeline import enrich_manifest


def main():
    parser = argparse.ArgumentParser(
        description='Enrich DataWarp manifest with semantic metadata using Gemini LLM',
        epilog='Example: python enrich_manifest.py input.yaml output.yaml'
    )
    parser.add_argument('input', help='Input manifest YAML file')
    parser.add_argument('output', nargs='?', help='Output manifest YAML file (default: input_enriched.yaml)')
    parser.add_argument('--reference', default=None,
                        help='Reference manifest for comparison (default: None = fresh LLM enrichment)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without writing output')

    args = parser.parse_args()

    # Auto-generate output filename if not provided
    if args.output is None:
        input_path = Path(args.input)
        output_name = input_path.stem + '_enriched' + input_path.suffix
        args.output = str(input_path.parent / output_name)
        print(f"Output file not specified, using: {args.output}")

    # Validate output filename
    if args.output == 'output':
        print("Error: 'output' is not a valid filename. Please specify a proper output file.")
        print(f"   Suggestion: {Path(args.input).stem}_enriched.yaml")
        sys.exit(1)

    if args.dry_run:
        print(f"DRY RUN: Would enrich {args.input} -> {args.output}")
        if args.reference:
            print(f"  Using reference: {args.reference}")
        sys.exit(0)

    # Call library function
    result = enrich_manifest(
        input_path=args.input,
        output_path=args.output,
        reference_path=args.reference,
        event_store=None,  # CLI doesn't use EventStore
        publication=None,
        period=None
    )

    if result.success:
        print(f"\nEnrichment complete!")
        print(f"  Sources enriched: {result.sources_enriched}")
        print(f"  Sources from reference: {result.sources_from_reference}")
        print(f"  Total sources: {result.sources_total}")
        if result.llm_calls_made > 0:
            print(f"  LLM tokens: {result.input_tokens:,} in, {result.output_tokens:,} out")
        print(f"  Output: {result.output_path}")
        sys.exit(0)
    else:
        print(f"\nEnrichment failed: {result.error}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
