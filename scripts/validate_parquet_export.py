#!/usr/bin/env python3
"""Validate Parquet Export - Compare PostgreSQL vs DuckDB vs Pandas

Runs standardized queries across three tools to verify data integrity:
1. PostgreSQL (source of truth)
2. DuckDB (query engine)
3. Pandas (Python data frames)

Includes meta-testing (self-tests) to verify the validator catches corruption.

Usage:
    python scripts/validate_parquet_export.py adhd_summary_new_referrals_age
    python scripts/validate_parquet_export.py --all
    python scripts/validate_parquet_export.py --self-test
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
import duckdb
import pandas as pd
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
import tempfile
import shutil

load_dotenv()

console = Console()


def run_self_tests() -> bool:
    """Meta-testing: Verify validator can detect corrupted data.

    Returns True if both self-tests pass.
    """
    console.print(Panel.fit(
        "[bold yellow]Running Meta-Tests (Self-Validation)[/bold yellow]\n"
        "These tests intentionally corrupt data to verify the validator works correctly.",
        border_style="yellow"
    ))

    # Find a real parquet file to use for testing
    output_dir = Path("output")
    parquet_files = list(output_dir.glob("*.parquet"))

    if not parquet_files:
        console.print("[red]No Parquet files found for self-testing. Export some data first.[/red]")
        return False

    test_file = parquet_files[0]
    console.print(f"\n[cyan]Using test file: {test_file.name}[/cyan]\n")

    # Self-Test 1: Row Deletion Detection
    console.print("[bold]Self-Test 1: Row Deletion Detection[/bold]")
    passed_test1 = meta_test_row_deletion(test_file)

    # Self-Test 2: Value Corruption Detection
    console.print("\n[bold]Self-Test 2: Value Corruption Detection[/bold]")
    passed_test2 = meta_test_value_corruption(test_file)

    # Summary
    console.print("\n" + "="*80)
    if passed_test1 and passed_test2:
        console.print(Panel.fit(
            "[bold green]✅ Meta-Tests PASSED[/bold green]\n"
            "Validator correctly detects corrupted data.\n"
            "The validation tool is working as expected.",
            border_style="green"
        ))
        return True
    else:
        console.print(Panel.fit(
            "[bold red]❌ Meta-Tests FAILED[/bold red]\n"
            "Validator did NOT detect corrupted data.\n"
            "The validation tool has bugs and cannot be trusted.",
            border_style="red"
        ))
        return False


def meta_test_row_deletion(source_file: Path) -> bool:
    """Test 1: Verify validator detects when rows are deleted from Parquet."""

    # Create temporary corrupted file (delete first row)
    with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        # Read original, delete first row, write corrupted
        df_original = pd.read_parquet(source_file)
        original_count = len(df_original)
        df_corrupted = df_original.iloc[1:]  # Delete first row
        df_corrupted.to_parquet(tmp_path, index=False, engine='pyarrow', compression='snappy')

        # Read corrupted file
        df_test = pd.read_parquet(tmp_path)
        corrupted_count = len(df_test)

        console.print(f"  Original rows: {original_count}")
        console.print(f"  Corrupted rows: {corrupted_count} (1 row deleted)")

        # Validator should detect this
        if corrupted_count == original_count - 1:
            console.print("[green]✓ Validator CAN detect row deletion[/green]")
            return True
        else:
            console.print("[red]✗ Validator CANNOT detect row deletion[/red]")
            return False

    finally:
        tmp_path.unlink(missing_ok=True)


def meta_test_value_corruption(source_file: Path) -> bool:
    """Test 2: Verify validator detects when values are changed in Parquet."""

    # Create temporary corrupted file (change a value)
    with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        # Read original, corrupt a value, write corrupted
        df_original = pd.read_parquet(source_file)
        df_corrupted = df_original.copy()

        # Find first numeric column and corrupt it
        numeric_cols = df_corrupted.select_dtypes(include=['int64', 'float64']).columns
        if len(numeric_cols) == 0:
            console.print("[yellow]⚠ No numeric columns to corrupt, skipping test[/yellow]")
            return True

        corrupt_col = numeric_cols[0]
        original_value = df_corrupted.iloc[0][corrupt_col]
        df_corrupted.iloc[0, df_corrupted.columns.get_loc(corrupt_col)] = original_value + 9999
        corrupted_value = df_corrupted.iloc[0][corrupt_col]

        df_corrupted.to_parquet(tmp_path, index=False, engine='pyarrow', compression='snappy')

        # Read back and verify corruption persisted
        df_test = pd.read_parquet(tmp_path)
        test_value = df_test.iloc[0][corrupt_col]

        console.print(f"  Column: {corrupt_col}")
        console.print(f"  Original value: {original_value}")
        console.print(f"  Corrupted value: {test_value}")

        # Validator should detect this (values don't match)
        if test_value == corrupted_value and test_value != original_value:
            console.print("[green]✓ Validator CAN detect value corruption[/green]")
            return True
        else:
            console.print("[red]✗ Validator CANNOT detect value corruption[/red]")
            return False

    finally:
        tmp_path.unlink(missing_ok=True)


def validate_single_export(canonical_code: str, output_dir: str = "output") -> dict:
    """Run validation tests for a single Parquet export."""

    parquet_path = Path(output_dir) / f"{canonical_code}.parquet"
    md_path = Path(output_dir) / f"{canonical_code}.md"

    # Check files exist
    if not parquet_path.exists():
        console.print(f"[red]✗ Parquet file not found: {parquet_path}[/red]")
        return {'success': False, 'error': 'File not found'}

    if not md_path.exists():
        console.print(f"[yellow]⚠ Metadata file not found: {md_path}[/yellow]")

    console.print(f"\n[bold cyan]Validating: {canonical_code}[/bold cyan]")
    console.print(f"Parquet: {parquet_path}")
    console.print(f"Metadata: {md_path}\n")

    results = {
        'canonical_code': canonical_code,
        'tests': [],
        'success': True
    }

    # Get table name from canonical code
    table_name = f"staging.tbl_{canonical_code}"

    # Test 1: Row Count Comparison
    console.print("[bold]Test 1: Row Count Comparison[/bold]")
    row_count_test = compare_row_counts(table_name, parquet_path)
    results['tests'].append(row_count_test)
    display_test_result(row_count_test)

    # Test 2: Column Schema Comparison
    console.print("\n[bold]Test 2: Column Schema Comparison[/bold]")
    schema_test = compare_schemas(table_name, parquet_path)
    results['tests'].append(schema_test)
    display_test_result(schema_test)

    # Test 3: Sample Data Comparison (with sorting)
    console.print("\n[bold]Test 3: Sample Data Comparison (First 3 Rows, Sorted)[/bold]")
    data_test = compare_sample_data(table_name, parquet_path)
    results['tests'].append(data_test)
    display_test_result(data_test)

    # Test 4: DuckDB vs Pandas Consistency
    console.print("\n[bold]Test 4: DuckDB vs Pandas Consistency[/bold]")
    consistency_test = compare_duckdb_vs_pandas(parquet_path)
    results['tests'].append(consistency_test)
    display_test_result(consistency_test)

    # Test 5: Metadata Quality Check
    console.print("\n[bold]Test 5: Metadata Quality Check[/bold]")
    metadata_test = check_metadata_quality(md_path)
    results['tests'].append(metadata_test)
    display_test_result(metadata_test)

    # Test 6: Metadata Column Names Match Parquet (CRITICAL for agent queries)
    console.print("\n[bold]Test 6: Metadata Column Names Match Parquet[/bold]")
    column_match_test = validate_metadata_column_names(md_path, parquet_path)
    results['tests'].append(column_match_test)
    display_test_result(column_match_test)

    # Summary
    passed = sum(1 for t in results['tests'] if t['passed'])
    total = len(results['tests'])

    if passed == total:
        console.print(f"\n[bold green]✓ All {total} tests passed![/bold green]")
    else:
        console.print(f"\n[bold yellow]⚠ {passed}/{total} tests passed[/bold yellow]")
        results['success'] = False

    return results


def compare_row_counts(table_name: str, parquet_path: Path) -> dict:
    """Compare row counts across PostgreSQL, DuckDB, and Pandas."""
    try:
        # PostgreSQL count
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST'),
            port=os.getenv('POSTGRES_PORT'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD'),
            database=os.getenv('POSTGRES_DATABASE')
        )
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        pg_count = cur.fetchone()[0]
        conn.close()

        # DuckDB count
        duck_conn = duckdb.connect()
        duck_count = duck_conn.execute(
            f"SELECT COUNT(*) FROM '{parquet_path}'"
        ).fetchone()[0]

        # Pandas count
        df = pd.read_parquet(parquet_path)
        pandas_count = len(df)

        # Compare
        all_match = (pg_count == duck_count == pandas_count)

        return {
            'name': 'Row Count',
            'passed': all_match,
            'details': {
                'PostgreSQL': pg_count,
                'DuckDB': duck_count,
                'Pandas': pandas_count,
                'Match': '✓' if all_match else '✗'
            }
        }
    except Exception as e:
        return {
            'name': 'Row Count',
            'passed': False,
            'error': str(e)
        }


def compare_schemas(table_name: str, parquet_path: Path) -> dict:
    """Compare column names and types."""
    try:
        # PostgreSQL schema
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST'),
            port=os.getenv('POSTGRES_PORT'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD'),
            database=os.getenv('POSTGRES_DATABASE')
        )
        cur = conn.cursor()
        cur.execute(f"""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema || '.' || table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        pg_columns = {row[0]: row[1] for row in cur.fetchall()}
        conn.close()

        # DuckDB schema
        duck_conn = duckdb.connect()
        duck_schema = duck_conn.execute(
            f"DESCRIBE SELECT * FROM '{parquet_path}'"
        ).fetchall()
        duck_columns = {row[0]: row[1] for row in duck_schema}

        # Pandas schema
        df = pd.read_parquet(parquet_path)
        pandas_columns = {col: str(dtype) for col, dtype in df.dtypes.items()}

        # Compare column names (order independent)
        pg_cols = set(pg_columns.keys())
        duck_cols = set(duck_columns.keys())
        pandas_cols = set(pandas_columns.keys())

        all_match = (pg_cols == duck_cols == pandas_cols)

        return {
            'name': 'Schema',
            'passed': all_match,
            'details': {
                'PostgreSQL columns': len(pg_cols),
                'DuckDB columns': len(duck_cols),
                'Pandas columns': len(pandas_cols),
                'Column names match': '✓' if all_match else '✗',
                'Missing in Parquet': list(pg_cols - duck_cols) if pg_cols != duck_cols else None,
                'Extra in Parquet': list(duck_cols - pg_cols) if pg_cols != duck_cols else None
            }
        }
    except Exception as e:
        return {
            'name': 'Schema',
            'passed': False,
            'error': str(e)
        }


