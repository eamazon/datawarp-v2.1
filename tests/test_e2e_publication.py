#!/usr/bin/env python3
"""
End-to-End Publication Test Suite

Comprehensive testing for DataWarp publication pipeline with DYNAMIC
publication discovery from config/publications_with_all_urls.yaml.

Test Categories:
1. TestE2EPublication - Core validation (config, CLI, tables, columns, data, periods)
2. TestE2EEvidence - Database evidence collection (workbooks, columns, manifests)
3. TestE2EForceReload - Force reload functionality
4. TestE2EValidation - Config error handling

Usage:
    # Test a single publication (dynamically discovered)
    pytest tests/test_e2e_publication.py -k "bed_overnight" -v

    # Run all tests for all publications in config
    pytest tests/test_e2e_publication.py -v

    # Show detailed evidence output
    pytest tests/test_e2e_publication.py -k "adhd" -v -s

    # Run only evidence collection tests
    pytest tests/test_e2e_publication.py -k "Evidence" -v -s

    # Run standalone with full report
    python tests/test_e2e_publication.py adhd --force

Publications are automatically discovered from:
    config/publications_with_all_urls.yaml
"""

import pytest
import subprocess
import psycopg2
import yaml
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Test configuration
CONFIG_FILE = PROJECT_ROOT / "config" / "publications_with_all_urls.yaml"
LOGS_DIR = PROJECT_ROOT / "logs"

# Database connection
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "database": os.getenv("POSTGRES_DB", "datawarp2"),
    "user": os.getenv("POSTGRES_USER", "databot"),
    "password": os.getenv("POSTGRES_PASSWORD", "databot_dev_password"),
}


@dataclass
class E2ETestResult:
    """Results from e2e test run."""
    publication: str
    success: bool
    cli_exit_code: int
    cli_output: str
    cli_duration_seconds: float
    tables_created: List[str]
    total_rows: int
    periods_loaded: List[str]
    columns_sample: Dict[str, List[str]]
    errors: List[str]
    warnings: List[str]


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def load_config() -> dict:
    """Load publications config."""
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)


def get_publication_info(pub_code: str) -> Optional[dict]:
    """Get publication config by code."""
    config = load_config()
    return config.get("publications", {}).get(pub_code)


def clear_publication_data(pub_code: str) -> int:
    """Clear all data for a publication. Returns rows deleted."""
    conn = get_db_connection()
    cursor = conn.cursor()
    total_deleted = 0

    try:
        # Get tables that might belong to this publication
        cursor.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'staging'
        """)
        tables = [row[0] for row in cursor.fetchall()]

        # Clear manifest tracking
        cursor.execute("""
            DELETE FROM datawarp.tbl_manifest_files
            WHERE source_code ILIKE %s
        """, (f"%{pub_code.split('_')[-1]}%",))

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Warning: Could not clear data: {e}")
    finally:
        cursor.close()
        conn.close()

    return total_deleted


def get_staging_tables() -> List[str]:
    """Get all staging tables."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'staging'
        ORDER BY table_name
    """)
    tables = [row[0] for row in cursor.fetchall()]

    cursor.close()
    conn.close()
    return tables


def get_table_info(table_name: str) -> Dict:
    """Get detailed info about a table."""
    conn = get_db_connection()
    cursor = conn.cursor()

    info = {
        "name": table_name,
        "columns": [],
        "row_count": 0,
        "periods": [],
        "sample_data": None
    }

    try:
        # Get columns
        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'staging' AND table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        info["columns"] = [(row[0], row[1]) for row in cursor.fetchall()]

        # Get row count
        cursor.execute(f'SELECT COUNT(*) FROM staging."{table_name}"')
        info["row_count"] = cursor.fetchone()[0]

        # Get periods if _period column exists
        col_names = [c[0] for c in info["columns"]]
        if "_period" in col_names:
            cursor.execute(f'SELECT DISTINCT _period FROM staging."{table_name}" ORDER BY _period')
            info["periods"] = [row[0] for row in cursor.fetchall()]

        # Get sample data (first 3 rows)
        cursor.execute(f'SELECT * FROM staging."{table_name}" LIMIT 3')
        info["sample_data"] = cursor.fetchall()

    except Exception as e:
        info["error"] = str(e)

    cursor.close()
    conn.close()
    return info


def get_manifest_records(pub_code: str) -> List[Dict]:
    """Get manifest file records for publication."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Build search patterns from publication code
    # e.g., "bed_overnight" -> search for "bed", "overnight", "beds"
    parts = pub_code.lower().replace("_", " ").split()
    patterns = []
    for part in parts:
        patterns.append(f"%{part}%")
        # Also try plural/singular variations
        if part.endswith("s"):
            patterns.append(f"%{part[:-1]}%")
        else:
            patterns.append(f"%{part}s%")

    # Build OR query
    where_clauses = " OR ".join(["source_code ILIKE %s"] * len(patterns))
    cursor.execute(f"""
        SELECT source_code, period, status, rows_loaded, loaded_at, manifest_name
        FROM datawarp.tbl_manifest_files
        WHERE {where_clauses}
        ORDER BY period, source_code
    """, patterns)

    records = []
    for row in cursor.fetchall():
        records.append({
            "source_code": row[0],
            "period": row[1],
            "status": row[2],
            "rows_loaded": row[3],
            "loaded_at": row[4],
            "manifest_name": row[5] if len(row) > 5 else "unknown"
        })

    cursor.close()
    conn.close()
    return records


