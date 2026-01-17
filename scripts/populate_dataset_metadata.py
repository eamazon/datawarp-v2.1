#!/usr/bin/env python3
"""
Populate dataset-level metadata from column-level metadata.

Reads tbl_column_metadata and aggregates into dataset-level metadata JSONB
for intelligent agent querying.

Usage:
    python scripts/populate_dataset_metadata.py --all
    python scripts/populate_dataset_metadata.py --source adhd_summary_discharged_referrals_waiting_time
    python scripts/populate_dataset_metadata.py --domain mental_health
"""

import os
import sys
import json
import argparse
from typing import Dict, List, Optional, Set
from datetime import datetime
from dotenv import load_dotenv
import psycopg2

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def infer_organizational_lenses(columns: List[Dict]) -> Dict[str, bool]:
    """
    Infer which organizational lenses are supported based on column patterns.

    GENERIC pattern-based detection - NOT hard-coded to healthcare.
    Works for any domain: ICB commissioning, retail, finance, etc.

    Patterns:
    - {lens}_code or {lens}_name → that lens is supported
    - geography_level with values containing lens names → flexible lens
    """
    column_names = [c['column_name'].lower() for c in columns]

    lenses = {
        'provider': False,
        'icb': False,
        'sub_icb': False,
        'gp_practice': False,
        'region': False,
        'national': False
    }

    # Check for explicit lens columns
    for lens in lenses.keys():
        # Look for {lens}_code, {lens}_name, {lens}_id patterns
        normalized_lens = lens.replace('_', '')
        if any(normalized_lens in col or lens in col for col in column_names):
            lenses[lens] = True

    # Check for flexible geography_level column
    for col in columns:
        if col['column_name'].lower() in ['geography_level', 'organization_level', 'level']:
            # Assume all lenses if flexible level column exists
            return {k: True for k in lenses.keys()}

    return lenses


def infer_unit(description: str, column_name: str, data_type: str) -> str:
    """Infer measurement unit from description and column metadata."""
    desc_lower = description.lower() if description else ''
    col_lower = column_name.lower()

    # Percentage patterns
    if any(word in desc_lower for word in ['percentage', 'percent', 'rate', 'proportion']):
        return 'percentage'

    # Count patterns
    if any(word in desc_lower or word in col_lower for word in ['count', 'number of', 'total']):
        return 'count'

    # Time patterns
    if any(word in col_lower for word in ['weeks', 'days', 'months', 'years', 'time']):
        if 'week' in col_lower:
            return 'weeks'
        elif 'day' in col_lower:
            return 'days'
        elif 'month' in col_lower:
            return 'months'
        elif 'year' in col_lower:
            return 'years'
        return 'time_period'

    # Currency patterns
    if any(word in desc_lower for word in ['£', 'gbp', 'pounds', 'cost', 'spend']):
        return 'GBP'

    # Default based on data type
    if data_type in ['INTEGER', 'BIGINT']:
        return 'count'
    elif data_type in ['NUMERIC', 'DECIMAL', 'FLOAT', 'DOUBLE PRECISION']:
        return 'numeric'

    return 'unknown'


def infer_aggregation(data_type: str, unit: str, column_name: str) -> str:
    """Infer default aggregation method for a measure."""
    col_lower = column_name.lower()

    # Rates and percentages need weighted averages (not simple average)
    if unit in ['percentage', 'rate']:
        return 'weighted_average'

    # Counts should be summed
    if unit == 'count' or 'count' in col_lower:
        return 'sum'

    # Time measurements (median is more robust than mean for wait times)
    if unit in ['weeks', 'days', 'months', 'years']:
        if 'median' in col_lower:
            return 'median'
        return 'average'

    # Default for numeric
    return 'average'


def infer_has_target(column_name: str, description: str) -> bool:
    """Infer if this metric has a performance target."""
    target_keywords = [
        'target', 'standard', 'threshold', 'compliance',
        'constitutional', 'waiting time standard'
    ]

    text = (column_name + ' ' + (description or '')).lower()
    return any(keyword in text for keyword in target_keywords)