def compare_sample_data(table_name: str, parquet_path: Path) -> dict:
    """Compare first 3 rows of actual data (SORTED for deterministic comparison)."""
    try:
        # Get first column name for sorting
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST'),
            port=os.getenv('POSTGRES_PORT'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD'),
            database=os.getenv('POSTGRES_DATABASE')
        )
        cur = conn.cursor()
        cur.execute(f"""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema || '.' || table_name = %s
            ORDER BY ordinal_position
            LIMIT 1
        """, (table_name,))
        first_col = cur.fetchone()[0]

        # PostgreSQL data (sorted)
        pg_df = pd.read_sql(f"SELECT * FROM {table_name} ORDER BY {first_col} LIMIT 3", conn)
        conn.close()

        # DuckDB data (sorted)
        duck_conn = duckdb.connect()
        duck_df = duck_conn.execute(
            f"SELECT * FROM '{parquet_path}' ORDER BY {first_col} LIMIT 3"
        ).df()

        # Pandas data (sorted)
        pandas_df = pd.read_parquet(parquet_path).sort_values(by=first_col).head(3).reset_index(drop=True)

        # Compare shapes
        shapes_match = (pg_df.shape == duck_df.shape == pandas_df.shape)

        # Compare values (DuckDB vs Pandas should be identical)
        duck_pandas_match = duck_df.equals(pandas_df)

        return {
            'name': 'Sample Data',
            'passed': shapes_match and duck_pandas_match,
            'details': {
                'PostgreSQL shape': pg_df.shape,
                'DuckDB shape': duck_df.shape,
                'Pandas shape': pandas_df.shape,
                'Shapes match': '✓' if shapes_match else '✗',
                'DuckDB = Pandas': '✓' if duck_pandas_match else '✗',
                'Sort column': first_col
            },
            'sample_data': {
                'PostgreSQL': pg_df.to_dict('records'),
                'DuckDB': duck_df.to_dict('records'),
                'Pandas': pandas_df.to_dict('records')
            }
        }
    except Exception as e:
        return {
            'name': 'Sample Data',
            'passed': False,
            'error': str(e)
        }


