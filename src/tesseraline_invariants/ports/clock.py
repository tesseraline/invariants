"""Port: the time written into audit records, fixed in tests.

`tesseraline-invariants/src/tesseraline_invariants/ports/clock.py`
"""

from __future__ import annotations

from typing import Protocol


class Clock(Protocol):
    """Tell the time as ISO 8601 in UTC."""

    def now(self) -> str:
        """The current time, e.g. "2026-11-17T21:04:05Z"."""
        ...
