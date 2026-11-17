"""A restyle that loses a number, and a total that forgets a line.

`tesseraline-invariants/examples/caught/caught_example/texts.py`
"""

from __future__ import annotations

import re

from caught_example.models import Order, Summary
from tesseraline_invariants import holds, invariant, preserves


@invariant(preserves("numbers"), dry_run=True)
def shorten(text: str) -> str:
    """Shorten a sentence for a card (mistake: drops every percentage)."""
    return re.sub(r"\s*\d+(\.\d+)?%", "", text)


@invariant(
    holds(lambda order, summary: summary.total == sum(order.lines), name="total adds up"),
    dry_run=True,
)
def summarize(order: Order) -> Summary:
    """Summarise an order (mistake: only the first three lines are added)."""
    return Summary(order.order_id, sum(order.lines[:3]))
