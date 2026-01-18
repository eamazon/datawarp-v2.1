#!/usr/bin/env python
"""Test pattern compression with a single RTT provider file.

Shows compression → LLM enrichment → expansion pipeline in detail.

Usage:
    python scripts/test_pattern_compression.py
"""
import sys
import json
import yaml
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from datawarp.pipeline.manifest import generate_manifest
from datawarp.pipeline.enricher import enrich_manifest
from datawarp.pipeline.column_compressor import (
    compress_manifest_for_enrichment,
    expand_manifest_from_enrichment,
    detect_sequential_pattern
)


def print_section(title: str):
    """Print formatted section header."""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")


def analyze_columns(preview: dict, label: str):
    """Analyze and display column structure."""
    columns = preview.get('columns', [])
    pattern_info = preview.get('pattern_info')

    print(f"{label}:")
    print(f"  Total columns: {len(columns)}")

    if pattern_info:
        print(f"  Pattern detected: {pattern_info['pattern']}")
        print(f"  Pattern count: {pattern_info['count']}")
        print(f"  Sample columns: {pattern_info['sample_columns']}")

    # Group columns by prefix
    from collections import defaultdict
    prefixes = defaultdict(int)
    for col in columns:
        prefix = col.split('_')[0] if '_' in col else col
        prefixes[prefix] += 1

    print(f"  Column groups:")
    for prefix, count in sorted(prefixes.items(), key=lambda x: -x[1])[:5]:
        print(f"    - {prefix}*: {count} columns")

    print(f"  First 5 columns: {columns[:5]}")
    print(f"  Last 3 columns: {columns[-3:]}")
    print()


