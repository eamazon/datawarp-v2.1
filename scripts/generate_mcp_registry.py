#!/usr/bin/env python3
"""Generate MCP dataset registry from existing catalog.parquet and .md files.

This script bootstraps the multi-dataset MCP server configuration from your
existing DataWarp outputs. Run once to create initial config, then manually
enrich metadata as needed.

Usage:
    python scripts/generate_mcp_registry.py

Output:
    mcp_server/config/datasets.yaml     - Dataset registry
    mcp_server/metadata/{domain}.yaml   - Domain-specific metadata
"""

from pathlib import Path
import pandas as pd
import yaml
import re
import sys

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
MCP_SERVER = PROJECT_ROOT / "mcp_server"
MCP_CONFIG = MCP_SERVER / "config"
MCP_METADATA = MCP_SERVER / "metadata"


def extract_domain_from_code(code: str) -> str:
    """Infer domain from dataset code."""
    code_lower = code.lower()
    if code_lower.startswith('adhd') or 'adhd' in code_lower:
        return 'mental_health'
    elif code_lower.startswith('pcn') or 'workforce' in code_lower:
        return 'workforce'
    elif code_lower.startswith('gp_') or 'practice' in code_lower:
        return 'primary_care'
    elif 'waiting' in code_lower:
        return 'waiting_times'
    elif 'opensafely' in code_lower:
        return 'research'
    elif 'bulletin' in code_lower or 'table' in code_lower:
        return 'publications'
    elif 'regional' in code_lower or 'icb' in code_lower:
        return 'geography'
    else:
        return 'other'


def extract_tags_from_code(code: str) -> list:
    """Extract meaningful tags from dataset code."""
    # Split on underscores
    parts = code.lower().split('_')

    # Filter out common non-descriptive parts
    skip_words = {'summary', 'csv', 'parquet', 'data', 'tbl', 'raw', 'all', 'val'}
    tags = [p for p in parts if p not in skip_words and len(p) > 2]

    return tags[:5]  # Limit to 5 tags


