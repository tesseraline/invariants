"""Port: where audit records go; never switched off by a log level.

`tesseraline-invariants/src/tesseraline_invariants/ports/audit_sink.py`
"""

from __future__ import annotations

from typing import Protocol


class AuditSink(Protocol):
    """Append one audit record; records carry ids and hashes only, never a secret value."""

    def write(self, record: dict[str, object]) -> None:
        """Append one record (schema version in record["schema"]).

        :param record: the record to keep.
        """
        ...