def test_single_file():
    """Test pattern compression with single RTT provider file."""

    # RTT Provider file (April 2025)
    url = "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2025/06/Incomplete-Provider-Apr25-XLSX-9M-77252.xlsx"

    print_section("STEP 1: GENERATE MANIFEST (with full column preview)")

    manifest_path = Path("manifests/test/rtt_provider_apr25_test.yaml")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"URL: {url}")
    print(f"Generating manifest to: {manifest_path}\n")

    result = generate_manifest(url, manifest_path)

    if not result.success:
        print(f"❌ Manifest generation failed: {result.error}")
        return

    print(f"✅ Manifest generated: {result.sources_count} sources, {result.files_count} files\n")

    # Load manifest
    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    sources = manifest.get('sources', [])
    print(f"Sources in manifest: {len(sources)}")

    # Analyze first source
    if sources:
        first_source = sources[0]
        files = first_source.get('files', [])
        print(f"Files in first source: {len(files)}\n")

        if files:
            first_file = files[0]
            preview = first_file.get('preview', {})
            analyze_columns(preview, "ORIGINAL COLUMNS (before compression)")

            # Show pattern detection
            columns = preview.get('columns', [])
            pattern = detect_sequential_pattern(columns)

            if pattern:
                print(f"📊 Pattern Detection Results:")
                print(f"   Pattern: {pattern['pattern']}")
                print(f"   Count: {pattern['count']} columns")
                print(f"   Prefix: {pattern['prefix']}")
                print(f"   Sequential columns detected: {len(pattern['columns'])}")
                print()

    print_section("STEP 2: COMPRESS FOR LLM")

    # Compress manifest
    compressed_sources, compression_map = compress_manifest_for_enrichment(sources)

    print(f"Compression map keys: {list(compression_map.keys())}\n")

    if compression_map:
        for key, pattern in compression_map.items():
            print(f"Compressed pattern {key}:")
            print(f"  Pattern: {pattern['pattern']}")
            print(f"  Original count: {pattern['count']} columns")
            print(f"  Compressed to: {len(pattern['columns'][:2] + pattern['columns'][-1:])} samples")
            print()

    # Show compressed columns
    if compressed_sources:
        compressed_file = compressed_sources[0]['files'][0]
        compressed_preview = compressed_file.get('preview', {})
        analyze_columns(compressed_preview, "COMPRESSED COLUMNS (sent to LLM)")

    # Calculate token savings
    original_cols = sum(len(f.get('preview', {}).get('columns', []))
                       for s in sources for f in s.get('files', []))
    compressed_cols = sum(len(f.get('preview', {}).get('columns', []))
                         for s in compressed_sources for f in s.get('files', []))

    print(f"📉 Compression Statistics:")
    print(f"   Original: {original_cols} columns")
    print(f"   Compressed: {compressed_cols} columns")
    print(f"   Reduction: {original_cols - compressed_cols} columns ({100*(original_cols-compressed_cols)/original_cols:.1f}%)")
    print(f"   Estimated token savings: ~{(original_cols - compressed_cols) * 50} tokens")
    print()

    # Save compressed manifest for inspection
    compressed_manifest_path = Path("manifests/test/rtt_provider_apr25_compressed.yaml")
    compressed_manifest = {
        'manifest': manifest['manifest'],
        'sources': compressed_sources
    }
    with open(compressed_manifest_path, 'w') as f:
        yaml.dump(compressed_manifest, f, default_flow_style=False, sort_keys=False)

    print(f"💾 Compressed manifest saved to: {compressed_manifest_path}")
    print(f"   (Inspect this to see what LLM receives)\n")

    print_section("STEP 3: LLM ENRICHMENT")

    print("⚠️  This step will call the actual Gemini API")
    print("   Cost: ~$0.03 per file")
    print()

    response = input("Continue with LLM enrichment? (y/n): ").strip().lower()

    if response != 'y':
        print("\n❌ Stopped before LLM call")
        print(f"\n📁 Files created for inspection:")
        print(f"   Original: {manifest_path}")
        print(f"   Compressed: {compressed_manifest_path}")
        return

    print("\n🔄 Calling LLM for enrichment...")

    # Create enriched manifest path
    enriched_manifest_path = Path("manifests/test/rtt_provider_apr25_enriched.yaml")

    # Enrich the compressed manifest
    enrich_result = enrich_manifest(
        input_path=str(compressed_manifest_path),
        output_path=str(enriched_manifest_path)
    )

    if not enrich_result.success:
        print(f"\n❌ Enrichment failed: {enrich_result.error}")
        return

    print(f"\n✅ Enrichment successful!")
    print(f"   Sources enriched: {enrich_result.sources_enriched}")
    print(f"   Input tokens: {enrich_result.input_tokens:,}")
    print(f"   Output tokens: {enrich_result.output_tokens:,}")
    print(f"   Latency: {enrich_result.latency_ms/1000:.1f}s")
    print(f"   Cost: ${(enrich_result.input_tokens * 0.000001 + enrich_result.output_tokens * 0.000004):.4f}")
    print()

    # Load enriched manifest
    with open(enriched_manifest_path) as f:
        enriched_manifest = yaml.safe_load(f)

    enriched_sources = enriched_manifest.get('sources', [])

    # Show enriched columns (still compressed)
    if enriched_sources:
        enriched_file = enriched_sources[0].get('files', [{}])[0]
        enriched_cols = enriched_file.get('columns', {})

        print(f"📝 LLM Output (compressed columns):")
        print(f"   Enriched columns: {len(enriched_cols)}")

        # Show sample enriched column
        if enriched_cols:
            sample_col_name = list(enriched_cols.keys())[0]
            sample_col = enriched_cols[sample_col_name]
            print(f"\n   Sample enriched column '{sample_col_name}':")
            print(f"     pg_name: {sample_col.get('pg_name')}")
            print(f"     description: {sample_col.get('description', '')[:80]}...")
            print(f"     metadata: {json.dumps(sample_col.get('metadata', {}), indent=10)}")
        print()

    print_section("STEP 4: EXPAND BACK TO FULL COLUMN SET")

    print("🔄 Expanding compressed columns using pattern metadata...\n")

    # Expand manifest
    expanded_sources = expand_manifest_from_enrichment(enriched_sources, compression_map)

    # Show expanded columns
    if expanded_sources:
        expanded_file = expanded_sources[0].get('files', [{}])[0]
        expanded_cols = expanded_file.get('columns', {})

        print(f"✅ Expansion complete!")
        print(f"   Final columns: {len(expanded_cols)}")
        print()

        # Show sample expanded columns
        print(f"   Sample expanded columns:")
        for col_name in list(expanded_cols.keys())[:3]:
            col_meta = expanded_cols[col_name]
            print(f"\n   Column: {col_name}")
            print(f"     pg_name: {col_meta.get('pg_name')}")
            print(f"     description: {col_meta.get('description', '')[:60]}...")

        # Verify all pattern columns exist
        if compression_map:
            first_pattern = list(compression_map.values())[0]
            pattern_cols = first_pattern['columns']

            print(f"\n   Pattern column verification:")
            print(f"     Expected: {len(pattern_cols)} columns")
            print(f"     Found: {sum(1 for col in pattern_cols if col in expanded_cols)} columns")

            missing = [col for col in pattern_cols if col not in expanded_cols]
            if missing:
                print(f"     ⚠️  Missing: {len(missing)} columns")
                print(f"        First missing: {missing[:3]}")
            else:
                print(f"     ✅ All pattern columns present!")
        print()

    # Save final expanded manifest
    final_manifest_path = Path("manifests/test/rtt_provider_apr25_final.yaml")
    final_manifest = {
        'manifest': enriched_manifest['manifest'],
        'sources': expanded_sources
    }
    with open(final_manifest_path, 'w') as f:
        yaml.dump(final_manifest, f, default_flow_style=False, sort_keys=False)

    print(f"💾 Final expanded manifest saved to: {final_manifest_path}\n")

    print_section("SUMMARY")

    print("Pipeline completed successfully! 🎉\n")

    print("📁 Generated files:")
    print(f"   1. Original manifest:   {manifest_path}")
    print(f"   2. Compressed (LLM in): {compressed_manifest_path}")
    print(f"   3. Enriched (LLM out):  {enriched_manifest_path}")
    print(f"   4. Final (expanded):    {final_manifest_path}")
    print()

    print("📊 Stats:")
    print(f"   Original columns:  {original_cols}")
    print(f"   Compressed to:     {compressed_cols} ({100*compressed_cols/original_cols:.1f}%)")
    print(f"   Expanded to:       {len(expanded_cols)} (100%)")
    print(f"   Token savings:     ~{(original_cols - compressed_cols) * 50}")
    print(f"   LLM tokens in:     {enrich_result.input_tokens:,}")
    print(f"   LLM tokens out:    {enrich_result.output_tokens:,}")
    print(f"   Cost:              ${(enrich_result.input_tokens * 0.000001 + enrich_result.output_tokens * 0.000004):.4f}")
    print()

    print("🔍 Next steps:")
    print("   1. Inspect compressed manifest to see LLM input")
    print("   2. Inspect enriched manifest to see LLM output")
    print("   3. Inspect final manifest to verify expansion")
    print("   4. Compare original vs final column metadata")
    print()


if __name__ == '__main__':
    try:
        test_single_file()
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