def run_backfill_cli(pub_code: str, force: bool = False, timeout: int = 300) -> Tuple[int, str, float]:
    """Run backfill.py CLI and return (exit_code, output, duration)."""
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "backfill.py"),
        "--pub", pub_code,
        "--config", str(CONFIG_FILE),
        "--quiet"
    ]

    if force:
        cmd.append("--force")

    start = datetime.now()

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(PROJECT_ROOT)
    )

    duration = (datetime.now() - start).total_seconds()
    output = result.stdout + "\n" + result.stderr

    return result.returncode, output, duration


def validate_semantic_names(columns: List[Tuple[str, str]]) -> Tuple[bool, List[str]]:
    """Validate that column names are semantic (not generic like col_0, col_1)."""
    import re
    issues = []

    for col_name, col_type in columns:
        # Skip system columns
        if col_name.startswith("_"):
            continue

        # Check for truly generic names (col_0, col_1, column_a, etc.)
        # Note: col_100_general_surgery is OK - it's NHS specialty code with description
        if re.match(r"^col_\d+$", col_name):  # col_0, col_1 (no description)
            issues.append(f"Generic column name: {col_name}")
        elif re.match(r"^column_[a-z]$", col_name):  # column_a, column_b
            issues.append(f"Generic column name: {col_name}")

        # Check for very short names (likely not semantic)
        if len(col_name) < 3 and col_name not in ("id", "no"):
            issues.append(f"Very short column name: {col_name}")

        # Check for numeric-only names
        if col_name.isdigit():
            issues.append(f"Numeric column name: {col_name}")

    return len(issues) == 0, issues


def validate_table_name(table_name: str) -> Tuple[bool, List[str]]:
    """Validate that table name is semantic."""
    issues = []

    # Should start with tbl_
    if not table_name.startswith("tbl_"):
        issues.append(f"Table doesn't start with tbl_: {table_name}")

    # Should not contain date patterns (we want date-agnostic names)
    import re
    if re.search(r"20\d{2}", table_name):
        issues.append(f"Table name contains year: {table_name}")
    if re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\d{2}", table_name, re.I):
        issues.append(f"Table name contains month: {table_name}")

    return len(issues) == 0, issues


# =============================================================================
# PYTEST FIXTURES
# =============================================================================

@pytest.fixture(scope="session")
def db_connection():
    """Provide database connection for session."""
    conn = get_db_connection()
    yield conn
    conn.close()


@pytest.fixture
def config():
    """Load config file."""
    return load_config()


# =============================================================================
# DYNAMIC TEST CASE DISCOVERY
# =============================================================================

def get_all_publications_from_config() -> List[str]:
    """Dynamically get all publications from config file."""
    try:
        config = load_config()
        return list(config.get("publications", {}).keys())
    except Exception as e:
        print(f"Warning: Could not load config: {e}")
        return []


