from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from io import StringIO

_ACTIVE_RUN_ID: ContextVar[str | None] = ContextVar("ui_active_run_id", default=None)
_SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|authorization|bearer|token|secret|password)(\s*[:=]\s*)([^\s,;]+)"
)


def _redact(message: str) -> str:
    return _SECRET_PATTERN.sub(r"\1\2[REDACTED]", message)


class RunLogHandler(logging.Handler):
    """Capture only records emitted inside one interactive run context."""

    def __init__(self, run_id: str, *, level: int = logging.INFO) -> None:
        super().__init__(level=level)
        self.run_id = run_id
        self.buffer = StringIO()
        self.setFormatter(
            logging.Formatter(
                "[%(asctime)s] %(levelname)-5s %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    def emit(self, record: logging.LogRecord) -> None:
        if _ACTIVE_RUN_ID.get() != self.run_id:
            return
        try:
            self.buffer.write(_redact(self.format(record)) + "\n")
        except Exception:  # noqa: BLE001 - logging handlers must never break a run.
            self.handleError(record)

    def text(self) -> str:
        return self.buffer.getvalue().rstrip()


@contextmanager
def capture_run_logs(
    run_id: str,
    *,
    level: str = "INFO",
    logger_name: str = "llm_ontology",
) -> Iterator[RunLogHandler]:
    logger = logging.getLogger(logger_name)
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    handler = RunLogHandler(run_id, level=numeric_level)
    previous_level = logger.level
    token = _ACTIVE_RUN_ID.set(run_id)
    logger.addHandler(handler)
    if not logger.isEnabledFor(numeric_level):
        logger.setLevel(numeric_level)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
        _ACTIVE_RUN_ID.reset(token)
