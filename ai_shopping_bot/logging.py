"""Structured logging helper. Event name plus fields, never f-strings in log calls."""

from __future__ import annotations

import logging
from typing import Any


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"ai_shopping_bot.{name}")


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields: Any) -> None:
    logger.log(level, event, extra={"fields": fields})
