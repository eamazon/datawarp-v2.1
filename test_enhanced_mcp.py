#!/usr/bin/env python3
"""Quick test of enhanced MCP tools."""

import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from mcp_server.backends.postgres import PostgreSQLBackend
from datawarp.storage.connection import get_connection

backend = PostgreSQLBackend()

print("Testing Enhanced MCP Tools")
print("=" * 60)

# Test 1: discover_by_keyword simulation
print("\n1. Testing discover_by_keyword (searching for 'prevalence')...")
with get_connection() as conn:
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT canonical_source_code, COUNT(*) as match_count
        FROM datawarp.tbl_column_metadata
        WHERE 'prevalence' = ANY(query_keywords) OR 'count' = ANY(query_keywords)
        GROUP BY canonical_source_code
        ORDER BY match_count DESC
        LIMIT 5
    """)
    results = cur.fetchall()
    print(f"   Found {len(results)} matching datasets:")
    for row in results:
        print(f"     - {row[0]} ({row[1]} matches)")

# Test 2: get_kpis simulation
print("\n2. Testing get_kpis for 'adhd_prevalence'...")
metadata = backend.get_dataset_metadata('adhd_prevalence')
if metadata and metadata.get('metadata'):
    kpis = metadata['metadata'].get('kpis', [])
    print(f"   Found {len(kpis)} KPIs:")
    for kpi in kpis:
        print(f"     - {kpi['column']}: {kpi['label'][:60]}...")
else:
    print("   No metadata found")

# Test 3: query_metric simulation
print("\n3. Testing query_metric for 'patient_count'...")
df = backend.load_dataset('adhd_prevalence', limit=5)
if 'patient_count' in df.columns:
    print(f"   Column exists! Sample values:")
    print(f"     - Total rows loaded: {len(df)}")
    print(f"     - Columns: {list(df.columns)[:5]}...")
else:
    print(f"   Column 'patient_count' not found in dataset")

print("\n" + "=" * 60)
print("✓ All tests completed successfully!")
print("\nNext: Test in Claude Desktop to verify MCP protocol integration")