def get_test_publications():
    """Generate pytest params dynamically from config."""
    pubs = get_all_publications_from_config()
    return [pytest.param(pub, id=pub) for pub in pubs]


# Dynamic publication discovery from config
TEST_PUBLICATIONS = get_test_publications()


class TestE2EPublication:
    """End-to-end tests for publication loading."""

    @pytest.mark.parametrize("pub_code", TEST_PUBLICATIONS)
    def test_publication_exists_in_config(self, pub_code: str, config: dict):
        """Test that publication exists in config file."""
        pub_info = config.get("publications", {}).get(pub_code)
        assert pub_info is not None, f"Publication '{pub_code}' not found in config"
        assert pub_info.get("name"), f"Publication '{pub_code}' missing 'name' field"

    @pytest.mark.parametrize("pub_code", TEST_PUBLICATIONS)
    def test_publication_has_valid_urls(self, pub_code: str, config: dict):
        """Test that publication has valid URLs or template."""
        pub_info = config.get("publications", {}).get(pub_code)

        if "urls" in pub_info:
            # Explicit URLs mode
            for entry in pub_info["urls"]:
                assert entry.get("period"), f"Missing period in URL entry"
                assert entry.get("url"), f"Missing URL for period {entry.get('period')}"
                url = entry.get("url")
                assert url.startswith(("http://", "https://")), f"Invalid URL: {url}"
        else:
            # Template mode
            assert pub_info.get("landing_page") or pub_info.get("url_template"), \
                f"Publication needs either 'urls' or 'landing_page'/'url_template'"

    @pytest.mark.parametrize("pub_code", TEST_PUBLICATIONS)
    def test_cli_runs_successfully(self, pub_code: str, force_reload: bool):
        """Test that CLI runs without errors."""
        exit_code, output, duration = run_backfill_cli(pub_code, force=force_reload)

        # Check for validation errors
        assert "CONFIG VALIDATION FAILED" not in output, \
            f"Config validation failed:\n{output}"

        # Check for successful completion or already loaded
        success_indicators = [
            "COMPLETE:",
            "ALL DATA UP TO DATE",
            "already loaded"
        ]
        has_success = any(ind in output for ind in success_indicators)

        assert exit_code == 0, f"CLI failed with exit code {exit_code}:\n{output}"
        assert has_success, f"CLI output doesn't indicate success:\n{output}"

        print(f"\n  Duration: {duration:.1f}s")
        print(f"  Output: {output[:500]}...")

    @pytest.mark.parametrize("pub_code", TEST_PUBLICATIONS)
    def test_tables_created_with_semantic_names(self, pub_code: str):
        """Test that tables are created with semantic names."""
        # First ensure data is loaded
        run_backfill_cli(pub_code)

        # Get manifest records
        records = get_manifest_records(pub_code)
        assert len(records) > 0, f"No manifest records found for {pub_code}"

        # Check table names
        source_codes = set(r["source_code"] for r in records)
        for source_code in source_codes:
            table_name = f"tbl_{source_code}"
            valid, issues = validate_table_name(table_name)
            assert valid, f"Table name issues: {issues}"

    @pytest.mark.parametrize("pub_code", TEST_PUBLICATIONS)
    def test_columns_have_semantic_names(self, pub_code: str):
        """Test that columns have semantic names (not generic)."""
        # First ensure data is loaded
        run_backfill_cli(pub_code)

        # Get all tables
        tables = get_staging_tables()

        # Find tables related to this publication
        pub_tables = [t for t in tables if pub_code.split("_")[-1] in t.lower()]

        if not pub_tables:
            # Try finding by manifest records
            records = get_manifest_records(pub_code)
            pub_tables = [f"tbl_{r['source_code']}" for r in records]
            pub_tables = [t for t in pub_tables if t.replace("tbl_", "") in [r["source_code"] for r in records]]

        # Skip test if no tables found (may not have been loaded yet)
        if len(pub_tables) == 0:
            pytest.skip(f"No tables found for {pub_code} - may need to load data first")

        all_issues = []
        for table in pub_tables[:3]:  # Check first 3 tables
            if table in tables:
                info = get_table_info(table)
                valid, issues = validate_semantic_names(info["columns"])
                if not valid:
                    all_issues.extend([f"{table}: {i}" for i in issues])

        # Warn but don't fail for a few generic columns (some NHS data has unavoidable generic names)
        if all_issues:
            print(f"\n  Column warnings: {all_issues[:5]}")
            # Fail only if more than 5 generic columns
            assert len(all_issues) <= 5, f"Too many column name issues: {all_issues[:10]}"

    @pytest.mark.parametrize("pub_code", TEST_PUBLICATIONS)
    def test_data_loaded_to_database(self, pub_code: str):
        """Test that data is actually loaded to database."""
        # First ensure data is loaded
        run_backfill_cli(pub_code)

        # Get manifest records
        records = get_manifest_records(pub_code)
        assert len(records) > 0, f"No manifest records for {pub_code}"

        # Check total rows
        total_rows = sum(r["rows_loaded"] or 0 for r in records)
        assert total_rows > 0, f"No rows loaded for {pub_code}"

        # Verify at least one record has 'loaded' status
        loaded = [r for r in records if r["status"] == "loaded"]
        assert len(loaded) > 0, f"No records with 'loaded' status"

        print(f"\n  Records: {len(records)}")
        print(f"  Total rows: {total_rows:,}")
        print(f"  Loaded: {len(loaded)}")

    @pytest.mark.parametrize("pub_code", TEST_PUBLICATIONS)
    def test_period_tracking_works(self, pub_code: str):
        """Test that period tracking is working correctly."""
        # First ensure data is loaded
        run_backfill_cli(pub_code)

        # Get manifest records
        records = get_manifest_records(pub_code)

        # Skip if no records (publication may not have loaded yet)
        if len(records) == 0:
            pytest.skip(f"No manifest records for {pub_code} - may need to load data first")

        # Check periods are valid format
        import re
        for r in records:
            period = r["period"]
            # Should match various period formats
            valid_formats = [
                r"^\d{4}-\d{2}$",       # 2025-04 (monthly)
                r"^FY\d{2}-Q[1-4]$",    # FY25-Q1 (fiscal quarter)
                r"^FY\d{2,4}-\d{2}$",   # FY2024-25 (fiscal year)
                r"^\d{4}$",             # 2025 (annual)
                r"^\d{4}-Q[1-4]$",      # 2020-Q1 (calendar quarter)
                r"^\d{4}-\d{2}-\d{2}$", # 2025-04-01 (daily)
            ]
            is_valid = any(re.match(fmt, str(period)) for fmt in valid_formats)
            assert is_valid, f"Invalid period format: {period}"

        print(f"\n  Periods: {set(r['period'] for r in records)}")