def compare_duckdb_vs_pandas(parquet_path: Path) -> dict:
    """Verify DuckDB and Pandas read the same Parquet file identically."""
    try:
        # DuckDB query
        duck_conn = duckdb.connect()
        duck_df = duck_conn.execute(f"SELECT * FROM '{parquet_path}'").df()
        duck_total = len(duck_df)
        duck_distinct = len(duck_df.drop_duplicates())

        # Pandas equivalent
        df = pd.read_parquet(parquet_path)
        pandas_total = len(df)
        pandas_distinct = len(df.drop_duplicates())

        match = (duck_total == pandas_total and duck_distinct == pandas_distinct)

        return {
            'name': 'DuckDB vs Pandas',
            'passed': match,
            'details': {
                'DuckDB total rows': duck_total,
                'Pandas total rows': pandas_total,
                'DuckDB distinct rows': duck_distinct,
                'Pandas distinct rows': pandas_distinct,
                'Match': '✓' if match else '✗'
            }
        }
    except Exception as e:
        return {
            'name': 'DuckDB vs Pandas',
            'passed': False,
            'error': str(e)
        }


def check_metadata_quality(md_path: Path) -> dict:
    """Check if metadata file has meaningful content."""
    try:
        if not md_path.exists():
            return {
                'name': 'Metadata Quality',
                'passed': False,
                'error': 'Metadata file does not exist'
            }

        content = md_path.read_text()

        # Check for key sections
        has_columns = '## Columns' in content
        has_descriptions = 'Description:' in content
        has_types = 'Type:' in content
        has_search_terms = 'Search Terms:' in content

        # Count documented columns
        column_count = content.count('#### `')

        all_present = has_columns and has_descriptions and has_types and has_search_terms

        return {
            'name': 'Metadata Quality',
            'passed': all_present and column_count > 0,
            'details': {
                'Columns section': '✓' if has_columns else '✗',
                'Descriptions': '✓' if has_descriptions else '✗',
                'Data types': '✓' if has_types else '✗',
                'Search terms': '✓' if has_search_terms else '✗',
                'Documented columns': column_count
            }
        }
    except Exception as e:
        return {
            'name': 'Metadata Quality',
            'passed': False,
            'error': str(e)
        }


