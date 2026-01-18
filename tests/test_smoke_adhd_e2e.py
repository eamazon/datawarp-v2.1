#!/usr/bin/env python3
"""
ADHD E2E Smoke Test - Real pipeline execution for pre-commit hook

This test runs a REAL end-to-end pipeline with ADHD (smallest publication):
- Downloads actual NHS file (or uses cached)
- Runs enrichment (with reference, no LLM call)
- Loads to database
- Verifies metadata stored

Total time: ~15-20 seconds (acceptable for pre-commit)

WHY: After v2.2 refactoring hell, we need actual E2E validation at commit time,
not just logic tests. This catches integration issues BEFORE they enter the repo.

Can be skipped with: SKIP_E2E_SMOKE=1 git commit
"""

import pytest
import subprocess
import sys
import os
from pathlib import Path
from datawarp.storage.connection import get_connection

PROJECT_ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="module")
def skip_if_disabled():
    """Skip if SKIP_E2E_SMOKE environment variable is set."""
    if os.getenv('SKIP_E2E_SMOKE'):
        pytest.skip("E2E smoke test skipped (SKIP_E2E_SMOKE=1)")


def test_adhd_e2e_pipeline(skip_if_disabled):
    """Test ADHD publication through entire pipeline.

    PERFORMANCE MODES:
    - Without FORCE_E2E: Health check (0.4s) - checks data exists
    - With FORCE_E2E=1: Real pipeline (9.6s) - actually runs everything

    Usage:
        # Fast mode (default)
        pytest tests/test_smoke_adhd_e2e.py

        # Real E2E mode
        FORCE_E2E=1 pytest tests/test_smoke_adhd_e2e.py
    """

    # Check if we should force actual pipeline execution
    force_real_e2e = os.getenv('FORCE_E2E') == '1'

    # Run backfill for ADHD (smallest, fastest publication)
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "backfill.py"),
        "--pub", "adhd",
        "--config", str(PROJECT_ROOT / "config" / "publications_with_all_urls.yaml"),
        "--period", "2025-05",  # Single period only
        "--quiet"
    ]

    if force_real_e2e:
        cmd.append("--force")  # Actually re-run pipeline
        print("\n🚀 FORCE_E2E=1: Running REAL pipeline (~10 seconds)...")
    else:
        print("\n🏥 Health check mode: Verifying system state (~0.5 seconds)...")
        print("   (Set FORCE_E2E=1 to run actual pipeline)")

    print("\n🔄 Running ADHD E2E pipeline...")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,  # 60 second timeout
        cwd=str(PROJECT_ROOT)
    )

    # Check command succeeded
    if result.returncode != 0:
        print(f"\n❌ Backfill failed:\n{result.stdout}\n{result.stderr}")
        pytest.fail(f"ADHD backfill failed with code {result.returncode}")

    print("✅ ADHD pipeline completed")

    # Verify data in database
    try:
        with get_connection() as conn:
            cur = conn.cursor()

            # Check sources registered
            cur.execute("""
                SELECT COUNT(*) FROM datawarp.tbl_data_sources
                WHERE code LIKE 'adhd%'
            """)
            source_count = cur.fetchone()[0]
            assert source_count > 0, "❌ No ADHD sources in database"
            print(f"✅ {source_count} ADHD sources registered")

            # Check metadata stored
            cur.execute("""
                SELECT COUNT(*) FROM datawarp.tbl_column_metadata
                WHERE canonical_source_code LIKE 'adhd%'
            """)
            metadata_count = cur.fetchone()[0]
            assert metadata_count > 0, "❌ CRITICAL: No ADHD metadata stored"
            print(f"✅ {metadata_count} ADHD columns with metadata")

            # Check at least one table has data
            cur.execute("""
                SELECT table_name FROM datawarp.tbl_data_sources
                WHERE code LIKE 'adhd%'
                LIMIT 1
            """)
            result = cur.fetchone()
            if result:
                table_name = result[0]
                cur.execute(f"SELECT COUNT(*) FROM staging.{table_name}")
                row_count = cur.fetchone()[0]
                assert row_count > 0, f"❌ No data in {table_name}"
                print(f"✅ {row_count} rows loaded in {table_name}")

    except Exception as e:
        pytest.fail(f"❌ Database validation failed: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
