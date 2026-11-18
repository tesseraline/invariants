"""The data the example functions take: a write handle holding credentials, an order, a note.

`tesseraline-invariants/examples/passing/passing_example/models.py`
"""

from __future__ import annotations

from dataclasses import dataclass

from tesseraline_invariants import Secret


@dataclass(frozen=True, slots=True)
class WriteHandle:
    """Where a query writes, and the credentials to do it."""

    table: str
    credentials: Secret[str]


@dataclass(frozen=True, slots=True)
class Order:
    """An order with its line amounts in cents."""

    order_id: str
    lines: list[int]


@dataclass(frozen=True, slots=True)
class Summary:
    """What a summary reports about an order."""

    order_id: str
    total: int


def example_handles() -> list[WriteHandle]:
    """Factory named in pyproject.toml: realistic handles (fake credentials)."""
    return [WriteHandle("orders", "example-password"), WriteHandle("audit_log", "example-token")]


def example_sentences() -> list[str]:
    """Factory named in pyproject.toml: sentences like the ones the function really gets.

    Random strings from Hypothesis almost never look like "rose 15% to 1,200", so a preserves
    promise needs realistic text from a factory to mean anything.
    """
    return [
        "Attendance rose 15% to 1,200 people this season.",
        "Rainfall dropped 2.5 percent on 3 May 2024.",
        "Tickets stayed at 40 dollars each.",
    ]
