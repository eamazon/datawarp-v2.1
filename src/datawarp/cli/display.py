"""
CLI display module for balanced, user-friendly output.

Design principles:
- Grouped by period (clear hierarchy)
- Tree structure for stages
- Collapsed long lists
- Inline warnings
- Clean summary
"""

from datetime import datetime
from typing import List, Dict, Optional
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
    stage_timings: Dict[str, float] = field(default_factory=dict)  # stage -> duration_s
    sources: List[SourceResult] = field(default_factory=list)
    status: str = "success"  # success, failed, partial
    error: Optional[str] = None
    
    @property
    def total_duration(self) -> float:
        """Total duration across all stages."""
        return sum(self.stage_timings.values())
    
    @property
    def total_rows(self) -> int:
        """Total rows across all sources."""
        return sum(s.rows for s in self.sources)
    
    @property
    def total_columns(self) -> int:
        """Total new columns across all sources."""
        return sum(s.columns_added for s in self.sources)
    
    @property
    def warning_count(self) -> int:
        """Count sources with warnings."""
        return sum(1 for s in self.sources if s.status == "warning")


class BalancedDisplay:
    """
    Balanced display mode - tree structure, grouped by period.
    
    Example output:
        📅 May 2025
           ├─ Fetching manifest...
           ├─ Enriching (LLM: gemini-2.5-flash-lite)... 0.8s
           └─ Loading to database...
              ├─ tbl_adhd                    1,304 rows  ✓
              ├─ tbl_mhsds_historic          5,609 rows  ✓
              └─ Completed in 2.3s
    """
    
    MAX_SOURCES_SHOWN = 5  # Show first N sources, then collapse
    
    def __init__(self, publication_name: str):
        self.publication_name = publication_name
        self.periods: List[PeriodResult] = []
    
    def print_header(self):
        """Print publication header."""
        header = f" DataWarp Backfill - {self.publication_name} "
        width = 80
        print()
        print("╔" + "═" * (width - 2) + "╗")
        print("║" + header.center(width - 2) + "║")
        print("╚" + "═" * (width - 2) + "╝")
        print()
    
    def print_period_start(self, period: str):
        """Print period header."""
        # Format period nicely (e.g., "may25" -> "May 2025")
        month_map = {
            'jan': 'January', 'feb': 'February', 'mar': 'March', 'apr': 'April',
            'may': 'May', 'jun': 'June', 'jul': 'July', 'aug': 'August',
            'sep': 'September', 'oct': 'October', 'nov': 'November', 'dec': 'December'
        }
        
        month_code = period[:3].lower()
        year = "20" + period[3:]
        month_name = month_map.get(month_code, period[:3].upper())
        
        print(f"📅 {month_name} {year}")
    
    def print_stage(self, stage_name: str, is_last: bool = False):
        """Print stage name."""
        branch = "└─" if is_last else "├─"
        print(f"   {branch} {stage_name}...", end="", flush=True)
    
    def print_stage_complete(self, duration_s: float):
        """Complete a stage line with duration."""
        print(f" {duration_s:.1f}s")
    
    def print_sources(self, sources: List[SourceResult]):
        """Print source loading results."""
        print("   └─ Loading to database...")
        
        # Show first N sources
        sources_to_show = sources[:self.MAX_SOURCES_SHOWN]
        remaining = len(sources) - len(sources_to_show)
        
        for i, source in enumerate(sources_to_show):
            is_last = (i == len(sources_to_show) - 1) and remaining == 0
            branch = "└─" if is_last else "├─"
            
            # Format source name (truncate if needed)
            name = source.name[:28].ljust(28)
            rows = f"{source.rows:>6,} rows"
            
            # Status symbol
            if source.status == "error":
                status = "✗"
            elif source.status == "warning":
                status = "⚠️"
            else:
                status = "✓"
            
            # Column info
            cols_info = f"+{source.columns_added} cols" if source.columns_added > 0 else ""
            
            print(f"      {branch} {name} {rows:>12}  {status} {cols_info}")
            
            # Print warning if present
            if source.warning:
                warning_branch = "│" if not is_last else " "
                print(f"      {warning_branch}    ⚠️  {source.warning}")
        
        # Show collapsed message
        if remaining > 0:
            print(f"      └─ [...{remaining} more sources]")
    
    def print_period_complete(self, period_result: PeriodResult):
        """Print period completion."""
        duration = period_result.total_duration
        print(f"      └─ Completed in {duration:.1f}s")
        print()
    
    def print_summary(self):
        """Print final summary."""
        total_processed = len([p for p in self.periods if p.status == "success"])
        total_failed = len([p for p in self.periods if p.status == "failed"])
        total_sources = sum(len(p.sources) for p in self.periods)
        total_rows = sum(p.total_rows for p in self.periods)
        total_columns = sum(p.total_columns for p in self.periods)
        total_warnings = sum(p.warning_count for p in self.periods)
        
        print("─" * 80)
        status_line = f"✓ {total_processed} periods processed"
        if total_failed > 0:
            status_line += f" | {total_failed} failed"
        if total_warnings > 0:
            status_line += f" ({total_warnings} warnings)"
        
        stats_line = f"  {total_sources} sources loaded | {total_rows:,} rows | {total_columns} columns added"
        
        print(status_line)
        print(stats_line)
        print("─" * 80)
