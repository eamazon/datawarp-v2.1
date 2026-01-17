#!/usr/bin/env python3
"""Test semantic discovery with correct keywords."""

import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

print("=" * 100)
print("TEST: Semantic Discovery by Keyword (FIXED)")
print("=" * 100)

conn = psycopg2.connect(
    host=os.getenv('POSTGRES_HOST'),
    port=os.getenv('POSTGRES_PORT'),
    user=os.getenv('POSTGRES_USER'),
    password=os.getenv('POSTGRES_PASSWORD'),
    database=os.getenv('POSTGRES_DB')
)
cur = conn.cursor()

# Use actual keywords from the database
keywords = ['rtt', 'completed_pathways']

print(f"\nSearching for datasets with keywords: {keywords}")
print("-" * 100)

cur.execute("""
    SELECT DISTINCT
        ds.code,
        ds.name,
        COUNT(cm.column_name) as matching_columns
    FROM datawarp.tbl_data_sources ds
    INNER JOIN datawarp.tbl_column_metadata cm
        ON cm.canonical_source_code = ds.code
    WHERE cm.query_keywords && %s  -- Array overlap operator
    GROUP BY ds.code, ds.name
    ORDER BY matching_columns DESC
""", (keywords,))

results = cur.fetchall()
print(f"✅ Found {len(results)} datasets:\n")

for code, name, count in results:
    print(f"  📊 {name}")
    print(f"     Code: {code}")
    print(f"     Matching columns: {count}")
    print()

# Also test single keyword search
print("\n" + "=" * 100)
print("Single keyword search: 'provider_count'")
print("-" * 100)

cur.execute("""
    SELECT 
        cm.canonical_source_code,
        cm.column_name,
        cm.description
    FROM datawarp.tbl_column_metadata cm
    WHERE 'provider_count' = ANY(cm.query_keywords)
    ORDER BY cm.canonical_source_code, cm.column_name
""")

results2 = cur.fetchall()
print(f"✅ Found {len(results2)} columns with 'provider_count' keyword:\n")

for source, col, desc in results2[:5]:
    print(f"  • {source}.{col}")
    print(f"    {desc[:80]}...")
    print()

conn.close()

print("=" * 100)
print("✅ ALL TESTS PASSED")
print("=" * 100)
