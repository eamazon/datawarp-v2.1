#!/usr/bin/env python3
"""Validate DataWarp manifest structure and contents.

Usage:
    python scripts/validate_manifest.py manifests/production/adhd/adhd_aug25_enriched.yaml
    python scripts/validate_manifest.py manifests/production/adhd/*.yaml --strict
    python scripts/validate_manifest.py manifests/test/*.yaml --check-urls
"""
import sys
import yaml
import argparse
import requests
from pathlib import Path
from collections import Counter
from typing import List, Tuple


def check_url_reachability(url: str, timeout: int = 10) -> Tuple[bool, str]:
    """Check if URL is reachable with HEAD request.

    Returns:
        (is_reachable, message)
    """
    try:
        # Try HEAD first (faster, doesn't download content)
        response = requests.head(url, timeout=timeout, allow_redirects=True)

        if response.status_code == 200:
            return True, "OK"
        elif response.status_code == 405:  # Method Not Allowed
            # Some servers don't support HEAD, try GET with stream
            response = requests.get(url, timeout=timeout, stream=True, allow_redirects=True)
            if response.status_code == 200:
                return True, "OK (via GET)"
            else:
                return False, f"HTTP {response.status_code}"
        else:
            return False, f"HTTP {response.status_code}"

    except requests.exceptions.Timeout:
        return False, f"Timeout after {timeout}s"
    except requests.exceptions.ConnectionError as e:
        return False, f"Connection error: {str(e)[:100]}"
    except Exception as e:
        return False, f"Error: {str(e)[:100]}"


def validate_manifest(manifest_path: Path, strict: bool = False, check_urls: bool = False):
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
    if check_urls:
        print("   Checking URL reachability...")
        for src in sources:
            src_id = src.get('code', 'unknown')
            files = src.get('files', [])

            for i, file in enumerate(files):
                url = file.get('url')
                if not url:
                    continue

                is_reachable, message = check_url_reachability(url)

                if not is_reachable:
                    errors.append(f"Source '{src_id}', file {i}: URL not reachable - {message}")
                    print(f"      ❌ {url[:80]}... - {message}")
                else:
                    print(f"      ✅ {url[:80]}... - {message}")

    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description='Validate DataWarp manifest')
    parser.add_argument('manifest', nargs='+', help='Manifest file(s) to validate')
    parser.add_argument('--strict', action='store_true', help='Enable strict validation (warnings become errors)')
    parser.add_argument('--check-urls', action='store_true', help='Check if file URLs are reachable (slow)')

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

        errors, warnings = validate_manifest(path, args.strict, args.check_urls)

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
