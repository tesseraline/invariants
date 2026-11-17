"""Catch the exits besides the return value: structlog events and standard logging records.

`tesseraline-invariants/src/tesseraline_invariants/infrastructure/capture.py`

While a promised function runs, structlog is captured with `structlog.testing.capture_logs` and the
root standard logger gets a handler at DEBUG level; both are restored afterwards. Every event and
record is rendered to text (message, arguments and extra fields) so `never_contains` can search it.
What a dependency received is read by the runner from the fakes themselves. A structlog logger bound
and cached before the check (cache_logger_on_first_use=True) keeps its old configuration: a stated
limit.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from collections.abc import Iterator

_RECORD_DEFAULTS = set(vars(logging.LogRecord("", 0, "", 0, "", None, None)))


class _Collect(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.texts: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        extra = {k: v for k, v in vars(record).items() if k not in _RECORD_DEFAULTS}
        self.texts.append(
            record.getMessage() + " " + json.dumps(extra, default=repr, sort_keys=True)
        )


@contextmanager
def captured_exits() -> Iterator[list[tuple[str, str]]]:
    """Collect log output from inside the block as (where, text) pairs, filled when it ends.

    Examples:
        >>> import logging
        >>> with captured_exits() as exits:
        ...     logging.getLogger("demo").info("sent %s", "token-123")
        >>> exits[0][0], "token-123" in exits[0][1]
        ('a standard log record', True)
    """
    exits: list[tuple[str, str]] = []
    root = logging.getLogger()
    handler, level = _Collect(), root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    saved = structlog.get_config()
    cap = structlog.testing.LogCapture()
    # every level: a project that filters info while checking could still emit info in production
    structlog.configure(
        processors=[cap],
        wrapper_class=structlog.make_filtering_bound_logger(logging.NOTSET),
        cache_logger_on_first_use=False,
    )
    try:
        yield exits
    finally:
        structlog.configure(**saved)
        root.removeHandler(handler)
        root.setLevel(level)
        exits.extend(
            ("a structlog event", json.dumps(e, default=repr, sort_keys=True)) for e in cap.entries
        )
        exits.extend(("a standard log record", text) for text in handler.texts)
