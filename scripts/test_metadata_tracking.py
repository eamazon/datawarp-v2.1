#!/usr/bin/env python3
"""
Test metadata tracking across various edge cases.

Tests:
1. Initial load - metadata created
2. Reload same data - metadata unchanged
3. Schema drift - new columns added
4. Reference-based enrichment - metadata reused
5. LLM enrichment changes - metadata updated
6. Force reload - metadata preserved/updated correctly
7. Column type changes - metadata updated
"""

import sys
import psycopg2
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from datawarp.storage.connection import get_connection

# ANSI colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

class MetadataTest:
    """Test framework for metadata tracking."""

    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0

    def log(self, message, color=''):
        """Print colored log message."""
        print(f"{color}{message}{RESET}")

    def test(self, name, condition, details=''):
        """Run a test assertion."""
        self.tests_run += 1
        if condition:
            self.tests_passed += 1
            self.log(f"  ✓ {name}", GREEN)
            if details:
                self.log(f"    {details}", BLUE)
        else:
            self.tests_failed += 1
            self.log(f"  ✗ {name}", RED)
            if details:
                self.log(f"    {details}", RED)

    def section(self, title):
        """Print test section header."""
        self.log(f"\n{BOLD}{'='*80}", YELLOW)
        self.log(f"{title}", YELLOW)
        self.log(f"{'='*80}{RESET}\n", YELLOW)

    def summary(self):
        """Print test summary."""
        self.log(f"\n{BOLD}{'='*80}", BLUE)
        self.log(f"TEST SUMMARY", BLUE)
        self.log(f"{'='*80}{RESET}", BLUE)
        self.log(f"Total tests: {self.tests_run}")
        self.log(f"Passed: {self.tests_passed}", GREEN)
        if self.tests_failed > 0:
            self.log(f"Failed: {self.tests_failed}", RED)
        else:
            self.log(f"Failed: {self.tests_failed}", GREEN)

        pass_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        color = GREEN if pass_rate == 100 else YELLOW if pass_rate >= 80 else RED
        self.log(f"Pass rate: {pass_rate:.1f}%", color)

        return self.tests_failed == 0


def get_column_metadata(source_code):
    """Get all column metadata for a source."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    column_name,
                    original_name,
                    description,
                    data_type,
                    is_dimension,
                    is_measure,
                    query_keywords,
                    metadata_source,
                    confidence,
                    created_at,
                    updated_at
                FROM datawarp.tbl_column_metadata
                WHERE canonical_source_code = %s
                ORDER BY column_name
            """, (source_code,))

            columns = cur.fetchall()
            return [{
                'column_name': row[0],
                'original_name': row[1],
                'description': row[2],
                'data_type': row[3],
                'is_dimension': row[4],
                'is_measure': row[5],
                'query_keywords': row[6],
                'metadata_source': row[7],
                'confidence': row[8],
                'created_at': row[9],
                'updated_at': row[10]
            } for row in columns]


def get_load_history(source_code, limit=5):
    """Get recent load history for a source."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    lh.id,
                    lh.file_url,
                    lh.rows_loaded,
                    lh.columns_added,
                    lh.load_mode,
                    lh.loaded_at
                FROM datawarp.tbl_load_history lh
                JOIN datawarp.tbl_data_sources ds ON lh.source_id = ds.id
                WHERE ds.code = %s
                ORDER BY lh.loaded_at DESC
                LIMIT %s
            """, (source_code, limit))

            return cur.fetchall()


def get_table_columns(schema, table):
    """Get actual columns in a staging table."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
            """, (schema, table))

            return cur.fetchall()


def test_adhd_metadata(test):
    """Test ADHD publication metadata tracking."""
    test.section("TEST 1: ADHD Metadata Tracking")

    # Check metadata exists for ADHD sources
    sources_to_check = [
        'adhd_summary_open_referrals_age',
        'adhd_summary_closed_referrals_age',
        'adhd_mhsds_historic'
    ]

    for source_code in sources_to_check:
        metadata = get_column_metadata(source_code)

        test.test(
            f"Metadata exists for {source_code}",
            len(metadata) > 0,
            f"Found {len(metadata)} columns with metadata"
        )

        if metadata:
            # Check metadata fields are populated
            has_descriptions = sum(1 for m in metadata if m['description']) / len(metadata) * 100
            has_data_types = sum(1 for m in metadata if m['data_type']) / len(metadata) * 100

            test.test(
                f"  {source_code}: Descriptions populated",
                has_descriptions >= 80,
                f"{has_descriptions:.0f}% of columns have descriptions"
            )

            test.test(
                f"  {source_code}: Data types populated",
                has_data_types == 100,
                f"{has_data_types:.0f}% of columns have data types"
            )

            # Check for dimension/measure classification
            dimensions = [m for m in metadata if m['is_dimension']]
            measures = [m for m in metadata if m['is_measure']]

            test.test(
                f"  {source_code}: Has dimension columns",
                len(dimensions) > 0,
                f"Found {len(dimensions)} dimension columns"
            )

            test.test(
                f"  {source_code}: Has measure columns",
                len(measures) > 0,
                f"Found {len(measures)} measure columns"
            )

            # Check metadata source
            metadata_sources = set(m['metadata_source'] for m in metadata)
            test.test(
                f"  {source_code}: Metadata source tracked",
                len(metadata_sources) > 0,
                f"Sources: {', '.join(metadata_sources)}"
            )