def infer_metric_type(column_name: str, description: str, has_target: bool) -> str:
    """
    Classify metric as 'performance' (has target) or 'intelligence' (trend/correlation).

    Performance metrics: Have specific targets/standards to meet
    Intelligence metrics: Used for understanding trends, not pass/fail
    """
    if has_target:
        return 'performance'

    intelligence_keywords = [
        'prevalence', 'trend', 'change', 'growth', 'variation',
        'distribution', 'demographic', 'breakdown', 'analysis'
    ]

    text = (column_name + ' ' + (description or '')).lower()
    if any(keyword in text for keyword in intelligence_keywords):
        return 'intelligence'

    # Default to intelligence if unclear
    return 'intelligence'


def infer_granularity(dimensions: List[Dict]) -> str:
    """Infer dataset granularity from dimensions."""
    has_provider = any(d['column'].lower().startswith('provider') for d in dimensions)
    has_icb = any(d['column'].lower().startswith('icb') for d in dimensions)
    has_time = any(d['column'].lower() in ['date', 'period', 'time_period', 'month', 'quarter'] for d in dimensions)

    level = []
    if has_provider:
        level.append('provider')
    elif has_icb:
        level.append('icb')

    if has_time:
        time_col = next((d for d in dimensions if 'period' in d['column'].lower() or 'date' in d['column'].lower()), None)
        if time_col:
            col_name = time_col['column'].lower()
            if 'month' in col_name:
                level.append('monthly')
            elif 'quarter' in col_name or 'q1' in col_name or 'q2' in col_name:
                level.append('quarterly')
            elif 'year' in col_name:
                level.append('yearly')
            else:
                level.append('periodic')

    return '_'.join(level) if level else 'unknown'


def generate_typical_queries(kpis: List[Dict], dimensions: List[Dict], source_code: str) -> List[str]:
    """Generate typical query patterns for this dataset."""
    queries = []

    # Get main metric name
    main_kpi = kpis[0] if kpis else None
    if not main_kpi:
        return []

    metric_label = main_kpi['label']

    # Time trend query
    if any(d['column'].lower() in ['date', 'period', 'time_period', 'month', 'quarter'] for d in dimensions):
        queries.append(f"{metric_label} trend over time")

    # Geographic breakdowns
    geo_dims = [d for d in dimensions if any(g in d['column'].lower() for g in ['geography', 'icb', 'provider', 'region'])]
    if geo_dims:
        geo_name = geo_dims[0]['column'].replace('_', ' ').title()
        queries.append(f"{metric_label} by {geo_name}")

    # Demographic breakdowns
    demo_dims = [d for d in dimensions if any(g in d['column'].lower() for g in ['age', 'gender', 'ethnicity', 'deprivation'])]
    if demo_dims:
        demo_name = demo_dims[0]['column'].replace('_', ' ').title()
        queries.append(f"{metric_label} by {demo_name}")

    # Comparison query
    if len(kpis) > 1:
        queries.append(f"Compare {kpis[0]['label']} vs {kpis[1]['label']}")

    return queries[:4]  # Max 4 typical queries


def infer_is_measure(column_name: str, description: str, data_type: str) -> bool:
    """Infer if a column is a measure (KPI) based on heuristics."""
    col_lower = column_name.lower()
    desc_lower = (description or '').lower()

    # Check for explicit measure patterns in column name/description
    # (regardless of data type - handles varchar columns with numeric data)
    measure_patterns = [
        'count', 'rate', 'percentage', 'percent', 'total', 'sum', 'avg', 'average',
        'median', 'mean', 'value', 'amount', 'number_of', 'prevalence',
        'fte', 'headcount', 'volume', 'capacity', 'waiting_time', 'wait_time', 'wait'
    ]

    # Strong indicators (column name patterns)
    if any(col_lower.endswith('_' + pattern) or col_lower.startswith(pattern + '_') or pattern == col_lower
           for pattern in measure_patterns):
        # But not if it's an ID or reference code
        if not any(word in col_lower for word in ['_id', '_code', '_key']):
            return True

    # Numeric types are likely measures if they have measure-like names
    if data_type in ['INTEGER', 'BIGINT', 'NUMERIC', 'DECIMAL', 'FLOAT', 'DOUBLE PRECISION']:
        # But not if it's an ID or code
        if any(word in col_lower for word in ['_id', '_code', '_key', 'identifier']):
            return False

        # Any numeric column with measure-related description
        if any(word in desc_lower for word in measure_patterns):
            return True

    return False


