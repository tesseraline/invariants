"""Two ways a secret leaves: inside a repr written into JSON, and base64-encoded in a header.

`tesseraline-invariants/examples/caught/caught_example/exports.py`

In the first, an object that holds credentials is written whole into query JSON through its repr,
and the credentials leave with it.
"""

from __future__ import annotations

import base64
import json

from caught_example.models import WriteHandle
from tesseraline_invariants import Secret, invariant, never_contains


@invariant(never_contains(Secret), dry_run=True)
def to_query_json(handle: WriteHandle) -> str:
    """Describe where a query writes, for the query page (leaks: the repr holds the credentials)."""
    return json.dumps({"table": handle.table, "handle": repr(handle)})


@invariant(never_contains(Secret), dry_run=True)
def debug_header(handle: WriteHandle) -> str:
    """A debug header for support (leaks: base64 is not encryption)."""
    return base64.b64encode(f"{handle.table}:{handle.credentials}".encode()).decode()