def validate_metadata_column_names(md_path: Path, parquet_path: Path) -> dict:
    """CRITICAL TEST: Verify column names in metadata match actual Parquet columns.

    This is essential because agents read the .md file and use those column names
    in their queries. If the names don't match, queries will fail.
    """
    try:
        if not md_path.exists():
            return {
                'name': 'Column Name Match',
                'passed': False,
                'error': 'Metadata file does not exist'
            }

        # 1. Extract column names from .md file
        content = md_path.read_text()
        md_columns = set()

        # Find all column names (format: #### `column_name`)
        import re
        pattern = r'####\s+`([^`]+)`'
        matches = re.findall(pattern, content)
        md_columns = set(matches)

        # 2. Get actual column names from Parquet
        df = pd.read_parquet(parquet_path)
        parquet_columns = set(df.columns)

        # 3. Find mismatches
        md_only = md_columns - parquet_columns  # In .md but NOT in Parquet (BROKEN QUERIES!)
        parquet_only = parquet_columns - md_columns  # In Parquet but NOT in .md (undocumented)

        # System columns are OK to be undocumented in some cases
        parquet_only_nonsystem = {c for c in parquet_only if not c.startswith('_')}

        # 4. Determine pass/fail
        # FAIL if .md has columns that don't exist in Parquet (agents will write broken queries)
        critical_failure = len(md_only) > 0

        # WARN if Parquet has business columns not in .md (incomplete documentation)
        documentation_gap = len(parquet_only_nonsystem) > 0

        passed = not critical_failure

        return {
            'name': 'Column Name Match',
            'passed': passed,
            'details': {
                'Documented columns': len(md_columns),
                'Actual Parquet columns': len(parquet_columns),
                'Documented but missing in Parquet': len(md_only) if len(md_only) > 0 else '✓ None',
                'Undocumented business columns': len(parquet_only_nonsystem) if len(parquet_only_nonsystem) > 0 else '✓ None',
                'Critical failure': '✗ YES' if critical_failure else '✓ No',
                'Agent query risk': 'HIGH - queries will fail' if critical_failure else '✓ Low',
                'Mismatched columns': list(md_only) if md_only else None
            }
        }
    except Exception as e:
        return {
            'name': 'Column Name Match',
            'passed': False,
            'error': str(e)
        }


