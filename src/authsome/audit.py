"""Audit logging for Authsome operations."""

import json
from pathlib import Path
from typing import Any

from loguru import logger

from authsome.utils import utc_now


class AuditLogger:
    """Append-only structured audit logger."""

    def __init__(self, filepath: Path, enabled: bool = True) -> None:
        self.filepath = filepath
        self.enabled = enabled
        if not self.enabled:
            logger.warning("Audit logging is disabled.")

    def log(self, event_type: str, **kwargs: Any) -> None:
        """Write an event to the audit log."""
        if not self.enabled:
            return

        # Ensure directory exists
        if not self.filepath.parent.exists():
            try:
                self.filepath.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error("Failed to create audit log directory {}: {}", self.filepath.parent, e)
                return

        # Filter out None values to keep the log clean
        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}

        entry = {
            "timestamp": utc_now().isoformat(),
            "event": event_type,
            **filtered_kwargs,
        }

        try:
            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error("Failed to write to audit log at {}: {}", self.filepath, e)
