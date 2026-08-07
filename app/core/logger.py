"""
Structured logging configuration.
Every log line is emitted as JSON so job submissions, worker
activity, retries and failures can all be filtered/parsed later.
Logs go to both the console and logs/app.log.
"""

import json
import logging
import os
from app.core.config import settings

os.makedirs(settings.LOG_DIR, exist_ok=True)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_data"):
            payload.update(record.extra_data)
        return json.dumps(payload)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(JsonFormatter())

    file_handler = logging.FileHandler(settings.LOG_FILE)
    file_handler.setFormatter(JsonFormatter())

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger


def log_event(logger: logging.Logger, message: str, level: str = "info", **extra):
    """Helper to attach structured fields (job_id, status, etc.) to a log line."""
    log_fn = getattr(logger, level, logger.info)
    log_fn(message, extra={"extra_data": extra})
