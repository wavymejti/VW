"""
Memory Log Collector for VW California AI Trip Planner.

Collects, stores, and manages system, application, and interaction logs
in memory. Provides search, filtering, statistic calculations, export to JSON,
and integration with standard Python logging.
"""

from datetime import datetime, timezone
import json
import logging
import threading
from typing import Any, Dict, List, Optional


class MemoryLogger:
    """
    In-memory log collector that accumulates log records thread-safely.
    """

    def __init__(self, max_capacity: Optional[int] = 10000) -> None:
        """
        Initialize the in-memory logger.

        Args:
            max_capacity (int, optional): Maximum number of log records to keep.
                                          Defaults to 10000.
        """
        self._logs: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self.max_capacity = max_capacity

    def log(
        self,
        level: str,
        message: str,
        category: str = "GENERAL",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record a log entry into memory.

        Args:
            level (str): Severity level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL').
            message (str): Log text message.
            category (str): System component or category name.
            metadata (dict, optional): Additional contextual metadata.

        Returns:
            dict: The newly created log record.
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level.upper(),
            "category": category,
            "message": message,
            "metadata": metadata or {},
        }

        with self._lock:
            if self.max_capacity and len(self._logs) >= self.max_capacity:
                # Evict oldest entry if capacity limit reached
                self._logs.pop(0)
            self._logs.append(entry)

        return entry

    def info(
        self,
        message: str,
        category: str = "GENERAL",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record an INFO level log."""
        return self.log("INFO", message, category, metadata)

    def warning(
        self,
        message: str,
        category: str = "GENERAL",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record a WARNING level log."""
        return self.log("WARNING", message, category, metadata)

    def error(
        self,
        message: str,
        category: str = "GENERAL",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record an ERROR level log."""
        return self.log("ERROR", message, category, metadata)

    def debug(
        self,
        message: str,
        category: str = "GENERAL",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record a DEBUG level log."""
        return self.log("DEBUG", message, category, metadata)

    def get_logs(
        self,
        level: Optional[str] = None,
        category: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve collected logs from memory with optional filtering.

        Args:
            level (str, optional): Filter by log level.
            category (str, optional): Filter by category.
            limit (int, optional): Return up to `limit` latest records.

        Returns:
            list: List of matching log record dictionaries.
        """
        with self._lock:
            results = list(self._logs)

        if level:
            lvl_upper = level.upper()
            results = [r for r in results if r["level"] == lvl_upper]

        if category:
            cat_upper = category.upper()
            results = [r for r in results if r["category"].upper() == cat_upper]

        if limit is not None and limit > 0:
            results = results[-limit:]

        return results

    def search_logs(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for logs containing a given query string in message or metadata.

        Args:
            query (str): Substring query to search for.

        Returns:
            list: List of matching log entries.
        """
        q_lower = query.lower()
        with self._lock:
            logs_copy = list(self._logs)

        matching = []
        for entry in logs_copy:
            msg_match = q_lower in entry["message"].lower()
            meta_match = q_lower in json.dumps(entry["metadata"]).lower()
            if msg_match or meta_match:
                matching.append(entry)

        return matching

    def get_stats(self) -> Dict[str, Any]:
        """
        Calculate summary statistics of logs stored in memory.

        Returns:
            dict: Summary containing total counts per log level and category.
        """
        with self._lock:
            logs_copy = list(self._logs)

        stats: Dict[str, Any] = {
            "total_logs": len(logs_copy),
            "by_level": {},
            "by_category": {},
        }

        for entry in logs_copy:
            lvl = entry["level"]
            cat = entry["category"]

            stats["by_level"][lvl] = stats["by_level"].get(lvl, 0) + 1
            stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1

        return stats

    def clear(self) -> None:
        """Clear all stored logs from memory."""
        with self._lock:
            self._logs.clear()

    def export_json(self) -> str:
        """
        Export all in-memory logs as a formatted JSON string.

        Returns:
            str: JSON string of all log records.
        """
        with self._lock:
            return json.dumps(self._logs, indent=2, ensure_ascii=False)


# Global singleton memory logger instance
_GLOBAL_MEMORY_LOGGER = MemoryLogger()


def get_memory_logger() -> MemoryLogger:
    """
    Get global singleton MemoryLogger instance.

    Returns:
        MemoryLogger: The shared global memory logger object.
    """
    return _GLOBAL_MEMORY_LOGGER


class MemoryLogHandler(logging.Handler):
    """
    Custom Logging Handler that forwards Python standard `logging` messages
    directly into the in-memory MemoryLogger.
    """

    def __init__(self, memory_logger: Optional[MemoryLogger] = None) -> None:
        super().__init__()
        self.memory_logger = memory_logger or get_memory_logger()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.memory_logger.log(
                level=record.levelname,
                message=msg,
                category=record.name,
                metadata={
                    "filename": record.filename,
                    "lineno": record.lineno,
                    "funcName": record.funcName,
                },
            )
        except Exception:
            self.handleError(record)


def attach_memory_handler_to_root(logger_name: Optional[str] = None) -> None:
    """
    Attach standard logging handler to capture standard python logger output
    into memory.

    Args:
        logger_name (str, optional): Target logger name. Defaults to root logger.
    """
    target_logger = logging.getLogger(logger_name)
    handler = MemoryLogHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    target_logger.addHandler(handler)
