"""Promises that cannot be checked, and say so instead of passing.

`tesseraline-invariants/examples/caught/caught_example/unchecked.py`
"""

from __future__ import annotations

import socket

from caught_example.models import WriteHandle
from tesseraline_invariants import Secret, invariant, never_contains


@invariant(never_contains(Secret))
def send_to_warehouse(handle: WriteHandle) -> str:
    """Not marked dry_run=True: it may write somewhere, so a check never calls it."""
    return handle.table


@invariant(never_contains(Secret), dry_run=True)
def with_telemetry(handle: WriteHandle) -> str:
    """Marked dry_run, yet it calls the network: the check blocks it and names the host."""
    socket.getaddrinfo("telemetry.example", 443)
    return handle.table