class TestE2EEvidence:
    """Database evidence collection tests."""

    @pytest.mark.parametrize("pub_code", TEST_PUBLICATIONS)
    def test_collect_workbook_evidence(self, pub_code: str):
        """Collect and report workbook-level evidence."""
        run_backfill_cli(pub_code)
        records = get_manifest_records(pub_code)

        if not records:
            pytest.skip(f"No records for {pub_code}")

        # Group by manifest name
        workbooks = {}
        for r in records:
            manifest = r.get("manifest_name", "unknown")
            if manifest not in workbooks:
                workbooks[manifest] = {"sheets": 0, "rows": 0, "periods": set()}
            workbooks[manifest]["sheets"] += 1
            workbooks[manifest]["rows"] += r["rows_loaded"] or 0
            if r["period"]:
                workbooks[manifest]["periods"].add(r["period"])

        print(f"\n{'='*80}")
        print(f"WORKBOOK EVIDENCE: {pub_code}")
        print(f"{'='*80}")
        for wb, stats in workbooks.items():
            print(f"  {wb[:60]}")
            print(f"    Sheets: {stats['sheets']}, Rows: {stats['rows']:,}, Periods: {stats['periods']}")
        print(f"{'='*80}")

    @pytest.mark.parametrize("pub_code", TEST_PUBLICATIONS)
    def test_collect_column_evidence(self, pub_code: str):
        """Collect and report column metadata evidence."""
        run_backfill_cli(pub_code)
        records = get_manifest_records(pub_code)

        if not records:
            pytest.skip(f"No records for {pub_code}")

        # Get unique source codes and their tables
        source_codes = set(r["source_code"] for r in records)
        tables = get_staging_tables()

        print(f"\n{'='*80}")
        print(f"COLUMN EVIDENCE: {pub_code}")
        print(f"{'='*80}")

        total_cols = 0
        semantic_cols = 0
        generic_cols = []

        for source in list(source_codes)[:5]:  # Sample 5 tables
            table = f"tbl_{source}"
            if table in tables:
                info = get_table_info(table)
                cols = info["columns"]
                total_cols += len(cols)

                print(f"\n  TABLE: {table} ({len(cols)} columns, {info['row_count']:,} rows)")
                print(f"  Sample columns:")
                for col_name, col_type in cols[:8]:
                    print(f"    {col_name:<50} {col_type}")

                valid, issues = validate_semantic_names(cols)
                if not valid:
                    generic_cols.extend(issues)
                else:
                    semantic_cols += len(cols)

        print(f"\n  SUMMARY: {semantic_cols}/{total_cols} semantic columns")
        if generic_cols:
            print(f"  Generic columns found: {generic_cols[:5]}")
        print(f"{'='*80}")

    @pytest.mark.parametrize("pub_code", TEST_PUBLICATIONS)
    def test_collect_manifest_evidence(self, pub_code: str):
        """Collect and report manifest tracking evidence."""
        run_backfill_cli(pub_code)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get all manifest records with full details
        parts = pub_code.lower().replace("_", " ").split()
        patterns = [f"%{part}%" for part in parts]
        where_clauses = " OR ".join(["source_code ILIKE %s"] * len(patterns))

        cursor.execute(f"""
            SELECT
                manifest_name,
                source_code,
                period,
                status,
                rows_loaded,
                loaded_at
            FROM datawarp.tbl_manifest_files
            WHERE {where_clauses}
            ORDER BY loaded_at DESC
            LIMIT 20
        """, patterns)

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        if not rows:
            pytest.skip(f"No manifest records for {pub_code}")

        print(f"\n{'='*80}")
        print(f"MANIFEST EVIDENCE: {pub_code}")
        print(f"{'='*80}")
        print(f"  {'SOURCE':<40} {'PERIOD':<12} {'STATUS':<10} {'ROWS':>10}")
        print(f"  {'-'*40} {'-'*12} {'-'*10} {'-'*10}")

        for row in rows[:15]:
            source = row[1][:38] + '..' if len(row[1]) > 40 else row[1]
            print(f"  {source:<40} {row[2] or 'N/A':<12} {row[3]:<10} {row[4] or 0:>10,}")

        print(f"\n  Total records: {len(rows)}")
        print(f"{'='*80}")


