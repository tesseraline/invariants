"""Port: minimal failing inputs, kept per promise and replayed first.

`tesseraline-invariants/src/tesseraline_invariants/ports/regression_store.py`
"""

from __future__ import annotations

from typing import Protocol


class RegressionStore(Protocol):
    """Load and save encoded inputs that once broke a promise."""

    def load(self, promise_id: str) -> list[dict[str, object]]:
        """Saved cases for one promise, oldest first.

        :param promise_id: the promise.
        :returns: encoded arguments, {parameter name: data}, canaries in place of secrets.
        """
        ...

    def save(self, promise_id: str, case: dict[str, object]) -> None:
        """Keep a new minimal failing case; an identical case is stored once.

        :param promise_id: the promise.
        :param case: encoded arguments.
        """
        ...
