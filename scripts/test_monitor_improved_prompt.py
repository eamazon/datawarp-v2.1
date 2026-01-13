#!/usr/bin/env python3
"""
Test monitoring with improved prompt engineering

Tests whether better prompts improve Gemini's accuracy.
"""

import os
import sys
import json
from dotenv import load_dotenv
import google.generativeai as genai

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
load_dotenv()


def analyze_with_improved_prompt(event):
    """Use Gemini with improved, more specific prompt"""
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel(os.getenv('LLM_MODEL', 'gemini-2.0-flash-exp'))

    # IMPROVED PROMPT with explicit rules
    prompt = f"""You are a DataWarp monitoring agent analyzing NHS data load events.

EVENT DATA:
- Source: {event['source_code']}
- Rows Loaded: {event['rows_loaded']:,}
- Columns Added: {event.get('columns_added', 'None')}
- Load Mode: {event['load_mode']}
- Error Message: {event.get('error', 'None')}
- Previous Load: {event.get('previous_rows', 'Unknown')} rows

HISTORICAL CONTEXT:
- Typical Range: {event.get('typical_range', 'Unknown')}
- Last 5 Loads: {event.get('recent_history', 'No data')}

DETECTION RULES (apply in order):

1. CRITICAL if any:
   - 0 rows loaded when previous load had >100 rows
   - Rows loaded <10% of typical range (indicates extraction failure)
   - Error message contains "ParseError", "ExtractionError", or "SchemaError"

2. WARNING if any:
   - Error message contains "Timeout", "Connection", or "Network" (transient - retry)
   - Rows loaded 10-50% of typical range (suspicious but not critical)
   - More than 3 new columns added in a single load (schema drift)

3. NORMAL if:
   - Rows loaded within typical range ±20%
   - No errors
   - 0-2 columns added (normal evolution)

OUTPUT FORMAT (JSON only):
{{
  "status": "normal|warning|critical",
  "action": "none|retry|alert|investigate",
  "reason": "Brief explanation citing which rule triggered",
  "confidence": 0.0-1.0,
  "rule_triggered": "Rule number that matched (1, 2, or 3)"
}}
"""

    response = model.generate_content(prompt)

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
            "reason": f"Parse error: {str(e)}",
            "confidence": 0.0
        }


def main():
    print("="*70)
    print("DataWarp Monitoring Test - Improved Prompt Engineering")
    print("="*70)
    print()

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
            "name": "Connection Timeout (Warning/Retry)",
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
            "expected": "warning"  # Should retry transient errors
        },
        {
            "name": "Suspicious Low Row Count (Critical)",
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
            "expected": "critical"  # <10% of typical = extraction failure
        },
        {
            "name": "Large Schema Drift (Warning)",
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
            "expected": "warning"  # 5 columns = schema drift
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

        analysis = analyze_with_improved_prompt(test['event'])

        print(f"✓ Gemini (Improved Prompt):")
        print(f"  Status: {analysis['status'].upper()}")
        print(f"  Action: {analysis['action']}")
        print(f"  Reason: {analysis['reason']}")
        print(f"  Rule Triggered: {analysis.get('rule_triggered', 'N/A')}")

        if 'tokens' in analysis:
            total_tokens += analysis['tokens']['total']

        correct = analysis['status'] == test['expected']
        emoji = "✅" if correct else "❌"
        print(f"\n  Result: {emoji} Expected {test['expected'].upper()}, got {analysis['status'].upper()}")

        results.append({
            'test': test['name'],
            'expected': test['expected'],
            'actual': analysis['status'],
            'correct': correct
        })

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY - Improved Prompt")
    print(f"{'='*70}")

    correct_count = sum(1 for r in results if r['correct'])
    accuracy = (correct_count / len(results)) * 100

    print(f"Accuracy: {correct_count}/{len(results)} ({accuracy:.0f}%)")
    print(f"Total Tokens: {total_tokens:,}")

    cost = (total_tokens / 1_000_000) * 0.1875
    print(f"Total Cost: ${cost:.6f}")

    print("\nImprovement Analysis:")
    print("Original Prompt: 60% accuracy (3/5)")
    print(f"Improved Prompt: {accuracy:.0f}% accuracy ({correct_count}/{len(results)})")

    if accuracy > 60:
        print("\n✅ Improved prompt WORKS BETTER!")
    elif accuracy == 60:
        print("\n➡️  Similar accuracy - may need different approach")
    else:
        print("\n❌ Prompt engineering didn't help")

    print("\nDetailed Results:")
    for r in results:
        emoji = "✅" if r['correct'] else "❌"
        print(f"  {emoji} {r['test']}")

    print()


if __name__ == '__main__':
    main()
