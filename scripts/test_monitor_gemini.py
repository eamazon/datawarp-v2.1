#!/usr/bin/env python3
"""
Test monitoring script using Gemini API

Tests LLM-powered load event analysis on a small sample.
Shows token usage, cost, and analysis quality.
"""

import os
import sys
import json
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import google.generativeai as genai

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

load_dotenv()


def get_recent_load_events(limit=5):
    """Fetch recent load events from database"""
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST'),
        database=os.getenv('POSTGRES_DB'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
        port=os.getenv('POSTGRES_PORT')
    )

    cursor = conn.cursor(cursor_factory=RealDictCursor)

    query = """
    SELECT
        ds.code as source_code,
        ds.table_name,
        lh.rows_loaded,
        lh.columns_added,
        lh.load_mode,
        lh.loaded_at,
        lh.file_url
    FROM datawarp.tbl_load_history lh
    JOIN datawarp.tbl_data_sources ds ON lh.source_id = ds.id
    ORDER BY lh.loaded_at DESC
    LIMIT %s
    """

    cursor.execute(query, (limit,))
    events = cursor.fetchall()

    cursor.close()
    conn.close()

    return events


def analyze_event_with_gemini(event):
    """Use Gemini to analyze a load event"""

    # Configure Gemini
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel(os.getenv('LLM_MODEL', 'gemini-2.0-flash-exp'))

    prompt = f"""You are a DataWarp monitoring agent. Analyze this load event for anomalies.

Event Data:
- Source: {event['source_code']}
- Table: {event['table_name']}
- Rows Loaded: {event['rows_loaded']:,}
- Columns Added: {event['columns_added'] or 'None'}
- Load Mode: {event['load_mode']}
- Timestamp: {event['loaded_at']}
- File URL: {event['file_url'][:80]}...

Your task:
1. Determine if this event is normal, warning, or critical
2. Suggest an action: none, retry, alert, or investigate
3. Explain your reasoning in 1-2 sentences

Output ONLY valid JSON in this format:
{{
  "status": "normal|warning|critical",
  "action": "none|retry|alert|investigate",
  "reason": "explanation here",
  "confidence": 0.0-1.0
}}
"""

    # Call Gemini
    response = model.generate_content(prompt)

    # Parse JSON response
    try:
        # Extract JSON from response (might have markdown wrapper)
        text = response.text.strip()
        if text.startswith('```json'):
            text = text.split('```json')[1].split('```')[0].strip()
        elif text.startswith('```'):
            text = text.split('```')[1].split('```')[0].strip()

        analysis = json.loads(text)

        # Add token usage if available
        if hasattr(response, 'usage_metadata'):
            analysis['tokens'] = {
                'input': response.usage_metadata.prompt_token_count,
                'output': response.usage_metadata.candidates_token_count,
                'total': response.usage_metadata.total_token_count
            }

        return analysis

    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {e}")
        print(f"Raw response: {response.text}")
        return {
            "status": "error",
            "action": "investigate",
            "reason": f"Failed to parse LLM response: {str(e)}",
            "confidence": 0.0
        }


def main():
    print("="*70)
    print("DataWarp Monitoring Test - Gemini API")
    print("="*70)
    print()

    # Get recent events
    print("Fetching recent load events...")
    events = get_recent_load_events(limit=3)  # Start with just 3
    print(f"Found {len(events)} events\n")

    total_tokens = 0
    analyses = []

    for i, event in enumerate(events, 1):
        print(f"\n{'='*70}")
        print(f"Event {i}/{len(events)}")
        print(f"{'='*70}")
        print(f"Source: {event['source_code']}")
        print(f"Rows: {event['rows_loaded']:,}")
        print(f"Columns Added: {event['columns_added'] or 'None'}")
        print(f"Mode: {event['load_mode']}")
        print(f"Loaded: {event['loaded_at']}")
        print()

        print("Analyzing with Gemini...")
        analysis = analyze_event_with_gemini(event)

        print(f"\n✓ Analysis Complete:")
        print(f"  Status: {analysis['status'].upper()}")
        print(f"  Action: {analysis['action']}")
        print(f"  Reason: {analysis['reason']}")
        print(f"  Confidence: {analysis.get('confidence', 'N/A')}")

        if 'tokens' in analysis:
            tokens = analysis['tokens']
            print(f"\n  Token Usage:")
            print(f"    Input: {tokens['input']} tokens")
            print(f"    Output: {tokens['output']} tokens")
            print(f"    Total: {tokens['total']} tokens")
            total_tokens += tokens['total']

        analyses.append({
            'event': event,
            'analysis': analysis
        })

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Total Events Analyzed: {len(events)}")
    print(f"Total Tokens Used: {total_tokens:,}")

    # Calculate cost (Gemini Flash pricing)
    # Input: $0.075 per 1M tokens
    # Output: $0.30 per 1M tokens
    # Approximate 50/50 split for rough estimate
    cost = (total_tokens / 1_000_000) * 0.1875  # Average of input/output
    print(f"Estimated Cost: ${cost:.6f}")
    print(f"Cost per Event: ${cost/len(events):.6f}")

    # Daily/monthly projections
    daily_events = 50
    monthly_events = daily_events * 30
    daily_cost = (cost / len(events)) * daily_events
    monthly_cost = daily_cost * 30

    print(f"\nProjections (assuming {daily_events} events/day):")
    print(f"  Daily Cost: ${daily_cost:.4f}")
    print(f"  Monthly Cost: ${monthly_cost:.2f}")
    print(f"  Yearly Cost: ${monthly_cost * 12:.2f}")

    # Status breakdown
    statuses = {}
    for item in analyses:
        status = item['analysis']['status']
        statuses[status] = statuses.get(status, 0) + 1

    print(f"\nStatus Breakdown:")
    for status, count in statuses.items():
        print(f"  {status.capitalize()}: {count}")

    print()


if __name__ == '__main__':
    main()