def parse_md_metadata(md_path: Path) -> dict:
    """Parse column descriptions from markdown file."""
    if not md_path.exists():
        return {'columns': {}, 'purpose': ''}

    content = md_path.read_text()
    result = {'columns': {}, 'purpose': ''}

    # Extract purpose from ## Purpose section
    purpose_match = re.search(r'## Purpose\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
    if purpose_match:
        result['purpose'] = purpose_match.group(1).strip()[:500]  # Limit length

    # Parse column sections (#### `column_name`)
    col_pattern = r'####\s+`(\w+)`\s*\n(.*?)(?=####|\n##|\Z)'
    for match in re.finditer(col_pattern, content, re.DOTALL):
        col_name = match.group(1)
        col_content = match.group(2)

        col_info = {}

        # Extract description
        desc_match = re.search(r'\*\*Description:\*\*\s*(.+?)(?:\n|$)', col_content)
        if desc_match:
            col_info['description'] = desc_match.group(1).strip()

        # Extract type
        type_match = re.search(r'\*\*Type:\*\*\s*(.+?)(?:\n|$)', col_content)
        if type_match:
            col_info['data_type'] = type_match.group(1).strip()

        # Extract search terms
        terms_match = re.search(r'\*\*Search Terms:\*\*\s*(.+?)(?:\n|$)', col_content)
        if terms_match:
            terms = [t.strip() for t in terms_match.group(1).split(',')]
            col_info['query_keywords'] = terms

        # Infer role from column name
        if col_name.startswith('_'):
            col_info['role'] = 'system'
        elif any(x in col_name.lower() for x in ['count', 'total', 'rate', 'value', 'sum', 'avg']):
            col_info['role'] = 'measure'
        else:
            col_info['role'] = 'dimension'

        if col_info:
            result['columns'][col_name] = col_info

    return result


def main():
    """Generate MCP registry from existing catalog."""

    # Check catalog exists
    catalog_path = OUTPUT_DIR / "catalog.parquet"
    if not catalog_path.exists():
        print(f"Error: Catalog not found at {catalog_path}")
        print("Run: python scripts/rebuild_catalog.py first")
        sys.exit(1)

    # Load catalog
    print(f"Loading catalog from {catalog_path}...")
    catalog = pd.read_parquet(catalog_path)
    print(f"Found {len(catalog)} datasets in catalog")

    # Create directories
    MCP_CONFIG.mkdir(parents=True, exist_ok=True)
    MCP_METADATA.mkdir(parents=True, exist_ok=True)

    # Build datasets registry
    datasets = {}
    metadata_by_domain = {}
    domain_counts = {}

    for _, row in catalog.iterrows():
        code = row['source_code']
        domain = extract_domain_from_code(code)
        tags = extract_tags_from_code(code)

        # Track domain counts
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

        # Build file path (relative to project root)
        file_path = row.get('file_path', f"output/{code}.parquet")
        if file_path.startswith('output/'):
            file_path = file_path  # Keep as-is
        else:
            file_path = f"output/{file_path}"

        # Add to registry
        datasets[code] = {
            'backend': 'duckdb_parquet',
            'path': file_path,
            'metadata_file': f"metadata/{domain}.yaml",
            'domain': domain,
            'tags': tags
        }

        # Collect metadata by domain
        if domain not in metadata_by_domain:
            metadata_by_domain[domain] = {
                'domain': domain,
                'description': f"NHS {domain.replace('_', ' ').title()} datasets",
                'datasets': {}
            }

        # Parse .md file for column metadata
        md_path = OUTPUT_DIR / f"{code}.md"
        parsed = parse_md_metadata(md_path)

        metadata_by_domain[domain]['datasets'][code] = {
            'purpose': parsed.get('purpose') or row.get('description', f"DataWarp source: {code}"),
            'row_count': int(row['row_count']) if pd.notna(row.get('row_count')) else 0,
            'column_count': int(row['column_count']) if pd.notna(row.get('column_count')) else 0,
            'example_questions': [],  # To be filled manually
            'columns': parsed.get('columns', {})
        }

    # Build full registry
    registry = {
        'version': '1.0',
        'generated_from': 'catalog.parquet',
        'default_backend': 'duckdb_parquet',
        'datasets': datasets,
        'backends': {
            'duckdb_parquet': {
                'type': 'duckdb',
                'description': 'Query Parquet files via DuckDB (default)',
                'base_path': 'output/'
            },
            'postgres': {
                'type': 'postgres',
                'description': 'Query PostgreSQL staging tables directly',
                'schema': 'staging',
                'note': 'Uses POSTGRES_* env vars from .env'
            }
        }
    }

    # Write datasets.yaml
    config_path = MCP_CONFIG / "datasets.yaml"
    with open(config_path, 'w') as f:
        yaml.dump(registry, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    print(f"Written: {config_path}")

    # Write domain-specific metadata files
    for domain, metadata in metadata_by_domain.items():
        metadata_path = MCP_METADATA / f"{domain}.yaml"
        with open(metadata_path, 'w') as f:
            yaml.dump(metadata, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        print(f"Written: {metadata_path}")

    # Summary
    print("\n" + "=" * 60)
    print("MCP Registry Generation Complete")
    print("=" * 60)
    print(f"\nDatasets: {len(datasets)}")
    print(f"Domains:  {len(metadata_by_domain)}")
    print("\nDomain breakdown:")
    for domain, count in sorted(domain_counts.items(), key=lambda x: -x[1]):
        print(f"  {domain}: {count} datasets")

    print(f"\nConfig file: {config_path}")
    print(f"Metadata files: {MCP_METADATA}/*.yaml")

    print("\nNext steps:")
    print("1. Review generated files")
    print("2. Manually add example_questions to key datasets")
    print("3. Enrich column metadata with value_domains where useful")
    print("4. Run: python mcp_server/stdio_server.py")


if __name__ == "__main__":
    main()