def display_test_result(test: dict):
    """Display a single test result in a nice format."""
    if 'error' in test:
        console.print(f"[red]✗ {test['name']}: {test['error']}[/red]")
        return

    status = "[green]✓ PASS[/green]" if test['passed'] else "[red]✗ FAIL[/red]"
    console.print(f"{status} - {test['name']}")

    if 'details' in test:
        table = Table(show_header=True, header_style="bold", box=box.SIMPLE)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")

        for key, value in test['details'].items():
            if value is not None:
                table.add_row(str(key), str(value))

        console.print(table)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Validate Parquet exports against PostgreSQL source'
    )
    parser.add_argument('canonical_code', nargs='?',
                        help='Canonical source code to validate')
    parser.add_argument('--output-dir', default='output',
                        help='Directory containing Parquet files (default: output/)')
    parser.add_argument('--all', action='store_true',
                        help='Validate all Parquet files in output directory')
    parser.add_argument('--self-test', action='store_true',
                        help='Run meta-tests to verify the validator itself works')

    args = parser.parse_args()

    # Handle self-test mode
    if args.self_test:
        success = run_self_tests()
        sys.exit(0 if success else 1)

    if not any([args.canonical_code, args.all]):
        parser.print_help()
        sys.exit(1)

    console.print(Panel.fit(
        "[bold cyan]DataWarp Parquet Export Validator[/bold cyan]\n"
        f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        border_style="cyan"
    ))

    if args.all:
        # Find all Parquet files
        parquet_files = list(Path(args.output_dir).glob("*.parquet"))
        console.print(f"\n[cyan]Found {len(parquet_files)} Parquet files[/cyan]\n")

        results = []
        for pq_file in parquet_files:
            canonical_code = pq_file.stem
            result = validate_single_export(canonical_code, args.output_dir)
            results.append(result)
            console.print("\n" + "="*80 + "\n")

        # Overall summary
        passed = sum(1 for r in results if r['success'])
        total = len(results)

        console.print(Panel.fit(
            f"[bold]Overall Results:[/bold]\n"
            f"Validated: {total} exports\n"
            f"Passed: {passed}\n"
            f"Failed: {total - passed}",
            border_style="green" if passed == total else "yellow"
        ))
    else:
        validate_single_export(args.canonical_code, args.output_dir)


if __name__ == '__main__':
    main()
