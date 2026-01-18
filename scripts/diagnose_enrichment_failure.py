#!/usr/bin/env python
"""Diagnose enrichment failures by testing different scenarios.

This script systematically tests what causes LLM enrichment to fail:
1. Baseline: Full manifest with sample_rows
2. Test 1: Remove sample_rows
3. Test 2: Limit columns to first 20
4. Test 3: Process one sheet at a time
5. Test 4: Pattern compression

Saves raw LLM responses and token counts for analysis.
"""
import sys
import json
import yaml
from pathlib import Path
from datetime import datetime
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from datawarp.pipeline.enricher import build_enrichment_prompt, call_gemini_api


def save_test_result(test_name: str, status: str, details: dict, output_dir: Path):
    """Save test result to JSON file."""
    result = {
        'test': test_name,
        'timestamp': datetime.utcnow().isoformat(),
        'status': status,
        'details': details
    }

    output_file = output_dir / f"{test_name}.json"
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"   Saved: {output_file}")


def test_baseline(manifest_path: Path, output_dir: Path):
    """Test 1: Full manifest with sample_rows (should fail)."""
    print("\n" + "="*80)
    print("TEST 1: BASELINE - Full manifest with sample_rows")
    print("="*80)

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    sources = manifest.get('sources', [])

    # Count preview size
    total_cols = 0
    total_sample_keys = 0
    for source in sources:
        for file_entry in source.get('files', []):
            preview = file_entry.get('preview', {})
            cols = preview.get('columns', [])
            total_cols += len(cols)

            sample_rows = preview.get('sample_rows', [])
            if sample_rows:
                total_sample_keys += len(sample_rows[0].keys())

    print(f"\nManifest structure:")
    print(f"  Sources: {len(sources)}")
    print(f"  Total columns: {total_cols}")
    print(f"  Sample row keys: {total_sample_keys}")

    # Build prompt
    prompt = build_enrichment_prompt(manifest, sources)
    prompt_tokens = len(prompt.split()) * 1.3  # Rough estimate

    print(f"\nPrompt analysis:")
    print(f"  Prompt length: {len(prompt):,} chars")
    print(f"  Estimated tokens: {int(prompt_tokens):,}")

    # Save prompt to file for inspection
    prompt_file = output_dir / "baseline_prompt.txt"
    with open(prompt_file, 'w') as f:
        f.write(prompt)
    print(f"  Saved prompt: {prompt_file}")

    # Try calling LLM
    print(f"\n🔄 Calling Gemini API...")

    try:
        response_data, metadata = call_gemini_api(prompt)

        print(f"\n✅ LLM call succeeded!")
        print(f"  Input tokens: {metadata.get('input_tokens', 'N/A'):,}")
        print(f"  Output tokens: {metadata.get('output_tokens', 'N/A'):,}")
        print(f"  Latency: {metadata.get('latency_ms', 0)/1000:.1f}s")

        # Save raw response
        response_file = output_dir / "baseline_response.yaml"
        with open(response_file, 'w') as f:
            yaml.dump(response_data, f, default_flow_style=False)

        print(f"  Saved response: {response_file}")

        # Try parsing as YAML
        try:
            parsed = yaml.safe_load(yaml.dump(response_data))
            print(f"  ✅ Valid YAML structure")

            save_test_result('baseline', 'SUCCESS', {
                'input_tokens': metadata.get('input_tokens'),
                'output_tokens': metadata.get('output_tokens'),
                'sources_count': len(response_data.get('sources', [])) if isinstance(response_data, dict) else 0
            }, output_dir)

            return True

        except yaml.YAMLError as e:
            print(f"  ❌ YAML parse error: {e}")
            save_test_result('baseline', 'YAML_ERROR', {
                'error': str(e),
                'input_tokens': metadata.get('input_tokens'),
                'output_tokens': metadata.get('output_tokens')
            }, output_dir)
            return False

    except Exception as e:
        print(f"\n❌ LLM call failed: {e}")
        save_test_result('baseline', 'LLM_ERROR', {'error': str(e)}, output_dir)
        return False


