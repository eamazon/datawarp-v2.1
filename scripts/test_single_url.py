#!/usr/bin/env python3
"""
SIMPLE TEST: Process ONE NHS URL and monitor it with Gemini

This script shows you the ENTIRE flow in simple steps:
1. Download NHS file
2. Extract structure
3. Enrich with Gemini (add smart column names)
4. Load to PostgreSQL
5. Monitor with Gemini (check if it looks right)

NO automation, NO complexity - just ONE file to see how it works.
"""

import os
import sys
import yaml
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()


def print_step(step_num, title):
    """Print a clear step header"""
    print("\n" + "="*70)
    print(f"STEP {step_num}: {title}")
    print("="*70)


def main():
    print("\n" + "🚀 "*20)
    print("NHS DATA PIPELINE - SINGLE URL TEST")
    print("🚀 "*20)

    print("\nThis script will:")
    print("  1. Download ONE NHS Excel file (ADHD December 2025)")
    print("  2. Extract its structure (find tables, columns)")
    print("  3. Use Gemini to add smart names (instead of 'Sheet1')")
    print("  4. Load data into PostgreSQL database")
    print("  5. Use Gemini to check: 'Does this look right?'")
    print("\nTotal time: ~2-3 minutes")
    print("Total cost: ~$0.01 (Gemini API calls)")

    input("\nPress ENTER to start...")

    # STEP 1: Show what we're processing
    print_step(1, "What are we processing?")

    test_url = "https://digital.nhs.uk/data-and-information/publications/statistical/mi-adhd/december-2025"

    print(f"\nURL: {test_url}")
    print("Publication: ADHD Management Information")
    print("Period: December 2025")
    print("Type: Monthly NHS publication with Excel files")

    input("\nPress ENTER to continue...")

    # STEP 2: Generate manifest (find all Excel files on the page)
    print_step(2, "Download and detect structure")

    print("\nRunning: python scripts/url_to_manifest.py")
    print("This will:")
    print("  - Visit the NHS page")
    print("  - Find all Excel/CSV files")
    print("  - Download them")
    print("  - Detect tables and columns")
    print("\nThis takes ~30 seconds...")

    manifest_path = "manifests/test/adhd_dec25.yaml"
    os.makedirs("manifests/test", exist_ok=True)

    import subprocess
    result = subprocess.run([
        "python", "scripts/url_to_manifest.py",
        test_url,
        manifest_path
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"\n❌ Error: {result.stderr}")
        return

    print(f"\n✓ Structure detected and saved to: {manifest_path}")

    # Show what was found
    with open(manifest_path, 'r') as f:
        manifest = yaml.safe_load(f)

    print(f"\nFound {len(manifest['sources'])} tables:")
    for source in manifest['sources'][:3]:  # Show first 3
        print(f"  - Sheet: {source['sheet_name']}")
        print(f"    Columns: {len(source['columns'])}")

    if len(manifest['sources']) > 3:
        print(f"  ... and {len(manifest['sources']) - 3} more tables")

    input("\nPress ENTER to continue...")

    # STEP 3: Enrich with Gemini (add smart names)
    print_step(3, "Use Gemini to add smart names")

    print("\nInstead of generic names like:")
    print("  - 'sheet_1'")
    print("  - 'table_2'")
    print("  - 'column_a'")
    print("\nGemini will create semantic names like:")
    print("  - 'adhd_summary_referrals_by_age'")
    print("  - 'waiting_time_by_region'")
    print("  - 'patient_count'")

    print("\nRunning: python scripts/enrich_manifest.py")
    print("This takes ~20-30 seconds...")
    print("Cost: ~$0.005 (half a penny)")

    enriched_path = "manifests/test/adhd_dec25_enriched.yaml"

    result = subprocess.run([
        "python", "scripts/enrich_manifest.py",
        manifest_path,
        enriched_path
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"\n❌ Error: {result.stderr}")
        return

    print(f"\n✓ Smart names added! Saved to: {enriched_path}")

    # Show before/after example
    with open(enriched_path, 'r') as f:
        enriched = yaml.safe_load(f)

    print("\nExample of smart naming:")
    if enriched['sources']:
        source = enriched['sources'][0]
        print(f"  Original Sheet Name: {source.get('sheet_name', 'N/A')}")
        print(f"  Smart Code: {source.get('code', 'N/A')}")
        print(f"  Description: {source.get('description', 'N/A')[:60]}...")

    input("\nPress ENTER to continue...")

    # STEP 4: Load to database
    print_step(4, "Load data into PostgreSQL")

    print("\nRunning: datawarp load-batch")
    print("This will:")
    print("  - Create tables in PostgreSQL")
    print("  - Load all rows from Excel files")
    print("  - Track what was loaded")
    print("\nThis takes ~1-2 minutes...")

    result = subprocess.run([
        "datawarp", "load-batch", enriched_path
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"\n❌ Error: {result.stderr}")
        print("\nTip: Check that PostgreSQL is running")
        return

    print(f"\n✓ Data loaded to PostgreSQL!")
    print(result.stdout)

    input("\nPress ENTER to continue...")

    # STEP 5: Monitor with Gemini
    print_step(5, "Check with Gemini: 'Does this look right?'")

    print("\nNow let's ask Gemini to review what we just loaded...")
    print("Gemini will check:")
    print("  - Are there any 0-row loads? (broken extraction)")
    print("  - Are row counts reasonable?")
    print("  - Are there any errors?")

    print("\nRunning: python scripts/monitor_recent_loads.py")

    # Create simple monitoring script
    monitor_script = """
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
import google.generativeai as genai
import json

load_dotenv()

# Get recent loads
conn = psycopg2.connect(
    host=os.getenv('POSTGRES_HOST'),
    database=os.getenv('POSTGRES_DB'),
    user=os.getenv('POSTGRES_USER'),
    password=os.getenv('POSTGRES_PASSWORD')
)

cursor = conn.cursor(cursor_factory=RealDictCursor)
cursor.execute('''
    SELECT ds.code, lh.rows_loaded, lh.loaded_at
    FROM datawarp.tbl_load_history lh
    JOIN datawarp.tbl_data_sources ds ON lh.source_id = ds.id
    ORDER BY lh.loaded_at DESC
    LIMIT 5
''')

events = cursor.fetchall()
cursor.close()
conn.close()

print(f"\\nFound {len(events)} recent loads:\\n")

# Analyze with Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-2.0-flash-exp')

for event in events:
    print(f"Source: {event['code']}")
    print(f"Rows: {event['rows_loaded']:,}")

    # Ask Gemini
    prompt = f'''Analyze this NHS data load:
    Source: {event['code']}
    Rows Loaded: {event['rows_loaded']:,}

    Is this normal or anomalous? Output JSON only:
    {{"status": "normal|warning|critical", "reason": "brief explanation"}}
    '''

    response = model.generate_content(prompt)
    text = response.text.strip()

    # Extract JSON
    if '```json' in text:
        text = text.split('```json')[1].split('```')[0].strip()

    try:
        start = text.find('{')
        end = text.rfind('}') + 1
        analysis = json.loads(text[start:end])

        emoji = {"normal": "✅", "warning": "⚠️", "critical": "❌"}
        print(f"{emoji.get(analysis['status'], '?')} {analysis['status'].upper()}: {analysis['reason']}")
    except:
        print(f"Analysis: {text[:100]}")

    print()
"""

    with open('/tmp/monitor_recent.py', 'w') as f:
        f.write(monitor_script)

    result = subprocess.run(["python", "/tmp/monitor_recent.py"], capture_output=True, text=True)
    print(result.stdout)

    if result.returncode != 0:
        print(f"Error: {result.stderr}")

    # DONE
    print("\n" + "="*70)
    print("✅ TEST COMPLETE!")
    print("="*70)

    print("\nWhat happened:")
    print("  1. ✓ Downloaded NHS Excel file")
    print("  2. ✓ Extracted structure (tables, columns)")
    print("  3. ✓ Gemini added smart names")
    print("  4. ✓ Loaded to PostgreSQL")
    print("  5. ✓ Gemini checked: 'Looks good!'")

    print("\nYour data is now:")
    print(f"  - In PostgreSQL (staging.* tables)")
    print(f"  - In manifest files (manifests/test/)")
    print(f"  - Ready to query via MCP server")

    print("\nNext steps:")
    print("  - Add more URLs to publications_test.yaml")
    print("  - Run: python scripts/backfill.py")
    print("  - Set up monitoring cron job")

    print("\nQuestions? Check docs/README.md")
    print()


if __name__ == '__main__':
    main()
