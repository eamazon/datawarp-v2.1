#!/usr/bin/env python3
"""Compare two manifests to detect schema changes (fiscal year transitions).

Usage:
    python scripts/compare_manifests.py manifests/mar25.yaml manifests/apr25.yaml
    python scripts/compare_manifests.py manifests/mar25.yaml manifests/apr25.yaml --fiscal-boundary
"""
import sys
import yaml
import argparse
from pathlib import Path
from typing import Dict, Set, List, Tuple
from collections import Counter


def load_manifest(path: Path) -> Dict:
    """Load manifest YAML file."""
    with open(path) as f:
        return yaml.safe_load(f)


def get_source_codes(manifest: Dict) -> Set[str]:
    """Extract set of source codes from manifest."""
    return {src['code'] for src in manifest.get('sources', [])}


def get_source_details(manifest: Dict) -> Dict[str, Dict]:
    """Extract source details (code → {name, table, files})."""
    details = {}
    for src in manifest.get('sources', []):
        code = src['code']
        details[code] = {
            'name': src.get('name', ''),
            'table': src.get('table', ''),
            'file_count': len(src.get('files', [])),
            'enabled': src.get('enabled', True)
        }
    return details


def compare_manifests(manifest1_path: Path, manifest2_path: Path, fiscal_boundary: bool = False) -> None:
    """Compare two manifests and report differences."""

    m1 = load_manifest(manifest1_path)
    m2 = load_manifest(manifest2_path)

    codes1 = get_source_codes(m1)
    codes2 = get_source_codes(m2)
    details1 = get_source_details(m1)
    details2 = get_source_details(m2)

    # Calculate differences
    only_in_1 = codes1 - codes2
    only_in_2 = codes2 - codes1
    common = codes1 & codes2

    print(f"\n{'='*80}")
    print(f"Comparing:")
    print(f"  Reference: {manifest1_path.name} ({len(codes1)} sources)")
    print(f"  Current:   {manifest2_path.name} ({len(codes2)} sources)")
    print(f"{'='*80}")

    # Summary stats
    print(f"\n📊 Summary:")
    print(f"  Common sources: {len(common)}")
    print(f"  Only in {manifest1_path.stem}: {len(only_in_1)}")
    print(f"  Only in {manifest2_path.stem}: {len(only_in_2)}")
    print(f"  Schema consistency: {len(common)/len(codes1)*100:.1f}%")

    # Fiscal boundary expectations
    if fiscal_boundary:
        print(f"\n🗓️  Fiscal Boundary Analysis:")
        if len(only_in_2) > 0:
            print(f"  ✅ New sources added: {len(only_in_2)} (expected at FY transition)")
        if len(only_in_1) > 0:
            print(f"  ⚠️  Sources removed: {len(only_in_1)} (check if deprecated)")
        if len(common) / len(codes1) > 0.95:
            print(f"  ✅ High consistency ({len(common)/len(codes1)*100:.1f}%) - stable transition")
        elif len(common) / len(codes1) > 0.80:
            print(f"  🟡 Moderate consistency ({len(common)/len(codes1)*100:.1f}%) - some changes")
        else:
            print(f"  🔴 Low consistency ({len(common)/len(codes1)*100:.1f}%) - major restructuring")

    # Details of differences
    if only_in_1:
        print(f"\n❌ Sources removed in {manifest2_path.stem}:")
        for code in sorted(only_in_1):
            info = details1[code]
            print(f"   - {code}")
            print(f"       Name: {info['name']}")
            print(f"       Table: {info['table']}")

    if only_in_2:
        print(f"\n➕ Sources added in {manifest2_path.stem}:")
        for code in sorted(only_in_2):
            info = details2[code]
            print(f"   - {code}")
            print(f"       Name: {info['name']}")
            print(f"       Table: {info['table']}")

    # Check for file count changes in common sources
    file_count_changes = []
    for code in common:
        count1 = details1[code]['file_count']
        count2 = details2[code]['file_count']
        if count1 != count2:
            file_count_changes.append((code, count1, count2))

    if file_count_changes:
        print(f"\n📁 File count changes in common sources:")
        for code, count1, count2 in file_count_changes:
            change = count2 - count1
            symbol = "+" if change > 0 else ""
            print(f"   - {code}: {count1} → {count2} ({symbol}{change})")

    # Overall assessment
    print(f"\n{'='*80}")
    print(f"Assessment:")
    if len(only_in_1) == 0 and len(only_in_2) == 0:
        print(f"  ✅ STABLE: No schema changes detected")
    elif len(only_in_2) > len(only_in_1):
        print(f"  🟢 GROWTH: Net {len(only_in_2) - len(only_in_1)} sources added")
    elif len(only_in_1) > len(only_in_2):
        print(f"  🔴 REDUCTION: Net {len(only_in_1) - len(only_in_2)} sources removed")
    else:
        print(f"  🟡 RESTRUCTURE: {len(only_in_1)} removed, {len(only_in_2)} added")
    print(f"{'='*80}")


def main():
    parser = argparse.ArgumentParser(description='Compare two DataWarp manifests')
    parser.add_argument('manifest1', help='Reference manifest (earlier period)')
    parser.add_argument('manifest2', help='Current manifest (later period)')
    parser.add_argument('--fiscal-boundary', action='store_true',
                       help='Interpret as fiscal year boundary (March→April)')

    args = parser.parse_args()

    manifest1_path = Path(args.manifest1)
    manifest2_path = Path(args.manifest2)

    if not manifest1_path.exists():
        print(f"❌ Reference manifest not found: {args.manifest1}")
        sys.exit(1)

    if not manifest2_path.exists():
        print(f"❌ Current manifest not found: {args.manifest2}")
        sys.exit(1)

    compare_manifests(manifest1_path, manifest2_path, args.fiscal_boundary)


if __name__ == '__main__':
    main()
