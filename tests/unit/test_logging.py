from __future__ import annotations

import json
import logging

from ai_shopping_bot.logging import ROOT, configure_logging, get_logger, log_event


def _capture(capsys, fmt: str, level: str = "INFO"):
    configure_logging(level, fmt)
    log = get_logger("t")
    log_event(log, "monitor.refreshed", checked=3, note="two words", empty="")
    log_event(log, "debug.only", level=logging.DEBUG, x=1)
    return capsys.readouterr().err.strip().splitlines()


def test_text_format_renders_event_and_fields(capsys):
    lines = _capture(capsys, "text")
    assert lines == [
        'INFO     ai_shopping_bot.t monitor.refreshed checked=3 note="two words" empty=""'
    ]


def test_json_format_one_object_per_line(capsys):
    lines = _capture(capsys, "json")
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert obj["event"] == "monitor.refreshed" and obj["fields"]["checked"] == 3
    assert obj["logger"] == "ai_shopping_bot.t" and obj["level"] == "INFO" and obj["ts"]


def test_debug_level_and_idempotent_handler(capsys):
    lines = _capture(capsys, "text", level="DEBUG")
    assert any("debug.only x=1" in line for line in lines)
    configure_logging("INFO", "text")
    configure_logging("INFO", "text")
    root = logging.getLogger(ROOT)
    assert sum(1 for h in root.handlers if h.get_name() == "ai_shopping_bot.console") == 1
    assert root.propagate is False
