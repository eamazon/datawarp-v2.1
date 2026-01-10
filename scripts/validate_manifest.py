#!/usr/bin/env python3
"""Validate DataWarp manifest structure and contents.

Usage:
    python scripts/validate_manifest.py manifests/production/adhd/adhd_aug25_enriched.yaml
    python scripts/validate_manifest.py manifests/production/adhd/*.yaml --strict
"""
import sys
import yaml
import argparse
from pathlib import Path
from collections import Counter


def validate_manifest(manifest_path: Path, strict: bool = False):
    """Validate manifest structure and contents."""

    errors = []
    warnings = []

    # 1. YAML is valid
    try:
        with open(manifest_path) as f:
            data = yaml.safe_load(f)
    except Exception as e:
        errors.append(f"YAML parse error: {e}")
        return errors, warnings

    # 2. Required top-level keys
    if 'manifest' not in data:
        errors.append("Missing 'manifest' key")

    if 'sources' not in data:
        errors.append("Missing 'sources' key")
        return errors, warnings

    sources = data['sources']

    # 3. Each source has required fields
    for i, src in enumerate(sources):
        src_id = src.get('code', f'source_{i}')

        required_fields = ['code', 'name', 'table', 'enabled', 'files']
        for field in required_fields:
            if field not in src:
                errors.append(f"Source '{src_id}': Missing required field '{field}'")

        # Check files array
        if 'files' in src:
            if not isinstance(src['files'], list) or len(src['files']) == 0:
                errors.append(f"Source '{src_id}': 'files' must be non-empty array")

            for j, file in enumerate(src['files']):
                if 'url' not in file:
                    errors.append(f"Source '{src_id}', file {j}: Missing 'url'")

    # 4. No duplicate source codes
    codes = [s.get('code') for s in sources if 'code' in s]
    code_counts = Counter(codes)
    duplicates = [code for code, count in code_counts.items() if count > 1]
    if duplicates:
        errors.append(f"Duplicate source codes: {duplicates}")

    # 5. Warn if generic codes (strict mode)
    if strict:
        generic_patterns = ['table_', 'summary_', 'breakdown_', 'sheet_']
        for src in sources:
            code = src.get('code', '')
            if any(pattern in code.lower() for pattern in generic_patterns):
                warnings.append(f"Source '{code}': Generic code pattern (consider enrichment)")

    # 6. Warn if no column metadata (enriched manifests should have this)
    if 'enriched' in manifest_path.name or 'canonical' in manifest_path.name:
        sources_without_columns = [
            s.get('code') for s in sources
            if s.get('enabled', True) and 'columns' not in s
        ]
        if sources_without_columns:
            warnings.append(f"{len(sources_without_columns)} enabled sources missing 'columns' metadata")

    # 7. Check file URLs are reachable (optional, slow)
    # Skip for now, can add --check-urls flag later

    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description='Validate DataWarp manifest')
    parser.add_argument('manifest', nargs='+', help='Manifest file(s) to validate')
    parser.add_argument('--strict', action='store_true', help='Enable strict validation (warnings become errors)')

    args = parser.parse_args()

    total_errors = 0
    total_warnings = 0

    for manifest_path in args.manifest:
        path = Path(manifest_path)

        if not path.exists():
            print(f"❌ {manifest_path}: File not found")
            total_errors += 1
            continue

        print(f"\n{'='*80}")
        print(f"Validating: {manifest_path}")
        print(f"{'='*80}")

        errors, warnings = validate_manifest(path, args.strict)

        if errors:
            print(f"\n❌ ERRORS ({len(errors)}):")
            for err in errors:
                print(f"   - {err}")
            total_errors += len(errors)

        if warnings:
            print(f"\n⚠️  WARNINGS ({len(warnings)}):")
            for warn in warnings:
                print(f"   - {warn}")
            total_warnings += len(warnings)

        if not errors and not warnings:
            print("\n✅ VALID: No errors or warnings")

    print(f"\n{'='*80}")
    print(f"SUMMARY:")
    print(f"  Files validated: {len(args.manifest)}")
    print(f"  Total errors: {total_errors}")
    print(f"  Total warnings: {total_warnings}")
    print(f"{'='*80}")

    # Exit code: 0 if no errors, 1 if errors found
    sys.exit(1 if total_errors > 0 else 0)


if __name__ == '__main__':
    main()
