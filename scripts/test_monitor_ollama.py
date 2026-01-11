#!/usr/bin/env python3
"""
Test monitoring with local Ollama (Qwen)

Compares local LLM performance vs Gemini.
Shows speed, quality, and cost (FREE).
"""

import os
import sys
import json
import time
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
load_dotenv()


def analyze_event_with_ollama(event, model="qwen3:8b"):
    """Use Ollama (local LLM) to analyze a load event"""

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

    ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')

    start_time = time.time()

    response = requests.post(
        f'{ollama_url}/api/generate',
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",  # Force JSON output
            "options": {
                "temperature": 0.1
            }
        }
    )

    elapsed = time.time() - start_time

    if response.status_code != 200:
        return {
            "status": "error",
            "action": "investigate",
            "reason": f"Ollama request failed: {response.status_code}",
            "confidence": 0.0,
            "elapsed_time": elapsed
        }

    result = response.json()

    # Parse JSON response
    try:
        analysis = json.loads(result['response'])
        analysis['elapsed_time'] = elapsed
        analysis['model'] = model

        # Approximate token count (rough estimate)
        input_tokens = len(prompt.split())
        output_tokens = len(result['response'].split())
        analysis['tokens'] = {
            'input': input_tokens,
            'output': output_tokens,
            'total': input_tokens + output_tokens
        }

        return analysis

    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {e}")
        print(f"Raw response: {result.get('response', 'No response')[:200]}")
        return {
            "status": "error",
            "action": "investigate",
            "reason": f"Failed to parse: {str(e)}",
            "confidence": 0.0,
            "elapsed_time": elapsed
        }


def main():
    print("="*70)
    print("DataWarp Monitoring Test - Local Ollama (Qwen)")
    print("="*70)
    print()

    # Same test cases as Gemini
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
    total_time = 0

    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*70}")
        print(f"Test Case {i}/{len(test_cases)}: {test['name']}")
        print(f"{'='*70}")
        print(f"Source: {test['event']['source_code']}")
        print(f"Rows: {test['event']['rows_loaded']:,}")
        print(f"Error: {test['event']['error']}")
        print(f"Expected: {test['expected'].upper()}")
        print()

        print("Analyzing with Qwen3:8b...")
        analysis = analyze_event_with_ollama(test['event'])

        print(f"\n✓ Qwen Analysis:")
        print(f"  Status: {analysis['status'].upper()}")
        print(f"  Action: {analysis['action']}")
        print(f"  Reason: {analysis['reason']}")
        print(f"  Confidence: {analysis.get('confidence', 'N/A')}")
        print(f"  Time: {analysis['elapsed_time']:.2f}s")

        # Check if detected correctly
        correct = analysis['status'] == test['expected']
        emoji = "✅" if correct else "❌"
        print(f"\n  Result: {emoji} {'CORRECT' if correct else 'INCORRECT'}")

        total_time += analysis['elapsed_time']

        results.append({
            'test': test['name'],
            'expected': test['expected'],
            'actual': analysis['status'],
            'correct': correct,
            'time': analysis['elapsed_time'],
            'analysis': analysis
        })

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY - Local Ollama (Qwen3:8b)")
    print(f"{'='*70}")

    correct_count = sum(1 for r in results if r['correct'])
    accuracy = (correct_count / len(results)) * 100

    print(f"Accuracy: {correct_count}/{len(results)} ({accuracy:.0f}%)")
    print(f"Total Time: {total_time:.2f}s")
    print(f"Avg Time/Event: {total_time/len(results):.2f}s")
    print(f"Cost: $0.00 (FREE - local)")

    print("\nDetailed Results:")
    for r in results:
        emoji = "✅" if r['correct'] else "❌"
        print(f"  {emoji} {r['test']}: {r['expected']} → {r['actual']} ({r['time']:.2f}s)")

    print()


if __name__ == '__main__':
    main()
