#!/usr/bin/env python3
"""
Test monitoring with synthetic anomalies

Tests how well Gemini detects different types of problems.
"""

import os
import sys
import json
from dotenv import load_dotenv
import google.generativeai as genai

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
load_dotenv()


def analyze_event_with_gemini(event):
    """Use Gemini to analyze a load event"""
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel(os.getenv('LLM_MODEL', 'gemini-2.0-flash-exp'))

    prompt = f"""You are a DataWarp monitoring agent. Analyze this load event for anomalies.

Event Data:
- Source: {event['source_code']}
- Rows Loaded: {event['rows_loaded']:,}
- Columns Added: {event.get('columns_added', 'None')}
- Load Mode: {event['load_mode']}
- Error: {event.get('error', 'None')}
- Previous Load: {event.get('previous_rows', 'Unknown')} rows

Historical Context:
- Typical row count: {event.get('typical_range', 'Unknown')}
- Last 5 loads: {event.get('recent_history', 'No data')}

Your task:
1. Determine if this event is normal, warning, or critical
2. Suggest an action: none, retry, alert, or investigate
3. Explain your reasoning in 1-2 sentences

Output ONLY valid JSON:
{{
  "status": "normal|warning|critical",
  "action": "none|retry|alert|investigate",
  "reason": "explanation here",
  "confidence": 0.0-1.0
}}
"""

    response = model.generate_content(prompt)

    # Parse JSON
    try:
        text = response.text.strip()
        if text.startswith('```json'):
            text = text.split('```json')[1].split('```')[0].strip()
        elif text.startswith('```'):
            text = text.split('```')[1].split('```')[0].strip()

        analysis = json.loads(text)

        if hasattr(response, 'usage_metadata'):
            analysis['tokens'] = {
                'input': response.usage_metadata.prompt_token_count,
                'output': response.usage_metadata.candidates_token_count,
                'total': response.usage_metadata.total_token_count
            }

        return analysis

    except json.JSONDecodeError as e:
        return {
            "status": "error",
            "action": "investigate",
            "reason": f"Failed to parse: {str(e)}",
            "confidence": 0.0
        }


def main():
    print("="*70)
    print("DataWarp Monitoring Test - Anomaly Detection")
    print("="*70)
    print()

    # Test cases with different anomalies
    test_cases = [
        {
            "name": "Zero Rows Loaded (Critical)",
            "event": {
                "source_code": "adhd_summary_referrals",
                "rows_loaded": 0,
                "columns_added": "None",
                "load_mode": "replace",
                "error": "None",
                "previous_rows": 45234,
                "typical_range": "40k-50k",
                "recent_history": "44k, 45k, 43k, 46k, 44k"
            },
            "expected": "critical"
        },
        {
            "name": "Connection Timeout (Retry)",
            "event": {
                "source_code": "pcn_workforce_mar25",
                "rows_loaded": 0,
                "columns_added": "None",
                "load_mode": "replace",
                "error": "ConnectionTimeout: Failed to download file after 30s",
                "previous_rows": 12500,
                "typical_range": "10k-15k",
                "recent_history": "12k, 13k, 12k, 11k, 13k"
            },
            "expected": "warning"
        },
        {
            "name": "Suspicious Low Row Count (Warning)",
            "event": {
                "source_code": "gp_practice_registrations",
                "rows_loaded": 150,
                "columns_added": "None",
                "load_mode": "replace",
                "error": "None",
                "previous_rows": 2100000,
                "typical_range": "2M-2.2M",
                "recent_history": "2.1M, 2.15M, 2.08M, 2.12M, 2.1M"
            },
            "expected": "critical"
        },
        {
            "name": "Large Schema Drift (Investigate)",
            "event": {
                "source_code": "online_consultation_nov25",
                "rows_loaded": 534000,
                "columns_added": "['fiscal_year_q1', 'fiscal_year_q2', 'fiscal_year_q3', 'fiscal_year_q4', 'annual_total']",
                "load_mode": "append",
                "error": "None",
                "previous_rows": 527000,
                "typical_range": "500k-600k",
                "recent_history": "520k, 534k, 510k, 540k, 527k"
            },
            "expected": "warning"
        },
        {
            "name": "Normal Load (Baseline)",
            "event": {
                "source_code": "adhd_medication_usage",
                "rows_loaded": 45234,
                "columns_added": "None",
                "load_mode": "replace",
                "error": "None",
                "previous_rows": 44890,
                "typical_range": "40k-50k",
                "recent_history": "44k, 45k, 43k, 46k, 44k"
            },
            "expected": "normal"
        }
    ]

    results = []
    total_tokens = 0

    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*70}")
        print(f"Test Case {i}/{len(test_cases)}: {test['name']}")
        print(f"{'='*70}")
        print(f"Source: {test['event']['source_code']}")
        print(f"Rows: {test['event']['rows_loaded']:,}")
        print(f"Error: {test['event']['error']}")
        print(f"Expected: {test['expected'].upper()}")
        print()

        analysis = analyze_event_with_gemini(test['event'])

        print(f"✓ Gemini Analysis:")
        print(f"  Status: {analysis['status'].upper()}")
        print(f"  Action: {analysis['action']}")
        print(f"  Reason: {analysis['reason']}")
        print(f"  Confidence: {analysis.get('confidence', 'N/A')}")

        if 'tokens' in analysis:
            tokens = analysis['tokens']
            print(f"  Tokens: {tokens['total']}")
            total_tokens += tokens['total']

        # Check if detected correctly
        correct = analysis['status'] == test['expected']
        emoji = "✅" if correct else "❌"
        print(f"\n  Result: {emoji} {'CORRECT' if correct else 'INCORRECT'}")

        results.append({
            'test': test['name'],
            'expected': test['expected'],
            'actual': analysis['status'],
            'correct': correct,
            'analysis': analysis
        })

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")

    correct_count = sum(1 for r in results if r['correct'])
    accuracy = (correct_count / len(results)) * 100

    print(f"Accuracy: {correct_count}/{len(results)} ({accuracy:.0f}%)")
    print(f"Total Tokens: {total_tokens:,}")

    cost = (total_tokens / 1_000_000) * 0.1875
    print(f"Total Cost: ${cost:.6f}")

    print("\nDetailed Results:")
    for r in results:
        emoji = "✅" if r['correct'] else "❌"
        print(f"  {emoji} {r['test']}: {r['expected']} → {r['actual']}")

    print()


if __name__ == '__main__':
    main()
