#!/usr/bin/env python3
"""
Apply LLM-enriched codes and metadata back to YAML manifest.

This bridges the gap between enrichment and loading:
  url_to_manifest → enrich → apply_enrichment → load
                               ↑ YOU ARE HERE

Usage:
    python scripts/apply_enrichment.py \
        manifests/adhd_enriched.yaml \
        manifests/adhd_enriched_llm_response.json \
        manifests/adhd_canonical.yaml
"""
import sys
import yaml
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table

console = Console()

def apply_enrichment(yaml_path: str, json_path: str, output_path: str):
    """Apply enriched codes and metadata from JSON to YAML."""

    # Load both files
    console.print(f"[cyan]Loading YAML:[/cyan] {yaml_path}")
    yaml_data = yaml.safe_load(open(yaml_path))

    console.print(f"[cyan]Loading JSON:[/cyan] {json_path}")
    json_data = json.load(open(json_path))

    # Map enriched sources by code (LLM response doesn't include files array)
    enriched_map = {}
    for source in json_data.get('manifest', []):
        code = source.get('code')
        if code:
            enriched_map[code] = source

    console.print(f"\n[green]Found {len(enriched_map)} enriched sources[/green]")

    # Track updates
    updates = []
    matched_count = 0
    unmatched_sources = []

    # Apply enriched data to YAML sources
    for source in yaml_data.get('sources', []):
        old_code = source.get('code', 'N/A')

        # Try to match by code (exact match first)
        enriched = enriched_map.get(old_code)

        if enriched:
            matched_count += 1
            new_code = enriched['code']

            # Update source with enriched data
            source['code'] = new_code
            source['table'] = f"tbl_{new_code}"
            source['name'] = enriched.get('name', source.get('name', ''))
            source['description'] = enriched.get('description', '')
            source['metadata'] = enriched.get('metadata', {})
            source['columns'] = enriched.get('columns', [])

            # Preserve original for audit
            source['_original_code'] = old_code

            # Get identifying info for display
            display_id = source.get('name', old_code)[:50]
            if 'files' in source and len(source['files']) > 0:
                display_id = source['files'][0]['url'][:50]

            updates.append({
                'identifier': display_id + '...' if len(display_id) >= 50 else display_id,
                'old_code': old_code,
                'new_code': new_code,
                'changed': old_code != new_code
            })
        else:
            unmatched_sources.append(old_code)

    # Display changes
    console.print(f"\n[cyan]Matched {matched_count} sources[/cyan]")

    if unmatched_sources:
        console.print(f"[yellow]⚠ {len(unmatched_sources)} sources not found in enriched JSON:[/yellow]")
        for code in unmatched_sources[:5]:
            console.print(f"  - {code}")
        if len(unmatched_sources) > 5:
            console.print(f"  ... and {len(unmatched_sources) - 5} more")

    if updates:
        table = Table(title="Code Updates")
        table.add_column("Source", style="dim")
        table.add_column("Original Code", style="yellow")
        table.add_column("Enriched Code", style="green")
        table.add_column("Changed", justify="center")

        for update in updates:
            changed_icon = "✓" if update['changed'] else "="
            changed_style = "bold green" if update['changed'] else "dim"

            table.add_row(
                update['identifier'],
                update['old_code'],
                update['new_code'],
                f"[{changed_style}]{changed_icon}[/{changed_style}]"
            )

        console.print(table)

    # Save updated YAML
    with open(output_path, 'w') as f:
        yaml.dump(yaml_data, f, sort_keys=False, default_flow_style=False)

    console.print(f"\n[bold green]✅ Enriched manifest saved:[/bold green] {output_path}")

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)

    apply_enrichment(sys.argv[1], sys.argv[2], sys.argv[3])
