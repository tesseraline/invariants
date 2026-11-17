"""A restyle that keeps every number, and a total that adds every line.

`tesseraline-invariants/examples/passing/passing_example/texts.py`
"""

from __future__ import annotations

from passing_example.models import Order, Summary
from tesseraline_invariants import holds, invariant, preserves


@invariant(preserves("numbers"), dry_run=True)
def shorten(text: str) -> str:
    """Shorten a sentence for a card: tidy spaces, keep every number."""
    return " ".join(text.split())


@invariant(
    holds(lambda order, summary: summary.total == sum(order.lines), name="total adds up"),
    dry_run=True,
)
def summarize(order: Order) -> Summary:
    """Summarise an order: every line counts."""
    return Summary(order.order_id, sum(order.lines))
