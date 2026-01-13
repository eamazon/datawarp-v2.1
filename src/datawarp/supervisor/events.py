"""
Event system for pipeline observability and autonomous supervision.

Design principles:
- Structured events (dataclasses, not strings)
- Multi-output (console, file log, JSONL)
- Thread-safe for parallel operations
- Zero dependencies on pipeline code
"""

import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
from enum import Enum


class EventLevel(Enum):
    """Event severity levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class EventType(Enum):
    """Event types for pipeline stages."""
    # Run-level
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"

    # Period-level
    PERIOD_STARTED = "period_started"
    PERIOD_COMPLETED = "period_completed"
    PERIOD_FAILED = "period_failed"

    # Stage-level
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    STAGE_FAILED = "stage_failed"

    # Detail-level
    SHEET_CLASSIFIED = "sheet_classified"
    SOURCE_DETECTED = "source_detected"
    REFERENCE_MATCHED = "reference_matched"
    LLM_CALL = "llm_call"

    # Errors
    ERROR = "error"
    WARNING = "warning"


@dataclass
class Event:
    """Base event structure."""
    event_type: EventType
    timestamp: str
    run_id: str
    level: EventLevel = EventLevel.INFO

    # Context
    publication: Optional[str] = None
    period: Optional[str] = None
    stage: Optional[str] = None  # manifest, enrich, load, export

    # Event-specific data
    message: Optional[str] = None
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        d = asdict(self)
        d['event_type'] = self.event_type.value
        d['level'] = self.level.value
        return d


class EventStore:
    """
    Multi-output event store.

    Emits events to:
    - Console (human-readable, summary level)
    - File log (detailed, structured)
    - JSONL file (complete, queryable)
    """

    def __init__(self, run_id: str, logs_dir: Path = None):
        """
        Initialize event store.

        Args:
            run_id: Unique run identifier (e.g., "backfill_20260113_120000")
            logs_dir: Directory for logs (default: PROJECT_ROOT/logs)
        """
        self.run_id = run_id

        # Setup logs directory
        if logs_dir is None:
            project_root = Path(__file__).parent.parent.parent.parent
            logs_dir = project_root / "logs"

        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(exist_ok=True)

        # Setup file log
        log_file = self.logs_dir / f"{run_id}.log"
        self.file_logger = logging.getLogger(f"eventstore.{run_id}")
        self.file_logger.setLevel(logging.DEBUG)
        self.file_logger.handlers.clear()

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )
        self.file_logger.addHandler(file_handler)

        # Setup console logger
        self.console_logger = logging.getLogger(f"console.{run_id}")
        self.console_logger.setLevel(logging.INFO)
        self.console_logger.handlers.clear()
        self.console_logger.propagate = False

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(
            logging.Formatter('%(levelname)s: %(message)s')
        )
        self.console_logger.addHandler(console_handler)

        # Setup JSONL file
        events_dir = self.logs_dir / "events" / datetime.now().strftime("%Y-%m-%d")
        events_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_file = events_dir / f"{run_id}.jsonl"

        # Open JSONL file for appending
        self._jsonl_handle = open(self.jsonl_file, 'a')

    def emit(self, event: Event):
        """Emit event to all outputs."""
        # Ensure run_id matches
        event.run_id = self.run_id

        # Console output (summary level)
        self._emit_console(event)

        # File log (detailed)
        self._emit_file_log(event)

        # JSONL (everything)
        self._emit_jsonl(event)

    def _emit_console(self, event: Event):
        """Emit to console (summary level only)."""
        # Only show INFO+ level events
        if event.level == EventLevel.DEBUG:
            return

        # Format message
        if event.event_type == EventType.PERIOD_STARTED:
            msg = f"Processing: {event.publication}/{event.period}"
        elif event.event_type == EventType.STAGE_STARTED:
            msg = f"  Step: {event.stage}"
        elif event.event_type == EventType.STAGE_COMPLETED:
            msg = f"  [OK] {event.stage} completed"
        elif event.event_type == EventType.PERIOD_COMPLETED:
            msg = f"  [SUCCESS] {event.publication}/{event.period}"
        elif event.event_type == EventType.ERROR:
            msg = f"  [ERROR] {event.message}"
        elif event.event_type == EventType.WARNING:
            msg = f"  [WARNING] {event.message}"
        else:
            msg = event.message or f"{event.event_type.value}"

        # Emit to console
        if event.level == EventLevel.ERROR:
            self.console_logger.error(msg)
        elif event.level == EventLevel.WARNING:
            self.console_logger.warning(msg)
        else:
            self.console_logger.info(msg)

    def _emit_file_log(self, event: Event):
        """Emit to file log (detailed)."""
        # Format context
        context_parts = []
        if event.publication:
            context_parts.append(f"pub={event.publication}")
        if event.period:
            context_parts.append(f"period={event.period}")
        if event.stage:
            context_parts.append(f"stage={event.stage}")

        context = f"[{' '.join(context_parts)}]" if context_parts else ""

        # Format message
        msg = f"{event.event_type.value} {context}"
        if event.message:
            msg += f" - {event.message}"
        if event.details:
            # Add selected details (not full dict, too verbose)
            if 'error' in event.details:
                msg += f" (error={event.details['error'][:100]})"

        # Emit to file log
        if event.level == EventLevel.ERROR:
            self.file_logger.error(msg)
        elif event.level == EventLevel.WARNING:
            self.file_logger.warning(msg)
        elif event.level == EventLevel.DEBUG:
            self.file_logger.debug(msg)
        else:
            self.file_logger.info(msg)

    def _emit_jsonl(self, event: Event):
        """Emit to JSONL file (everything)."""
        self._jsonl_handle.write(json.dumps(event.to_dict()) + '\n')
        self._jsonl_handle.flush()

    def close(self):
        """Close file handles."""
        if hasattr(self, '_jsonl_handle'):
            self._jsonl_handle.close()

    def __enter__(self):
        """Context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close on context exit."""
        self.close()


def create_event(
    event_type: EventType,
    run_id: str,
    message: str = None,
    level: EventLevel = EventLevel.INFO,
    publication: str = None,
    period: str = None,
    stage: str = None,
    **details
) -> Event:
    """Helper to create events with consistent timestamps."""
    return Event(
        event_type=event_type,
        timestamp=datetime.now().isoformat(),
        run_id=run_id,
        level=level,
        publication=publication,
        period=period,
        stage=stage,
        message=message,
        details=details
    )
