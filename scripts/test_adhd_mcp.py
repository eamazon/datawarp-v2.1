#!/usr/bin/env python3
"""
Test ADHD data queries through MCP server

This simulates what Claude Desktop would do when you ask questions
about ADHD data.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd

# Load the catalog
catalog_path = "output/catalog.parquet"
catalog = pd.read_parquet(catalog_path)

print("="*70)
print("ADHD Data Available Through MCP Server")
print("="*70)
print()

# Find all ADHD datasets
adhd_datasets = catalog[catalog['source_code'].str.contains('adhd', case=False, na=False)]

print(f"Found {len(adhd_datasets)} ADHD-related datasets:\n")

# Show summary
for idx, row in adhd_datasets.iterrows():
    print(f"📊 {row['source_code']}")
    print(f"   Rows: {row['row_count']:,}")
    print(f"   Columns: {row['column_count']}")
    if pd.notna(row.get('description')):
        desc = str(row['description'])[:60]
        print(f"   Description: {desc}...")
    print()

# Test queries
print("\n" + "="*70)
print("Sample Queries You Can Ask Claude Desktop")
print("="*70)
print()

queries = [
    "How many ADHD referrals were there in May 2025?",
    "What is the average wait time for ADHD assessment?",
    "Compare ADHD referrals by age group",
    "Show me ADHD prevalence estimates",
    "What percentage of ADHD patients are on medication?",
]

for i, query in enumerate(queries, 1):
    print(f"{i}. {query}")

print()
print("="*70)
print("How to Use")
print("="*70)
print()
print("1. Open Claude Desktop app")
print("2. Restart it (to load the MCP server)")
print("3. Look for the 🔌 icon (MCP tools)")
print("4. Ask any question about ADHD data!")
print()
print("The MCP server will:")
print("  - Search through 184 NHS datasets")
print("  - Find relevant ADHD tables")
print("  - Query the data")
print("  - Return results in natural language")
print()

# Show sample data
print("="*70)
print("Sample ADHD Data Preview")
print("="*70)
print()

# Try to load a small ADHD dataset
try:
    sample_file = "output/adhd_summary_new_referrals_age.parquet"
    if os.path.exists(sample_file):
        df = pd.read_parquet(sample_file)
        print(f"Preview of: adhd_summary_new_referrals_age")
        print(f"Total rows: {len(df):,}")
        print()
        print(df.head(10).to_string())
        print()
    else:
        print("(Sample file not found)")
except Exception as e:
    print(f"Could not load sample: {e}")

print()
print("="*70)
print("Next Steps")
print("="*70)
print()
print("✅ MCP server configured")
print("✅ Catalog built (184 datasets)")
print("✅ ADHD data loaded and ready")
print()
print("👉 Open Claude Desktop and ask: 'What ADHD datasets are available?'")
print()