def infer_is_dimension(column_name: str, description: str, data_type: str) -> bool:
    """Infer if a column is a dimension (filter/grouping) based on heuristics."""
    col_lower = column_name.lower()
    desc_lower = (description or '').lower()

    # Date/time columns are dimensions
    if data_type in ['DATE', 'TIMESTAMP', 'TIMESTAMP WITHOUT TIME ZONE', 'TIMESTAMP WITH TIME ZONE']:
        return True

    if any(word in col_lower for word in ['date', 'period', 'month', 'quarter', 'year', 'time']):
        return True

    # Geographic dimensions
    if any(word in col_lower or word in desc_lower for word in [
        'geography', 'region', 'area', 'location', 'icb', 'provider', 'practice',
        'sub_icb', 'locality', 'place', 'national', 'ons_code', 'org_code'
    ]):
        return True

    # Demographic dimensions
    if any(word in col_lower or word in desc_lower for word in [
        'age', 'gender', 'sex', 'ethnicity', 'deprivation', 'demographic'
    ]):
        return True

    # Category/breakdown columns
    if any(word in col_lower for word in [
        'category', 'level', 'breakdown', 'group', 'band', 'type', 'status'
    ]):
        return True

    # Code/name pairs
    if any(col_lower.endswith(suffix) for suffix in ['_code', '_name', '_id']):
        return True

    return False


def infer_query_keywords(column_name: str, description: str) -> List[str]:
    """Generate query keywords from column name and description."""
    keywords = []

    # Split column name into words
    words = column_name.replace('_', ' ').split()
    keywords.extend(words)

    # Extract key phrases from description (first 50 chars)
    if description:
        desc_words = description[:50].replace(',', '').replace('.', '').split()
        keywords.extend(desc_words[:5])

    # Remove duplicates and common words
    stopwords = {'the', 'a', 'an', 'and', 'or', 'of', 'for', 'in', 'to', 'is', 'by'}
    keywords = [k.lower() for k in keywords if k.lower() not in stopwords]

    return list(set(keywords))[:10]  # Max 10 keywords


def populate_metadata_for_source(source_code: str, conn) -> Dict:
    """Extract and aggregate metadata for a single source."""
    cur = conn.cursor()

    # Get all column metadata for this source
    cur.execute("""
        SELECT
            column_name,
            description,
            data_type,
            is_measure,
            is_dimension,
            query_keywords,
            min_value,
            max_value,
            null_rate,
            distinct_count
        FROM datawarp.tbl_column_metadata
        WHERE canonical_source_code = %s
        ORDER BY column_name
    """, (source_code,))

    columns = []
    for row in cur.fetchall():
        # Infer missing flags if not set
        is_measure = row[3]
        is_dimension = row[4]
        query_keywords = row[5] or []

        if not is_measure and not is_dimension:
            # Both false - infer from heuristics
            is_measure = infer_is_measure(row[0], row[1], row[2])
            is_dimension = infer_is_dimension(row[0], row[1], row[2])

        if not query_keywords:
            # No keywords - generate from column name/description
            query_keywords = infer_query_keywords(row[0], row[1])

        columns.append({
            'column_name': row[0],
            'description': row[1],
            'data_type': row[2],
            'is_measure': is_measure,
            'is_dimension': is_dimension,
            'query_keywords': query_keywords,
            'min_value': float(row[6]) if row[6] is not None else None,
            'max_value': float(row[7]) if row[7] is not None else None,
            'null_rate': float(row[8]) if row[8] is not None else None,
            'distinct_count': row[9]
        })

    if not columns:
        return {}

    # Build KPIs list
    kpis = []
    for col in columns:
        if col['is_measure']:
            unit = infer_unit(col['description'] or '', col['column_name'], col['data_type'])
            has_target = infer_has_target(col['column_name'], col['description'] or '')

            kpi = {
                'column': col['column_name'],
                'label': (col['description'] or col['column_name'].replace('_', ' ').title()),
                'description': col['description'],
                'unit': unit,
                'aggregation': infer_aggregation(col['data_type'], unit, col['column_name']),
                'query_keywords': col['query_keywords'],
                'has_target': has_target,
                'metric_type': infer_metric_type(col['column_name'], col['description'] or '', has_target)
            }

            # Add stats if available
            if col['min_value'] is not None:
                kpi['min_value'] = col['min_value']
            if col['max_value'] is not None:
                kpi['max_value'] = col['max_value']
            if col['null_rate'] is not None:
                kpi['null_rate'] = col['null_rate']

            kpis.append(kpi)

    # Build dimensions list
    dimensions = []
    for col in columns:
        if col['is_dimension']:
            dim = {
                'column': col['column_name'],
                'description': col['description']
            }
            if col['distinct_count'] is not None:
                dim['cardinality'] = col['distinct_count']
            dimensions.append(dim)

    # Infer organizational lenses
    org_lenses = infer_organizational_lenses(columns)

    # Infer granularity
    granularity = infer_granularity(dimensions)

    # Generate typical queries
    typical_queries = generate_typical_queries(kpis, dimensions, source_code)

    # Build complete metadata
    metadata = {
        'organizational_lenses': org_lenses,
        'kpis': kpis,
        'dimensions': dimensions,
        'granularity': granularity,
        'typical_queries': typical_queries,
        'column_count': len(columns),
        'measure_count': len(kpis),
        'dimension_count': len(dimensions),
        'last_metadata_update': datetime.utcnow().isoformat()
    }

    return metadata