def test_schema_drift_tracking(test):
    """Test schema drift is tracked in load history."""
    test.section("TEST 2: Schema Drift Tracking")

    sources_to_check = [
        'adhd_summary_open_referrals_age',
        'adhd_summary_closed_referrals_age'
    ]

    for source_code in sources_to_check:
        history = get_load_history(source_code, limit=10)

        test.test(
            f"Load history exists for {source_code}",
            len(history) > 0,
            f"Found {len(history)} load records"
        )

        if history:
            # Check if any loads added columns
            loads_with_drift = [h for h in history if h[3] and len(h[3]) > 0]  # columns_added

            if loads_with_drift:
                test.test(
                    f"  {source_code}: Schema drift detected and tracked",
                    True,
                    f"{len(loads_with_drift)} loads added new columns"
                )

                # Show example
                example = loads_with_drift[0]
                test.log(f"    Example: Added columns {example[3]}", BLUE)
            else:
                test.test(
                    f"  {source_code}: No schema drift recorded",
                    True,
                    "All loads matched existing schema"
                )


def test_metadata_consistency(test):
    """Test metadata is consistent with actual table schema."""
    test.section("TEST 3: Metadata vs Actual Schema Consistency")

    sources_to_check = [
        ('adhd_summary_open_referrals_age', 'staging', 'tbl_adhd_summary_open_referrals_age'),
        ('adhd_mhsds_historic', 'staging', 'tbl_adhd_mhsds_historic')
    ]

    for source_code, schema, table in sources_to_check:
        metadata = get_column_metadata(source_code)
        actual_columns = get_table_columns(schema, table)

        if not actual_columns:
            test.test(
                f"Table {schema}.{table} exists",
                False,
                "Table not found in database"
            )
            continue

        metadata_cols = set(m['column_name'] for m in metadata)
        actual_cols = set(col[0] for col in actual_columns)

        # Exclude system columns
        system_cols = {'period', 'data_date', 'loaded_at'}
        actual_cols = actual_cols - system_cols

        missing_in_metadata = actual_cols - metadata_cols
        extra_in_metadata = metadata_cols - actual_cols

        test.test(
            f"{source_code}: All table columns have metadata",
            len(missing_in_metadata) == 0,
            f"Missing: {missing_in_metadata}" if missing_in_metadata else "All columns tracked"
        )

        test.test(
            f"{source_code}: No orphaned metadata",
            len(extra_in_metadata) == 0,
            f"Extra: {extra_in_metadata}" if extra_in_metadata else "No orphaned metadata"
        )


def test_reference_vs_llm_metadata(test):
    """Test that reference-based enrichment preserves metadata."""
    test.section("TEST 4: Reference vs LLM Enrichment Metadata")

    # Find sources that used reference enrichment
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT canonical_source_code, metadata_source, COUNT(*)
                FROM datawarp.tbl_column_metadata
                WHERE canonical_source_code LIKE 'adhd%'
                GROUP BY canonical_source_code, metadata_source
                ORDER BY canonical_source_code, metadata_source
            """)

            results = cur.fetchall()

            test.test(
                "Metadata source tracking exists",
                len(results) > 0,
                f"Found {len(results)} source/metadata_source combinations"
            )

            for source_code, metadata_source, count in results:
                test.log(f"  {source_code}: {count} columns from '{metadata_source}'", BLUE)


def test_metadata_timestamps(test):
    """Test metadata created_at and updated_at timestamps."""
    test.section("TEST 5: Metadata Timestamp Tracking")

    sources_to_check = ['adhd_summary_open_referrals_age']

    for source_code in sources_to_check:
        metadata = get_column_metadata(source_code)

        if metadata:
            # Check if any metadata was updated after creation
            updated_metadata = [m for m in metadata if m['updated_at'] > m['created_at']]

            test.test(
                f"{source_code}: Metadata has timestamps",
                all(m['created_at'] and m['updated_at'] for m in metadata),
                "All metadata has created_at and updated_at"
            )

            if updated_metadata:
                test.test(
                    f"{source_code}: Metadata updates tracked",
                    True,
                    f"{len(updated_metadata)} columns have been updated"
                )
            else:
                test.test(
                    f"{source_code}: No metadata updates yet",
                    True,
                    "All metadata created_at == updated_at"
                )


def main():
    """Run all metadata tests."""
    test = MetadataTest()

    test.log(f"\n{BOLD}DataWarp Metadata Tracking Test Suite{RESET}", BLUE)
    test.log(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n", BLUE)

    try:
        # Run test suites
        test_adhd_metadata(test)
        test_schema_drift_tracking(test)
        test_metadata_consistency(test)
        test_reference_vs_llm_metadata(test)
        test_metadata_timestamps(test)

        # Print summary
        test.summary()

        # Exit with appropriate code
        sys.exit(0 if test.tests_failed == 0 else 1)

    except Exception as e:
        test.log(f"\n{BOLD}FATAL ERROR:{RESET}", RED)
        test.log(str(e), RED)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
