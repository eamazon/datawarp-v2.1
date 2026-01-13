#!/usr/bin/env python3
"""
Test monitoring with Claude API

Compare Claude vs Gemini for anomaly detection.
Requires ANTHROPIC_API_KEY in .env
"""

import os
import sys
import json
from dotenv import load_dotenv
import anthropic

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
load_dotenv()


def analyze_with_claude(event):
    """Use Claude to analyze a load event"""

    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        return {
            "status": "error",
            "action": "investigate",
            "reason": "ANTHROPIC_API_KEY not found in .env",
            "confidence": 0.0
        }

    client = anthropic.Anthropic(api_key=api_key)

    # Count columns if present
    columns_added = event.get('columns_added', 'None')
    if columns_added != 'None' and isinstance(columns_added, str):
        # Try to parse the list and count
        try:
            import ast
            cols = ast.literal_eval(columns_added)
            column_count = len(cols)
        except:
            column_count = "Unknown"
    else:
        column_count = 0

    prompt = f"""You are a DataWarp monitoring agent analyzing NHS data load events.

EVENT DATA:
- Source: {event['source_code']}
- Rows Loaded: {event['rows_loaded']:,}
- Columns Added: {column_count} columns ({columns_added})
- Load Mode: {event['load_mode']}
- Error Message: {event.get('error', 'None')}
- Previous Load: {event.get('previous_rows', 'Unknown')} rows

HISTORICAL CONTEXT:
- Typical Range: {event.get('typical_range', 'Unknown')}
- Last 5 Loads: {event.get('recent_history', 'No data')}

DETECTION RULES:

1. CRITICAL if any:
   - 0 rows loaded when previous load had >100 rows (extraction failure)
   - Rows loaded <10% of typical range (indicates broken pipeline)
   - Error contains "ParseError", "ExtractionError", "SchemaError"

2. WARNING if any:
   - Error contains "Timeout", "Connection", "Network" (transient, should retry)
   - Rows loaded 10-50% of typical range (suspicious)
   - More than 3 new columns added (schema drift - investigate)

3. NORMAL if:
   - Rows within typical range ±20%
   - No errors, 0-2 columns added

OUTPUT (JSON only):
{{
  "status": "normal|warning|critical",
  "action": "none|retry|alert|investigate",
  "reason": "Brief explanation",
  "confidence": 0.0-1.0,
  "rule_triggered": "Rule number (1, 2, or 3)"
}}
"""

    try:
        message = client.messages.create(
            model="claude-3-5-haiku-20241022",  # Cheapest model
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # Parse JSON response
        text = message.content[0].text.strip()

        # Handle markdown code blocks
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0].strip()
        elif '```' in text:
            text = text.split('```')[1].split('```')[0].strip()

        # Handle JSON followed by extra text (Claude often adds explanation)
        # Find the first complete JSON object
        try:
            # Try to find JSON object boundaries
            start = text.find('{')
            if start == -1:
                raise ValueError("No JSON object found")

            # Find matching closing brace
            brace_count = 0
            end = start
            for i in range(start, len(text)):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end = i + 1
                        break

            json_text = text[start:end]
            analysis = json.loads(json_text)
        except (ValueError, json.JSONDecodeError):
            # Fallback: try parsing entire text
            analysis = json.loads(text)

        # Add token usage
        analysis['tokens'] = {
            'input': message.usage.input_tokens,
            'output': message.usage.output_tokens,
            'total': message.usage.input_tokens + message.usage.output_tokens
        }

        return analysis

    except Exception as e:
        return {
            "status": "error",
            "action": "investigate",
            "reason": f"Claude API error: {str(e)}",
            "confidence": 0.0
        }


def main():
    print("="*70)
    print("DataWarp Monitoring Test - Claude Haiku 3.5 (Economical)")
    print("="*70)
    print()

    # Check for API key
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("❌ ERROR: ANTHROPIC_API_KEY not found in .env")
        print()
        print("To test Claude:")
        print("1. Get free API key: https://console.anthropic.com ($5 credit)")
        print("2. Add to .env: ANTHROPIC_API_KEY=sk-ant-...")
        print("3. Run this script again")
        print()
        return

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
            "expected": "warning"
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
            "expected": "critical"
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

        analysis = analyze_with_claude(test['event'])

        if analysis['status'] == 'error':
            print(f"❌ Error: {analysis['reason']}")
            continue

        print(f"✓ Claude Analysis:")
        print(f"  Status: {analysis['status'].upper()}")
        print(f"  Action: {analysis['action']}")
        print(f"  Reason: {analysis['reason']}")
        print(f"  Rule: {analysis.get('rule_triggered', 'N/A')}")

        if 'tokens' in analysis:
            tokens = analysis['tokens']
            print(f"  Tokens: {tokens['total']} (in: {tokens['input']}, out: {tokens['output']})")
            total_tokens += tokens['total']

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
    print("SUMMARY - Claude Haiku 3.5")
    print(f"{'='*70}")

    correct_count = sum(1 for r in results if r['correct'])
    accuracy = (correct_count / len(results)) * 100

    print(f"Accuracy: {correct_count}/{len(results)} ({accuracy:.0f}%)")
    print(f"Total Tokens: {total_tokens:,}")

    # Claude Haiku pricing: $0.25/million input, $1.25/million output (roughly 50/50 = $0.75/million avg)
    cost = (total_tokens / 1_000_000) * 0.75
    print(f"Total Cost: ${cost:.6f}")
    print(f"Cost per Event: ${cost/len(results):.6f}")

    # Projections
    daily_events = 50
    monthly_cost = (cost / len(results)) * daily_events * 30

    print(f"\nProjections (50 events/day):")
    print(f"  Monthly Cost: ${monthly_cost:.2f}")
    print(f"  Yearly Cost: ${monthly_cost * 12:.2f}")

    print("\nComparison:")
    print("  Gemini:  60% accuracy, $0.09/month")
    print(f"  Claude:  {accuracy:.0f}% accuracy, ${monthly_cost:.2f}/month")

    print("\nDetailed Results:")
    for r in results:
        emoji = "✅" if r['correct'] else "❌"
        print(f"  {emoji} {r['test']}")

    print()


if __name__ == '__main__':
    main()
