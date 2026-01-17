"""
CLI display module for clean progress-based output.

Design: Live progress bar + clean results + summary
"""

import sys
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class SourceResult:
    """Result from loading a single source."""
    name: str
    rows: int
    columns_added: int = 0
    status: str = "success"  # success, warning, error
    warning: Optional[str] = None
    duration_ms: int = 0


@dataclass
class PeriodResult:
    """Result from processing a single period."""
    publication: str
    period: str
    stage_timings: dict = field(default_factory=dict)
    sources: List[SourceResult] = field(default_factory=list)
    status: str = "success"  # success, failed, partial
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    @property
    def total_duration(self) -> float:
        """Total duration across all stages."""
        return sum(self.stage_timings.values())

    @property
    def total_rows(self) -> int:
        """Total rows across all successfully loaded sources."""
        return sum(s.rows for s in self.sources if s.status == 'success')

    @property
    def total_columns(self) -> int:
        """Total new columns across all successfully loaded sources."""
        return sum(s.columns_added for s in self.sources if s.status == 'success')


class ProgressDisplay:
    """
    Progress bar style display.

    Shows:
    - Header
    - Live progress line (updates in place)
    - One-line results per period
    - Final summary
    """

    def __init__(self, publication_name: str):
        self.publication_name = publication_name
        self.periods: List[PeriodResult] = []
        self.current_period = None
        self.current_stage = None
        self.current_progress = 0
        self.total_stages = 4  # manifest, enrich, load, export

    def print_header(self):
        """Print publication header."""
        print()
        print(self.publication_name)
        print("━" * 80)
        print()

    def start_period(self, period: str):
        """Start processing a new period."""
        self.current_period = period
        self.current_stage = None
        self.current_progress = 0

    def update_progress(self, stage: str, progress: int = None):
        """Update the live progress line."""
        self.current_stage = stage
        if progress is not None:
            self.current_progress = progress
        else:
            # Auto-increment based on stage
            stage_map = {'manifest': 1, 'enrich': 2, 'load': 3, 'export': 4}
            self.current_progress = stage_map.get(stage, 0)

        # Calculate progress percentage
        pct = (self.current_progress / self.total_stages) * 100
        filled = int(pct / 5)  # 20 blocks for 100%
        bar = "█" * filled + "░" * (20 - filled)

        # Format period name (e.g., "may25" -> "May 2025")
        period_display = self._format_period(self.current_period)

        # Print with carriage return to overwrite
        msg = f"\r[{bar}] {period_display} | {stage}..."
        sys.stdout.write(msg)
        sys.stdout.flush()

    def complete_period(self, result: PeriodResult):
        """Print completion line for a period."""
        # Clear the progress line
        sys.stdout.write("\r" + " " * 80 + "\r")

        # Format period name
        period_display = self._format_period(result.period)

        # Status symbol
        if result.status == "failed":
            symbol = "✗"
        elif result.warnings:
            symbol = "✓"
        else:
            symbol = "✓"

        # Build result line (only count successfully loaded sources)
        duration = f"{result.total_duration:.1f}s"
        loaded_sources = [s for s in result.sources if s.status == 'success']
        sources_count = len(loaded_sources)
        rows_count = f"{result.total_rows:,}"

        # Warning indicator
        warning_text = ""
        if result.warnings:
            warning_text = f"  ({len(result.warnings)} warning{'s' if len(result.warnings) > 1 else ''})"

        # Print result
        if result.status == "failed":
            print(f"{symbol} {period_display:10} {duration:>6}  Failed: {result.error}")
        else:
            # Show columns added per period if any
            cols_text = ""
            if result.total_columns > 0:
                cols_text = f"  +{result.total_columns} cols"
            print(f"{symbol} {period_display:10} {duration:>6}  {sources_count:>2} sources  {rows_count:>8} rows{cols_text}{warning_text}")

        # Store result
        self.periods.append(result)

    def print_summary(self):
        """Print final summary."""
        print()
        print("━" * 80)

        # Calculate totals (only count successfully loaded sources)
        total_periods = len(self.periods)
        successful = len([p for p in self.periods if p.status == "success"])
        failed = len([p for p in self.periods if p.status == "failed"])
        total_sources = sum(len([s for s in p.sources if s.status == 'success']) for p in self.periods)
        total_rows = sum(p.total_rows for p in self.periods)
        total_columns = sum(p.total_columns for p in self.periods)

        # Summary line
        status = "COMPLETE" if failed == 0 else f"{successful}/{total_periods} completed"

        # Build summary parts
        parts = [f"{total_sources} sources", f"{total_rows:,} rows"]
        if total_columns > 0:
            parts.append(f"{total_columns} new columns")

        print(f"{status}: {' | '.join(parts)}")

        # Collect all warnings
        all_warnings = []
        for period in self.periods:
            for warning in period.warnings:
                all_warnings.append((period.period, warning))

        # Show warnings if any
        if all_warnings:
            print()
            print(f"Warnings ({len(all_warnings)}):")
            for period, warning in all_warnings[:5]:  # Show first 5
                period_display = self._format_period(period)
                print(f"  • {period_display}: {warning}")
            if len(all_warnings) > 5:
                print(f"  ... and {len(all_warnings) - 5} more")

        print("━" * 80)

    def _format_period(self, period: str) -> str:
        """Format period code to readable form."""
        from datawarp.utils.period import format_period_display
        return format_period_display(period)