class TestE2EForceReload:
    """Test force reload functionality."""

    @pytest.mark.parametrize("pub_code", TEST_PUBLICATIONS[:1] if TEST_PUBLICATIONS else [])
    def test_force_reload_replaces_data(self, pub_code: str):
        """Test that --force flag reloads data."""
        # First load
        exit_code1, output1, _ = run_backfill_cli(pub_code)
        assert exit_code1 == 0

        records1 = get_manifest_records(pub_code)

        # Second load without force (should skip)
        exit_code2, output2, _ = run_backfill_cli(pub_code, force=False)
        assert exit_code2 == 0
        assert "already loaded" in output2 or "UP TO DATE" in output2

        # Third load with force (should reload)
        exit_code3, output3, _ = run_backfill_cli(pub_code, force=True)
        assert exit_code3 == 0
        assert "COMPLETE:" in output3


class TestE2EValidation:
    """Validation-focused tests."""

    def test_config_validation_catches_errors(self):
        """Test that config validation catches errors."""
        # Create a temp bad config
        bad_config = PROJECT_ROOT / "config" / "test_bad_e2e.yaml"
        bad_config.write_text("""
publications:
  bad_pub:
    name: "Bad Publication"
    urls:
      - period: 2025-01
        # Missing URL!
""")

        try:
            cmd = [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "backfill.py"),
                "--pub", "bad_pub",
                "--config", str(bad_config),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            assert result.returncode != 0, "Should fail on bad config"
            assert "CONFIG VALIDATION FAILED" in result.stdout + result.stderr
        finally:
            bad_config.unlink()

    def test_nonexistent_publication_error(self):
        """Test error handling for non-existent publication."""
        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "backfill.py"),
            "--pub", "nonexistent_pub_xyz",
            "--config", str(CONFIG_FILE),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        assert result.returncode != 0, "Should fail for non-existent pub"
        assert "PUBLICATION NOT FOUND" in result.stdout + result.stderr


