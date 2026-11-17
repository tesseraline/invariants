"""Canaries: unique fake secrets planted in secret fields, then searched for in a function's output.

`tesseraline-invariants/src/tesseraline_invariants/domain/canary.py`

A canary is found in plain form, JSON-escaped, URL-encoded or base64-encoded (architecture decision
record 0008). Hashing and truncation hide it: a stated limit. The canary's value is never logged;
only its id is.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from urllib.parse import quote

PREFIX = "tsqcanary"


@dataclass(frozen=True, slots=True)
class Canary:
    """One planted fake secret: its id may be logged, its value never.

    Examples:
        >>> c = make_canary(seed=7, index=0)
        >>> c.value.startswith(PREFIX), len(c.canary_id)
        (True, 8)
    """

    canary_id: str
    value: str
    field: str = ""


def make_canary(seed: int, index: int, field: str = "") -> Canary:
    """Build a deterministic canary for one field: the same seed and index give the same value.

    :param seed: the check's seed, so a run can be repeated.
    :param index: position of the field among the planted ones.
    :param field: "Type.field" it was planted in, for the report.
    :returns: the canary; its value contains only letters and digits.
    """
    digest = hashlib.sha256(f"{seed}:{index}".encode()).hexdigest()
    return Canary(canary_id=digest[:8], value=f"{PREFIX}{digest[8:32]}", field=field)


def forms_of(canary: Canary) -> dict[str, tuple[str, ...]]:
    """Every searchable form of a canary, by encoding name.

    :param canary: the planted canary.
    :returns: {"plain": ..., "json": ..., "url": ..., "base64": ...}; base64 holds three stable
      cores, one per byte alignment, so the canary is found inside a longer encoded string.

    Examples:
        >>> sorted(forms_of(make_canary(1, 0)))
        ['base64', 'json', 'plain', 'url']
    """
    value = canary.value
    return {
        "plain": (value,),
        "json": (json.dumps(value)[1:-1],),
        "url": (quote(value, safe=""),),
        "base64": tuple(_base64_core(value, offset) for offset in range(3)),
    }


def found_in(text: str, canary: Canary) -> str | None:
    """Find a canary in text, in any known form.

    :param text: the function's output, rendered as text by the application layer.
    :param canary: the canary to look for.
    :returns: the name of the form it was found in, or None.

    Examples:
        >>> import base64
        >>> c = make_canary(3, 1)
        >>> found_in(base64.b64encode(("user=" + c.value).encode()).decode(), c)
        'base64'
        >>> found_in("nothing here", c) is None
        True
    """
    for form, variants in forms_of(canary).items():
        if any(v and v in text for v in variants):
            return form
    return None


def _base64_core(value: str, offset: int) -> str:
    """The part of base64(prefix + value) that does not depend on what surrounds the value."""
    encoded = base64.b64encode(b"\0" * offset + value.encode()).decode().rstrip("=")
    start = 4 if offset else 0
    return encoded[start:-4]
