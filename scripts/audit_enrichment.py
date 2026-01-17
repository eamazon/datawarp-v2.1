#!/usr/bin/env python3
"""
Audit enrichment quality in column metadata.

Checks:
- Do all measure columns have descriptions?
- Are dimension columns properly tagged?
- Are query_keywords populated?
- Flag issues for manual review

Usage:
    python scripts/audit_enrichment.py
    python scripts/audit_enrichment.py --source adhd_prevalence
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
import argparse

sys.path.insert(0, str(Path(__file__).parent.parent))


def audit_source(source_code: str, conn) -> dict:
    """Audit enrichment quality for a single source."""
    cur = conn.cursor()

    # Get all column metadata
    cur.execute("""
        SELECT
            column_name,
            description,
            is_measure,
            is_dimension,
            query_keywords,
            data_type
        FROM datawarp.tbl_column_metadata
        WHERE canonical_source_code = %s
    """, (source_code,))

    rows = cur.fetchall()
    if not rows:
        return {
            "source": source_code,
            "status": "NO_METADATA",
            "issues": ["No column metadata found"]
        }

    issues = []
    warnings = []
    stats = {
        "total_columns": len(rows),
        "measures": 0,
        "dimensions": 0,
        "neither": 0,
        "missing_descriptions": 0,
        "missing_keywords": 0
    }

    for row in rows:
        col_name, description, is_measure, is_dimension, keywords, data_type = row

        # Count by type
        if is_measure:
            stats["measures"] += 1
        if is_dimension:
            stats["dimensions"] += 1
        if not is_measure and not is_dimension:
            stats["neither"] += 1

        # Check 1: Measures should have descriptions
        if is_measure and not description:
            issues.append(f"Measure '{col_name}' missing description")
            stats["missing_descriptions"] += 1

        # Check 2: Dimensions should have descriptions
        if is_dimension and not description:
            warnings.append(f"Dimension '{col_name}' missing description")
            stats["missing_descriptions"] += 1

        # Check 3: All columns should have query keywords
        if not keywords or len(keywords) == 0:
            warnings.append(f"Column '{col_name}' missing query keywords")
            stats["missing_keywords"] += 1

        # Check 4: Numeric columns that aren't marked as measure (potential issue)
        if data_type in ['INTEGER', 'BIGINT', 'NUMERIC', 'DECIMAL'] and not is_measure:
            # Might be okay (could be IDs/codes), but worth flagging
            if not any(word in col_name.lower() for word in ['_id', '_code', 'identifier']):
                warnings.append(f"Numeric column '{col_name}' not marked as measure (might be okay)")

    # Overall assessment
    if len(issues) > 0:
        status = "ISSUES_FOUND"
    elif len(warnings) > 3:
        status = "WARNINGS"
    else:
        status = "OK"

    return {
        "source": source_code,
        "status": status,
        "stats": stats,
        "issues": issues,
        "warnings": warnings
    }


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description='Audit enrichment quality')
    parser.add_argument('--source', help='Audit specific source code')
    parser.add_argument('--all', action='store_true', help='Audit all sources')

    args = parser.parse_args()

    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST'),
        port=os.getenv('POSTGRES_PORT'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
        database=os.getenv('POSTGRES_DB')
    )

    cur = conn.cursor()

    # Determine which sources to audit
    if args.source:
        sources = [args.source]
    elif args.all:
        cur.execute("SELECT DISTINCT canonical_source_code FROM datawarp.tbl_column_metadata ORDER BY 1")
        sources = [row[0] for row in cur.fetchall()]
    else:
        # Default: audit sources with data loaded
        cur.execute("""
            SELECT DISTINCT s.code
            FROM datawarp.tbl_data_sources s
            INNER JOIN datawarp.tbl_column_metadata cm ON cm.canonical_source_code = s.code
            ORDER BY s.code
        """)
        sources = [row[0] for row in cur.fetchall()]

    print(f"Auditing {len(sources)} sources...")
    print("=" * 80)

    summary = {
        "OK": 0,
        "WARNINGS": 0,
        "ISSUES_FOUND": 0,
        "NO_METADATA": 0
    }

    for source in sources:
        result = audit_source(source, conn)
        summary[result['status']] += 1

        print(f"\n{result['source']}: {result['status']}")

        if result.get('stats'):
            stats = result['stats']
            print(f"  Columns: {stats['total_columns']} "
                  f"({stats['measures']} measures, {stats['dimensions']} dims, "
                  f"{stats['neither']} neither)")

        if result['issues']:
            print(f"  ⚠️  ISSUES ({len(result['issues'])}):")
            for issue in result['issues'][:5]:  # Show first 5
                print(f"     - {issue}")
            if len(result['issues']) > 5:
                print(f"     ... and {len(result['issues']) - 5} more")

        if result['warnings'] and len(result['warnings']) <= 3:
            print(f"  ⚡ Warnings ({len(result['warnings'])}):")
            for warning in result['warnings']:
                print(f"     - {warning}")
        elif result['warnings']:
            print(f"  ⚡ {len(result['warnings'])} warnings (run with --source to see details)")

    print("\n" + "=" * 80)
    print("SUMMARY:")
    print(f"  ✅ OK: {summary['OK']}")
    print(f"  ⚡ Warnings: {summary['WARNINGS']}")
    print(f"  ⚠️  Issues: {summary['ISSUES_FOUND']}")
    print(f"  ❌ No metadata: {summary['NO_METADATA']}")

    conn.close()

    # Exit code based on issues
    if summary['ISSUES_FOUND'] > 0:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