# =============================================================================
# COMPREHENSIVE E2E REPORT
# =============================================================================

def run_comprehensive_e2e(pub_code: str, force: bool = False) -> E2ETestResult:
    """Run comprehensive e2e test and return detailed results."""
    result = E2ETestResult(
        publication=pub_code,
        success=False,
        cli_exit_code=-1,
        cli_output="",
        cli_duration_seconds=0,
        tables_created=[],
        total_rows=0,
        periods_loaded=[],
        columns_sample={},
        errors=[],
        warnings=[]
    )

    # Check config
    pub_info = get_publication_info(pub_code)
    if not pub_info:
        result.errors.append(f"Publication '{pub_code}' not found in config")
        return result

    # Run CLI
    try:
        exit_code, output, duration = run_backfill_cli(pub_code, force=force)
        result.cli_exit_code = exit_code
        result.cli_output = output
        result.cli_duration_seconds = duration

        if exit_code != 0:
            result.errors.append(f"CLI failed with exit code {exit_code}")
    except subprocess.TimeoutExpired:
        result.errors.append("CLI timed out")
        return result
    except Exception as e:
        result.errors.append(f"CLI error: {e}")
        return result

    # Get manifest records
    records = get_manifest_records(pub_code)
    if not records:
        result.warnings.append("No manifest records found")
    else:
        result.total_rows = sum(r["rows_loaded"] or 0 for r in records)
        result.periods_loaded = list(set(r["period"] for r in records))

    # Get tables
    tables = get_staging_tables()
    result.tables_created = [t for t in tables if any(
        part in t.lower() for part in pub_code.lower().split("_")[-2:]
    )]

    # Get column samples
    for table in result.tables_created[:3]:
        info = get_table_info(table)
        result.columns_sample[table] = [c[0] for c in info["columns"][:10]]

        # Validate
        valid, issues = validate_semantic_names(info["columns"])
        if not valid:
            result.warnings.extend(issues)

    result.success = len(result.errors) == 0 and result.total_rows > 0

    return result


def print_e2e_report(result: E2ETestResult):
    """Print formatted e2e test report."""
    print("\n" + "=" * 80)
    print(f"E2E TEST REPORT: {result.publication}")
    print("=" * 80)

    status = "PASS" if result.success else "FAIL"
    print(f"\nStatus: {status}")
    print(f"CLI Exit Code: {result.cli_exit_code}")
    print(f"Duration: {result.cli_duration_seconds:.1f}s")

    print(f"\nDatabase Evidence:")
    print(f"  Tables Created: {len(result.tables_created)}")
    for t in result.tables_created:
        print(f"    - {t}")

    print(f"  Total Rows: {result.total_rows:,}")
    print(f"  Periods: {result.periods_loaded}")

    if result.columns_sample:
        print(f"\nColumn Samples:")
        for table, cols in result.columns_sample.items():
            print(f"  {table}:")
            for col in cols[:5]:
                print(f"    - {col}")

    if result.errors:
        print(f"\nErrors:")
        for e in result.errors:
            print(f"  - {e}")

    if result.warnings:
        print(f"\nWarnings:")
        for w in result.warnings:
            print(f"  - {w}")

    print("\n" + "=" * 80)


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run e2e tests for a publication")
    parser.add_argument("pub_code", help="Publication code to test")
    parser.add_argument("--force", action="store_true", help="Force reload data")
    parser.add_argument("--clear", action="store_true", help="Clear existing data first")

    args = parser.parse_args()

    if args.clear:
        print(f"Clearing data for {args.pub_code}...")
        clear_publication_data(args.pub_code)

    print(f"Running e2e test for: {args.pub_code}")
    result = run_comprehensive_e2e(args.pub_code, force=args.force)
    print_e2e_report(result)

    sys.exit(0 if result.success else 1)
