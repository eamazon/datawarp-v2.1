"""Simple observability module for DataWarp v2.1."""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ObservabilityLogger:
    """Simple logger for tracking batch load operations."""

    def __init__(self, manifest_name: str):
        """Initialize observability logger."""
        self.manifest_name = manifest_name
        self.events = []

    def log_event(self, event_type: str, details: Dict[str, Any]):
        """Log an event."""
        self.events.append({
            'type': event_type,
            'details': details
        })
        logger.info(f"{event_type}: {details}")


def init(manifest_name: str, db_conn=None) -> ObservabilityLogger:
    """Initialize observability logger for a batch."""
    return ObservabilityLogger(manifest_name)


def print_summary(obs_logger: ObservabilityLogger, stats: Dict[str, Any]):
    """Print summary of batch operations."""
    logger.info(f"Batch {obs_logger.manifest_name} complete")
    logger.info(f"Stats: {stats}")