def update_source_metadata(source_code: str, metadata: Dict, conn):
    """Update tbl_data_sources.metadata with aggregated metadata."""
    cur = conn.cursor()

    cur.execute("""
        UPDATE datawarp.tbl_data_sources
        SET metadata = %s::jsonb
        WHERE code = %s
    """, (json.dumps(metadata), source_code))

    conn.commit()


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description='Populate dataset-level metadata from column metadata')
    parser.add_argument('--all', action='store_true', help='Process all sources')
    parser.add_argument('--source', help='Process specific source code')
    parser.add_argument('--domain', help='Process all sources in domain')
    parser.add_argument('--dry-run', action='store_true', help='Preview metadata without updating')

    args = parser.parse_args()

    # Connect to database
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST'),
        port=os.getenv('POSTGRES_PORT'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
        database=os.getenv('POSTGRES_DB')
    )

    cur = conn.cursor()

    # Determine which sources to process
    if args.source:
        cur.execute("SELECT code FROM datawarp.tbl_data_sources WHERE code = %s", (args.source,))
    elif args.domain:
        cur.execute("SELECT code FROM datawarp.tbl_data_sources WHERE domain = %s", (args.domain,))
    elif args.all:
        # Only process sources that have column metadata
        cur.execute("""
            SELECT DISTINCT s.code
            FROM datawarp.tbl_data_sources s
            INNER JOIN datawarp.tbl_column_metadata cm ON cm.canonical_source_code = s.code
            ORDER BY s.code
        """)
    else:
        print("Error: Must specify --all, --source, or --domain")
        return 1

    source_codes = [row[0] for row in cur.fetchall()]

    if not source_codes:
        print("No sources found matching criteria")
        return 0

    print(f"Processing {len(source_codes)} sources...")

    success_count = 0
    error_count = 0

    for source_code in source_codes:
        try:
            print(f"\n{source_code}:")

            # Extract and aggregate metadata
            metadata = populate_metadata_for_source(source_code, conn)

            if not metadata:
                print(f"  ⚠️  No column metadata found, skipping")
                continue

            print(f"  ✓ {metadata['measure_count']} KPIs, {metadata['dimension_count']} dimensions")
            print(f"  ✓ Granularity: {metadata['granularity']}")
            print(f"  ✓ Lenses: {', '.join(k for k, v in metadata['organizational_lenses'].items() if v)}")

            if args.dry_run:
                print(f"  [DRY RUN] Would update metadata (size: {len(json.dumps(metadata))} bytes)")
                print(f"\n{json.dumps(metadata, indent=2)}")
            else:
                # Update database
                update_source_metadata(source_code, metadata, conn)
                print(f"  ✓ Metadata updated")

            success_count += 1

        except Exception as e:
            print(f"  ✗ Error: {e}")
            error_count += 1
            continue

    conn.close()

    print(f"\n{'='*60}")
    print(f"✓ Processed {success_count} sources successfully")
    if error_count > 0:
        print(f"✗ {error_count} sources had errors")

    return 0


if __name__ == '__main__':
    sys.exit(main())
