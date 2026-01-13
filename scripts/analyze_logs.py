#!/usr/bin/env python3
"""
EventStore Log Analyzer - Operational Observability Tool

Answers key operational questions:
1. Did the run succeed or fail?
2. Where exactly did it fail?
3. What patterns indicate problems?
4. How do I restart a failed load?

Usage:
    python scripts/analyze_logs.py                    # Analyze latest run
    python scripts/analyze_logs.py --run-id XYZ      # Analyze specific run
    python scripts/analyze_logs.py --all             # Summary of all runs today
    python scripts/analyze_logs.py --errors          # Show only errors
    python scripts/analyze_logs.py --restart         # Show restart commands for failures

Idempotency Model:
    DataWarp uses two levels of duplicate prevention:

    1. State tracking (state/state.json):
       - Records which publication/period combinations have been processed
       - Skip already-processed periods by default
       - Override with --force flag to reload

    2. Replace mode in database:
       - Data loading uses "mode: replace" which DELETEs existing rows
         for the same period before INSERTing new data
       - This makes reloads safe - no duplicate rows

    Restart Strategy:
       - If a run fails, use --restart to see restart commands
       - Commands include --force flag to bypass state tracking
       - Because of replace mode, re-running is always safe

    Example workflow for failed load:
       $ python scripts/analyze_logs.py --restart
       > python scripts/backfill.py --pub online_consultation --force

       $ python scripts/backfill.py --pub online_consultation --force
       # Re-processes the publication, replacing any partial data
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

LOGS_DIR = Path(__file__).parent.parent / "logs" / "events"


def load_log(log_path: Path) -> list:
    """Load JSONL log file."""
    events = []
    with open(log_path) as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    return events


def get_latest_log() -> Path:
    """Find the most recent log file."""
    today = datetime.now().strftime("%Y-%m-%d")
    today_dir = LOGS_DIR / today

    if not today_dir.exists():
        # Try yesterday
        from datetime import timedelta
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        today_dir = LOGS_DIR / yesterday

    if not today_dir.exists():
        print("No log directories found")
        sys.exit(1)

    logs = sorted(today_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not logs:
        print(f"No log files in {today_dir}")
        sys.exit(1)

    return logs[0]


def analyze_run(events: list) -> dict:
    """Analyze a run and return structured results."""
    result = {
        "run_id": None,
        "status": "UNKNOWN",
        "start_time": None,
        "end_time": None,
        "duration_sec": None,
        "publications": [],
        "stages": defaultdict(lambda: {"started": 0, "completed": 0, "failed": 0}),
        "errors": [],
        "warnings": [],
        "sources_loaded": 0,
        "rows_loaded": 0,
        "reference_matches": 0,
        "llm_calls": 0,
        "failure_point": None,
    }

    for event in events:
        event_type = event.get("event_type")

        # Extract run metadata
        if event_type == "run_started":
            result["run_id"] = event.get("run_id")
            result["start_time"] = event.get("timestamp")

        if event_type == "run_completed":
            result["end_time"] = event.get("timestamp")
            details = event.get("details", {})
            if details.get("failed", 0) > 0:
                result["status"] = "FAILED"
            elif details.get("processed", 0) > 0:
                result["status"] = "SUCCESS"
            else:
                result["status"] = "NO_WORK"

        # Track publications
        pub = event.get("publication")
        if pub and pub not in result["publications"]:
            result["publications"].append(pub)

        # Track stages
        stage = event.get("stage") or "unknown"
        if event_type == "stage_started":
            result["stages"][stage]["started"] += 1
        elif event_type == "stage_completed":
            result["stages"][stage]["completed"] += 1
        elif event_type == "stage_failed":
            result["stages"][stage]["failed"] += 1
            # Capture failure point
            if not result["failure_point"]:
                result["failure_point"] = {
                    "stage": stage,
                    "publication": event.get("publication"),
                    "period": event.get("period"),
                    "message": event.get("message"),
                    "error": event.get("details", {}).get("error") or event.get("error")
                }

        # Track errors
        if event_type == "error" or event.get("level") == "ERROR":
            result["errors"].append({
                "timestamp": event.get("timestamp"),
                "stage": stage,
                "publication": event.get("publication"),
                "period": event.get("period"),
                "message": event.get("message"),
                "error": event.get("details", {}).get("error") or event.get("error")
            })

        # Track warnings (real warnings, not misused ones)
        if event_type == "warning" and event.get("level") == "WARNING":
            result["warnings"].append({
                "stage": stage,
                "message": event.get("message")
            })

        # Track metrics
        if event_type == "reference_matched":
            details = event.get("details", {})
            result["reference_matches"] += details.get("matched", 0)

        if event_type == "llm_call":
            result["llm_calls"] += 1

        # Track load results from stage_completed messages
        if event_type == "stage_completed" and stage == "load":
            msg = event.get("message", "")
            if "rows" in msg:
                # Parse "Load completed for X: N rows in Yms"
                import re
                match = re.search(r"(\d+) rows", msg)
                if match:
                    result["rows_loaded"] += int(match.group(1))
                    result["sources_loaded"] += 1

    # Calculate duration
    if result["start_time"] and result["end_time"]:
        start = datetime.fromisoformat(result["start_time"])
        end = datetime.fromisoformat(result["end_time"])
        result["duration_sec"] = (end - start).total_seconds()

    # If no run_completed, mark as incomplete
    if not result["end_time"] and result["start_time"]:
        result["status"] = "INCOMPLETE"

    return result


def print_summary(result: dict):
    """Print human-readable summary."""
    status_icons = {
        "SUCCESS": "✅",
        "FAILED": "❌",
        "INCOMPLETE": "⚠️",
        "NO_WORK": "⏭️",
        "UNKNOWN": "❓"
    }

    icon = status_icons.get(result["status"], "❓")

    print(f"\n{'='*60}")
    print(f"{icon} RUN: {result['run_id']}")
    print(f"{'='*60}")

    print(f"\nStatus:      {result['status']}")
    print(f"Started:     {result['start_time']}")
    print(f"Ended:       {result['end_time'] or 'N/A'}")
    if result["duration_sec"]:
        print(f"Duration:    {result['duration_sec']:.1f}s")

    print(f"\nPublications: {', '.join(result['publications']) or 'None'}")
    print(f"Sources:      {result['sources_loaded']} loaded")
    print(f"Rows:         {result['rows_loaded']:,}")
    print(f"Ref Matches:  {result['reference_matches']} (LLM calls saved)")
    print(f"LLM Calls:    {result['llm_calls']}")

    # Stage summary
    print(f"\n--- Stage Summary ---")
    for stage, counts in sorted(result["stages"].items()):
        if counts["failed"] > 0:
            print(f"  {stage}: {counts['completed']}/{counts['started']} ❌ {counts['failed']} failed")
        else:
            print(f"  {stage}: {counts['completed']}/{counts['started']} ✓")

    # Warnings
    if result["warnings"]:
        print(f"\n--- Warnings ({len(result['warnings'])}) ---")
        for w in result["warnings"][:5]:
            print(f"  ⚠️  [{w['stage']}] {w['message'][:60]}")
        if len(result["warnings"]) > 5:
            print(f"  ... and {len(result['warnings'])-5} more")

    # Errors
    if result["errors"]:
        print(f"\n--- Errors ({len(result['errors'])}) ---")
        for e in result["errors"]:
            print(f"  ❌ [{e['stage']}] {e['publication']}/{e['period']}")
            print(f"     {e['message'][:70]}")
            if e.get("error"):
                print(f"     Error: {str(e['error'])[:60]}")

    # Failure point and restart guidance
    if result["failure_point"]:
        print(f"\n--- Failure Point ---")
        fp = result["failure_point"]
        print(f"  Stage:       {fp['stage']}")
        print(f"  Publication: {fp['publication']}")
        print(f"  Period:      {fp['period']}")
        print(f"  Error:       {fp['error'] or fp['message']}")

        print(f"\n--- Restart Command ---")
        print(f"  python scripts/backfill.py --pub {fp['publication']} --force")

    print()


def print_errors_only(events: list):
    """Print only errors in detail."""
    errors = [e for e in events if e.get("event_type") == "error" or e.get("level") == "ERROR"]

    if not errors:
        print("✅ No errors found in this log")
        return

    print(f"\n❌ Found {len(errors)} errors:\n")

    for i, e in enumerate(errors, 1):
        print(f"--- Error {i} ---")
        print(f"Time:        {e.get('timestamp')}")
        print(f"Stage:       {e.get('stage')}")
        print(f"Publication: {e.get('publication')}")
        print(f"Period:      {e.get('period')}")
        print(f"Message:     {e.get('message')}")

        details = e.get("details", {})
        if details.get("error"):
            print(f"Error:       {details['error']}")
        if details.get("context"):
            print(f"Context:     {json.dumps(details['context'], indent=2)}")
        print()


def print_restart_commands(result: dict):
    """Print commands to restart failed loads."""
    if result["status"] == "SUCCESS":
        print("✅ Run completed successfully - no restart needed")
        return

    print("\n--- Restart Commands ---\n")

    # Get unique failed publications
    failed_pubs = set()
    for e in result["errors"]:
        if e.get("publication"):
            failed_pubs.add(e["publication"])

    if result["failure_point"]:
        fp = result["failure_point"]
        if fp.get("publication"):
            failed_pubs.add(fp["publication"])

    if failed_pubs:
        print("To retry failed publications:")
        for pub in sorted(failed_pubs):
            print(f"  python scripts/backfill.py --pub {pub} --force")
    else:
        print("To retry entire run:")
        print(f"  python scripts/backfill.py --force")

    print("\nNote: --force bypasses 'already processed' checks and reloads data")
    print("      Data loading is idempotent (replace mode deletes by period first)")


def summarize_all_runs():
    """Summarize all runs from today."""
    today = datetime.now().strftime("%Y-%m-%d")
    today_dir = LOGS_DIR / today

    if not today_dir.exists():
        print(f"No logs for today ({today})")
        return

    logs = sorted(today_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)

    print(f"\n{'='*70}")
    print(f"Run Summary for {today}")
    print(f"{'='*70}\n")

    for log_path in logs:
        events = load_log(log_path)
        result = analyze_run(events)

        status_icons = {"SUCCESS": "✅", "FAILED": "❌", "INCOMPLETE": "⚠️", "NO_WORK": "⏭️"}
        icon = status_icons.get(result["status"], "❓")

        duration = f"{result['duration_sec']:.0f}s" if result["duration_sec"] else "N/A"
        pubs = ", ".join(result["publications"][:2]) + ("..." if len(result["publications"]) > 2 else "")
        run_id = result['run_id'] or log_path.stem

        print(f"{icon} {run_id:40} {duration:>6}  {result['sources_loaded']:>3} sources  {result['rows_loaded']:>10,} rows  {pubs}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Analyze EventStore logs for operational insights",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/analyze_logs.py                  # Analyze latest run
  python scripts/analyze_logs.py --all            # Summary of all runs today
  python scripts/analyze_logs.py --errors         # Show only errors
  python scripts/analyze_logs.py --restart        # Show restart commands
  python scripts/analyze_logs.py --run-id backfill_20260113_104715
        """
    )
    parser.add_argument("--run-id", help="Specific run ID to analyze")
    parser.add_argument("--all", action="store_true", help="Summarize all runs today")
    parser.add_argument("--errors", action="store_true", help="Show only errors")
    parser.add_argument("--restart", action="store_true", help="Show restart commands for failures")
    parser.add_argument("--log", help="Path to specific log file")

    args = parser.parse_args()

    if args.all:
        summarize_all_runs()
        return

    # Find log file
    if args.log:
        log_path = Path(args.log)
    elif args.run_id:
        # Search for run_id
        found = None
        for date_dir in sorted(LOGS_DIR.iterdir(), reverse=True):
            if date_dir.is_dir():
                for log_file in date_dir.glob(f"*{args.run_id}*.jsonl"):
                    found = log_file
                    break
            if found:
                break
        if not found:
            print(f"Run ID not found: {args.run_id}")
            sys.exit(1)
        log_path = found
    else:
        log_path = get_latest_log()

    print(f"Analyzing: {log_path}")

    events = load_log(log_path)

    if args.errors:
        print_errors_only(events)
        return

    result = analyze_run(events)

    if args.restart:
        print_restart_commands(result)
    else:
        print_summary(result)


if __name__ == "__main__":
    main()
