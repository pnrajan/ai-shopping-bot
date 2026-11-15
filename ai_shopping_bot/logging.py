"""Structured logging helper. Event name plus fields, never f-strings in log calls.

``configure_logging`` attaches one console handler to the ``ai_shopping_bot`` logger so
events show up next to uvicorn's access log. Text format renders ``event key=value ...``;
JSON format renders one object per line for log shippers.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

ROOT = "ai_shopping_bot"
_HANDLER_NAME = "ai_shopping_bot.console"


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{ROOT}.{name}")


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields: Any) -> None:
    logger.log(level, event, extra={"fields": fields})


class TextFormatter(logging.Formatter):
    """``INFO     ai_shopping_bot.tracking monitor.refreshed checked=3 updated=3``"""

    def format(self, record: logging.LogRecord) -> str:
        fields = getattr(record, "fields", None) or {}
        tail = " ".join(f"{k}={_scalar(v)}" for k, v in fields.items())
        line = f"{record.levelname:<8} {record.name} {record.getMessage()}"
        if tail:
            line = f"{line} {tail}"
        if record.exc_info:
            line = f"{line}\n{self.formatException(record.exc_info)}"
        return line


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if fields:
            payload["fields"] = fields
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _scalar(v: Any) -> str:
    if isinstance(v, str) and (" " in v or not v):
        return json.dumps(v)
    return str(v)


def configure_logging(level: str = "INFO", fmt: str = "text") -> None:
    """Idempotent. Safe to call per ``create_app``; replaces our handler, never duplicates it."""
    root = logging.getLogger(ROOT)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.propagate = False
    for h in list(root.handlers):
        if h.get_name() == _HANDLER_NAME:
            root.removeHandler(h)
    handler = logging.StreamHandler(sys.stderr)
    handler.set_name(_HANDLER_NAME)
    handler.setFormatter(JsonFormatter() if fmt == "json" else TextFormatter())
    root.addHandler(handler)
