import json
import logging

import pytest
import structlog

from app.logging_config import configure_logging


def test_app_and_stdlib_logs_are_json(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")

    structlog.get_logger().info("app_event", answer=42)
    logging.getLogger("uvicorn.access").info('"GET /health HTTP/1.1" %d', 200)
    logging.getLogger("sqlalchemy").debug("below the level")

    app_log, access_log = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert app_log["event"] == "app_event"
    assert app_log["answer"] == 42
    assert access_log["event"] == '"GET /health HTTP/1.1" 200'
    assert access_log["logger"] == "uvicorn.access"
    assert access_log["level"] == "info"
