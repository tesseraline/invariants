"""Turn a function's output, or its input, into the text that invariants search and compare.

`tesseraline-invariants/src/tesseraline_invariants/application/rendering.py`

A value is rendered every way it could leave: as itself when it is text or bytes, as JSON through
its type, and as `repr`. A canary that leaves by any of these paths is found. Pydantic's masked
`SecretStr` shows as "**********" in JSON and repr, which is the point: a masked secret is not a
leak.
"""

from __future__ import annotations

import contextlib
import json
from typing import TYPE_CHECKING

from tesseraline_invariants.application.codec import CodecError, encode

if TYPE_CHECKING:
    from collections.abc import Iterable


def render(value: object, annotation: object) -> str:
    """Every textual form of a value, joined.

    :param value: an output or an argument.
    :param annotation: its declared type, used for the JSON form.
    :returns: text to search; never logged, it may hold canaries.

    Examples:
        >>> "15%" in render({"rate": "15%"}, dict[str, str])
        True
        >>> render(b"abc", bytes).startswith("abc")
        True
    """
    parts: list[str] = []
    if isinstance(value, str):
        parts.append(value)
    elif isinstance(value, (bytes, bytearray)):
        parts.append(bytes(value).decode("utf-8", errors="replace"))
    with contextlib.suppress(CodecError):  # the repr below still carries the value
        parts.append(json.dumps(encode(annotation, value), ensure_ascii=False, sort_keys=True))
    parts.append(repr(value))
    return "\n".join(parts)


def render_inputs(values: Iterable[tuple[object, object]]) -> str:
    """Render several (value, annotation) pairs as one text, for `preserves`.

    :param values: the data arguments of one call with their types.
    :returns: their renderings, one per line; one form each, so an item is not counted twice
        when inputs and output are compared.
    """
    out = []
    for value, annotation in values:
        if isinstance(value, str):
            out.append(value)
            continue
        try:
            out.append(json.dumps(encode(annotation, value), ensure_ascii=False, sort_keys=True))
        except CodecError:
            out.append(repr(value))
    return "\n".join(out)


def first_form(value: object, annotation: object) -> str:
    """The one natural textual form of an output, for `preserves` (text as itself, else JSON).

    :param value: the output.
    :param annotation: its declared type.
    :returns: one text, so numbers are not counted once per form.
    """
    return render_inputs([(value, annotation)])