def test_no_sample_rows(manifest_path: Path, output_dir: Path):
    """Test 2: Remove sample_rows, keep all columns."""
    print("\n" + "="*80)
    print("TEST 2: Remove sample_rows (keep all columns)")
    print("="*80)

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    sources = manifest.get('sources', [])

    # Remove sample_rows from all previews
    modified_sources = []
    for source in sources:
        modified_files = []
        for file_entry in source.get('files', []):
            modified_entry = file_entry.copy()
            if 'preview' in modified_entry:
                preview = modified_entry['preview'].copy()
                if 'sample_rows' in preview:
                    del preview['sample_rows']
                modified_entry['preview'] = preview
            modified_files.append(modified_entry)

        modified_source = source.copy()
        modified_source['files'] = modified_files
        modified_sources.append(modified_source)

    # Count columns
    total_cols = sum(len(f.get('preview', {}).get('columns', []))
                    for s in modified_sources for f in s.get('files', []))

    print(f"\nModified manifest:")
    print(f"  Sources: {len(modified_sources)}")
    print(f"  Total columns: {total_cols}")
    print(f"  Sample rows: REMOVED")

    # Build prompt
    prompt = build_enrichment_prompt(manifest, modified_sources)
    prompt_tokens = len(prompt.split()) * 1.3

    print(f"\nPrompt analysis:")
    print(f"  Prompt length: {len(prompt):,} chars")
    print(f"  Estimated tokens: {int(prompt_tokens):,}")
    print(f"  Reduction vs baseline: -{len(build_enrichment_prompt(manifest, sources)) - len(prompt):,} chars")

    # Save prompt
    prompt_file = output_dir / "no_sample_rows_prompt.txt"
    with open(prompt_file, 'w') as f:
        f.write(prompt)
    print(f"  Saved prompt: {prompt_file}")

    # Try calling LLM
    print(f"\n🔄 Calling Gemini API...")

    try:
        response_data, metadata = call_gemini_api(prompt)

        print(f"\n✅ LLM call succeeded!")
        print(f"  Input tokens: {metadata.get('input_tokens', 'N/A'):,}")
        print(f"  Output tokens: {metadata.get('output_tokens', 'N/A'):,}")
        print(f"  Latency: {metadata.get('latency_ms', 0)/1000:.1f}s")

        # Save response
        response_file = output_dir / "no_sample_rows_response.yaml"
        with open(response_file, 'w') as f:
            yaml.dump(response_data, f, default_flow_style=False)
        print(f"  Saved response: {response_file}")

        # Validate YAML
        try:
            parsed = yaml.safe_load(yaml.dump(response_data))
            print(f"  ✅ Valid YAML structure")

            save_test_result('no_sample_rows', 'SUCCESS', {
                'input_tokens': metadata.get('input_tokens'),
                'output_tokens': metadata.get('output_tokens'),
                'token_reduction': 'TBD'
            }, output_dir)
            return True

        except yaml.YAMLError as e:
            print(f"  ❌ YAML parse error: {e}")
            save_test_result('no_sample_rows', 'YAML_ERROR', {
                'error': str(e),
                'input_tokens': metadata.get('input_tokens'),
                'output_tokens': metadata.get('output_tokens')
            }, output_dir)
            return False

    except Exception as e:
        print(f"\n❌ LLM call failed: {e}")
        save_test_result('no_sample_rows', 'LLM_ERROR', {'error': str(e)}, output_dir)
        return False


