"""Logging for Inflection Curator.

This module provides logging functionality for the application, including a
function for auditing events.

Attributes:
    logger (logging.Logger): The logger for the application.
"""

import json, uuid, time, logging
from typing import Dict, Any, Optional
from collections.abc import Callable
from .config import LOG_SINK


def get_logger(name: str) -> logging.Logger:
    """Gets a logger instance.

    Args:
        name: The name of the logger.

    Returns:
        A logger instance.
    """
    return logging.getLogger(name)


logger = get_logger("app")
logging.basicConfig(level=logging.INFO)


def audit_event(
    event_type: str,
    payload: dict[str, Any],
    *,
    sink: str = LOG_SINK,
    http_post: Callable[[str, dict[str, Any]], None] | None = None,
) -> str:
    """Audits an event.

    Args:
        event_type: The type of the event.
        payload: The payload of the event.
        sink: The sink for the event. Can be 'stdout', 'file:/path/to/log.jsonl',
            or 'http(s)://...'.
        http_post: A callable to use for posting the event to an HTTP sink.

    Returns:
        The event ID.
    """
    event_id = str(uuid.uuid4())
    rec = {"event_id": event_id, "ts": time.time(), "type": event_type, **payload}
    if sink == "stdout":
        logger.info(json.dumps(rec, ensure_ascii=False))
    elif sink.startswith("file:"):
        path = sink.split("file:", 1)[1]
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    elif sink.startswith("http"):
        if http_post:
            http_post(sink, json=rec)
        else:
            logger.warning(
                "http sink set but no http_post provided; falling back to stdout"
            )
            logger.info(json.dumps(rec, ensure_ascii=False))
    else:
        logger.info(json.dumps(rec, ensure_ascii=False))
    return event_id
