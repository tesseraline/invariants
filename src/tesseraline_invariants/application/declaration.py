"""Inspect a promised function when it is decorated: every boundary typed, none hidden in a dict.

`tesseraline-invariants/src/tesseraline_invariants/application/declaration.py`

An untyped parameter or return raises `UntypedBoundaryError`; one
typed `dict`, `Any` or `object` raises `UntrackablePayloadError`. A forward reference that cannot be
resolved yet is returned as pending and resolved again at the first check.
"""

from __future__ import annotations

import inspect
import types
import typing
from collections.abc import Callable, Mapping, MutableMapping
from typing import Any, get_args, get_origin

from tesseraline_invariants.domain.exceptions import (
    UntrackablePayloadError,
    UntypedBoundaryError,
)

_HIDING = {
    dict: "dict",
    Any: "Any",
    object: "object",
    Mapping: "Mapping",
    MutableMapping: "MutableMapping",
}


def check_boundaries(function: Callable[..., object]) -> bool:
    """Raise if a boundary of the function cannot be tracked.

    :param function: the function being decorated.
    :returns: True when every annotation resolved; False when a forward reference is still pending.
    :raises UntypedBoundaryError: a parameter or the return value has no annotation.
    :raises UntrackablePayloadError: a boundary is typed dict, Any, object or a Mapping.

    Examples:
        >>> def f(x: int) -> str: ...
        >>> check_boundaries(f)
        True
        >>> def g(x: dict) -> str: ...
        >>> check_boundaries(g)
        Traceback (most recent call last):
        tesseraline_invariants.domain.exceptions.UntrackablePayloadError: ...: is typed dict; ...
    """
    name = qualified_name(function)
    signature = inspect.signature(function)
    for parameter in signature.parameters.values():
        if parameter.annotation is inspect.Parameter.empty:
            raise UntypedBoundaryError(name, parameter.name)
    if signature.return_annotation is inspect.Signature.empty:
        raise UntypedBoundaryError(name, "return")
    try:
        hints = typing.get_type_hints(function, include_extras=True)
    except NameError:
        return False
    for boundary, annotation in hints.items():
        hidden = _hiding_name(annotation)
        if hidden:
            raise UntrackablePayloadError(name, boundary, hidden)
    return True


def qualified_name(function: Callable[..., object]) -> str:
    """The id a promise uses for its function: "module:qualname".

    :param function: any function.
    :returns: e.g. "myapp.exporters:to_query_json".
    """
    return f"{function.__module__}:{function.__qualname__}"


def _hiding_name(annotation: object) -> str:
    """The name of the hiding type at the top of an annotation (also inside X | None), or ""."""
    base = annotation
    if get_origin(base) is typing.Annotated:
        base = get_args(base)[0]
    if base in _HIDING:
        return _HIDING[base]
    origin = get_origin(base)
    if origin in _HIDING:
        return _HIDING[origin]
    if origin in (typing.Union, types.UnionType):
        return next((h for arg in get_args(base) if (h := _hiding_name(arg))), "")
    return ""
