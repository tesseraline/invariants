"""Port: the recorded promises, `invariants.lock` by default.

`tesseraline-invariants/src/tesseraline_invariants/ports/lock_store.py`
"""

from __future__ import annotations

from typing import Protocol


class LockStore(Protocol):
    """Read and replace the recorded promises."""

    def read(self) -> list[dict[str, object]]:
        """Every recorded promise; empty when there is no lock yet."""
        ...

    def write(self, entries: list[dict[str, object]]) -> None:
        """Replace the record with these entries (sorted by id by the adapter).

        :param entries: one lock entry per promise.
        """
        ...
