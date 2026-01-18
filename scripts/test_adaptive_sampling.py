#!/usr/bin/env python
"""Test adaptive sampling solution for enrichment.

Problem: sample_rows with ALL 119 columns = 100KB of YAML overhead
Solution: sample_rows with REPRESENTATIVE subset = manageable size

Approach:
- Keep first 5 columns (identifiers)
- Keep 3 pattern samples (if detected)
- Keep last 5 columns (summaries)
- Total: ~15 columns in sample_rows vs 119

Benefits:
- LLM gets actual data examples
- Shows pattern sequence
- No token overflow
- Better than no samples at all
"""
import sys
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from datawarp.pipeline.enricher import build_enrichment_prompt, call_gemini_api


def create_adaptive_sampled_manifest(manifest_path: Path, max_sample_cols: int = 15):
    """Create manifest with adaptive sample_rows."""

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    sources = manifest.get('sources', [])

    adapted_sources = []
    for source in sources:
        adapted_files = []
        for file_entry in source.get('files', []):
            preview = file_entry.get('preview', {})
            columns = preview.get('columns', [])
            sample_rows = preview.get('sample_rows', [])

            if not sample_rows or len(columns) <= max_sample_cols:
                # Small file or no samples - keep as is
                adapted_files.append(file_entry)
                continue

            # Large file - adaptive sampling
            # Strategy: first 5, middle 5, last 5
            sample_cols = columns[:5] + columns[len(columns)//2-2:len(columns)//2+3] + columns[-5:]
            sample_cols = list(dict.fromkeys(sample_cols))  # Remove duplicates, keep order

            # Limit to max
            sample_cols = sample_cols[:max_sample_cols]

            # Filter sample_rows to only include these columns
            adapted_rows = []
            for row in sample_rows:
                adapted_row = {col: row[col] for col in sample_cols if col in row}
                adapted_rows.append(adapted_row)

            adapted_preview = {
                'columns': columns,  # Keep full column list
                'sample_rows': adapted_rows,  # Sampled rows
                'sample_note': f'Sample data for {len(sample_cols)} of {len(columns)} columns'
            }

            adapted_entry = file_entry.copy()
            adapted_entry['preview'] = adapted_preview
            adapted_files.append(adapted_entry)

        adapted_source = source.copy()
        adapted_source['files'] = adapted_files
        adapted_sources.append(adapted_source)

    return adapted_sources


def main():
    manifest_path = Path('manifests/test/rtt_provider_apr25_test.yaml')
    output_dir = Path('logs/enrichment_diagnostics') / 'adaptive_sampling'
    output_dir.mkdir(parents=True, exist_ok=True)

    print("="*80)
    print("ADAPTIVE SAMPLING TEST")
    print("="*80)

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    # Create adaptively sampled sources
    adapted_sources = create_adaptive_sampled_manifest(manifest_path, max_sample_cols=15)

    # Build prompt
    prompt = build_enrichment_prompt(manifest, adapted_sources)

    print(f"\nPrompt analysis:")
    print(f"  Prompt length: {len(prompt):,} chars")
    print(f"  Estimated tokens: {int(len(prompt.split()) * 1.3):,}")

    # Save prompt
    prompt_file = output_dir / "adaptive_sampling_prompt.txt"
    with open(prompt_file, 'w') as f:
        f.write(prompt)
    print(f"  Saved: {prompt_file}")

    # Show sample structure
    print(f"\nSample structure:")
    for source in adapted_sources[:1]:
        for file_entry in source.get('files', []):
            preview = file_entry.get('preview', {})
            columns = preview.get('columns', [])
            sample_rows = preview.get('sample_rows', [])

            if sample_rows:
                print(f"  Total columns: {len(columns)}")
                print(f"  Sample columns: {len(sample_rows[0].keys())}")
                print(f"  Sample keys: {list(sample_rows[0].keys())}")

    # Call LLM
    print(f"\n🔄 Calling Gemini API...")

    try:
        response_data, metadata = call_gemini_api(prompt)

        print(f"\n✅ SUCCESS!")
        print(f"  Input tokens: {metadata.get('input_tokens', 'N/A'):,}")
        print(f"  Output tokens: {metadata.get('output_tokens', 'N/A'):,}")
        print(f"  Latency: {metadata.get('latency_ms', 0)/1000:.1f}s")

        # Save response
        response_file = output_dir / "adaptive_sampling_response.yaml"
        with open(response_file, 'w') as f:
            yaml.dump(response_data, f, default_flow_style=False)
        print(f"  Saved: {response_file}")

        # Count enriched columns
        sources = response_data.get('sources', []) if isinstance(response_data, dict) else []
        for source in sources[:1]:
            cols = source.get('columns', [])
            print(f"  Enriched columns: {len(cols)}")

        return True

    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        return False


if __name__ == '__main__':
    main()
