"""Describing a write handle without its credentials, and a debug header without secrets.

`tesseraline-invariants/examples/passing/passing_example/exports.py`

Build the output from named fields, never from the whole object (log and serialise named
fields only).
"""

from __future__ import annotations

import base64
import json

from passing_example.models import WriteHandle
from tesseraline_invariants import Secret, invariant, never_contains


@invariant(never_contains(Secret), dry_run=True)
def to_query_json(handle: WriteHandle) -> str:
    """Describe where a query writes: the table only."""
    return json.dumps({"table": handle.table})


@invariant(never_contains(Secret), dry_run=True)
def debug_header(handle: WriteHandle) -> str:
    """A debug header for support: the table only."""
    return base64.b64encode(handle.table.encode()).decode()