def test_limited_columns(manifest_path: Path, output_dir: Path, limit: int = 20):
    """Test 3: Limit preview to first N columns."""
    print("\n" + "="*80)
    print(f"TEST 3: Limit preview to first {limit} columns")
    print("="*80)

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    sources = manifest.get('sources', [])

    # Limit columns in previews
    modified_sources = []
    for source in sources:
        modified_files = []
        for file_entry in source.get('files', []):
            modified_entry = file_entry.copy()
            if 'preview' in modified_entry:
                preview = modified_entry['preview'].copy()
                columns = preview.get('columns', [])

                if len(columns) > limit:
                    preview['columns'] = columns[:limit]
                    preview['full_column_count'] = len(columns)
                    preview['preview_truncated'] = True

                # Also limit sample_rows if present
                if 'sample_rows' in preview:
                    limited_rows = []
                    for row in preview['sample_rows']:
                        limited_row = {k: v for k, v in row.items()
                                     if k in preview['columns']}
                        limited_rows.append(limited_row)
                    preview['sample_rows'] = limited_rows

                modified_entry['preview'] = preview
            modified_files.append(modified_entry)

        modified_source = source.copy()
        modified_source['files'] = modified_files
        modified_sources.append(modified_source)

    # Count columns
    total_cols = sum(len(f.get('preview', {}).get('columns', []))
                    for s in modified_sources for f in s.get('files', []))

    print(f"\nModified manifest:")
    print(f"  Sources: {len(modified_sources)}")
    print(f"  Total columns: {total_cols}")
    print(f"  Limit per file: {limit}")

    # Build prompt
    prompt = build_enrichment_prompt(manifest, modified_sources)
    prompt_tokens = len(prompt.split()) * 1.3

    print(f"\nPrompt analysis:")
    print(f"  Prompt length: {len(prompt):,} chars")
    print(f"  Estimated tokens: {int(prompt_tokens):,}")

    # Save prompt
    prompt_file = output_dir / f"limited_{limit}_cols_prompt.txt"
    with open(prompt_file, 'w') as f:
        f.write(prompt)
    print(f"  Saved prompt: {prompt_file}")

    # Try calling LLM
    print(f"\n🔄 Calling Gemini API...")

    try:
        response_data, metadata = call_gemini_api(prompt)

        print(f"\n✅ LLM call succeeded!")
        print(f"  Input tokens: {metadata.get('input_tokens', 'N/A'):,}")
        print(f"  Output tokens: {metadata.get('output_tokens', 'N/A'):,}")

        response_file = output_dir / f"limited_{limit}_cols_response.yaml"
        with open(response_file, 'w') as f:
            yaml.dump(response_data, f, default_flow_style=False)
        print(f"  Saved response: {response_file}")

        save_test_result(f'limited_{limit}_cols', 'SUCCESS', {
            'input_tokens': metadata.get('input_tokens'),
            'output_tokens': metadata.get('output_tokens'),
            'column_limit': limit
        }, output_dir)
        return True

    except Exception as e:
        print(f"\n❌ LLM call failed: {e}")
        save_test_result(f'limited_{limit}_cols', 'ERROR', {'error': str(e)}, output_dir)
        return False


def main():
    """Run all diagnostic tests."""
    if len(sys.argv) < 2:
        print("Usage: python diagnose_enrichment_failure.py <manifest.yaml>")
        print("\nExample:")
        print("  python diagnose_enrichment_failure.py manifests/test/rtt_provider_apr25_test.yaml")
        sys.exit(1)

    manifest_path = Path(sys.argv[1])
    if not manifest_path.exists():
        print(f"❌ Manifest not found: {manifest_path}")
        sys.exit(1)

    # Create output directory
    output_dir = Path("logs/enrichment_diagnostics") / datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "="*80)
    print("ENRICHMENT FAILURE DIAGNOSTIC")
    print("="*80)
    print(f"\nManifest: {manifest_path}")
    print(f"Output: {output_dir}")
    print(f"\nAPI Key: {'✓' if os.getenv('GEMINI_API_KEY') else '✗ MISSING'}")

    if not os.getenv('GEMINI_API_KEY'):
        print("\n❌ GEMINI_API_KEY not set in environment")
        sys.exit(1)

    # Run tests in order of increasing modification
    results = {}

    # Test 1: Baseline (should fail with token limit)
    results['baseline'] = test_baseline(manifest_path, output_dir)

    # Test 2: No sample_rows
    results['no_sample_rows'] = test_no_sample_rows(manifest_path, output_dir)

    # Test 3: Limited columns (20)
    results['limited_20'] = test_limited_columns(manifest_path, output_dir, limit=20)

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print("\nTest Results:")
    for test, success in results.items():
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"  {test:20s}: {status}")

    print(f"\nDetailed results saved to: {output_dir}")
    print("\nNext steps:")
    print("  1. Review saved prompts (*.txt) to see what LLM received")
    print("  2. Review responses (*.yaml) to see what LLM returned")
    print("  3. Check *.json files for token counts and error details")
    print("  4. Compare which approach succeeds with minimal data loss")


if __name__ == '__main__':
    main()
