"""Turn arguments into plain data and back, plant canaries on the way, hash what was called.

`tesseraline-invariants/src/tesseraline_invariants/application/codec.py`

Every argument goes one way: encode to JSON-able data with Pydantic's `TypeAdapter`, put canaries at
the secret paths, rebuild the typed value. This reaches frozen dataclasses and nested models without
touching objects, stores regressions as JSON (never pickle), and gives the input hash that is the
only trace of an input in logs.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from pydantic import TypeAdapter

from tesseraline_invariants.domain.canary import Canary, make_canary
from tesseraline_invariants.domain.exceptions import InvariantsError

if TYPE_CHECKING:
    from tesseraline_invariants.application.secret_fields import SecretField


class CodecError(InvariantsError):
    """A value of this type cannot be turned into data and back; its promise is not checked."""

    def __init__(self, annotation: object, detail: str) -> None:
        """Keep the type and the reason.

        :param annotation: the type that failed.
        :param detail: what Pydantic said, shortened.
        """
        super().__init__(f"{annotation!r}: {detail}")
        self.annotation = annotation


def encode(annotation: object, value: object) -> Any:  # noqa: ANN401 - JSON-able data has no narrower type
    """Turn a typed value into JSON-able data.

    :param annotation: the parameter's type.
    :param value: a value of that type.
    :returns: dicts, lists, strings, numbers, booleans and None.
    :raises CodecError: when Pydantic cannot serialise the type.

    Examples:
        >>> encode(list[int], [1, 2])
        [1, 2]
    """
    try:
        return _adapter(annotation).dump_python(value, mode="json")
    except Exception as error:  # pydantic raises several unrelated types here
        raise CodecError(annotation, str(error)[:200]) from error


def decode(annotation: object, data: object) -> object:
    """Rebuild a typed value from data.

    :param annotation: the parameter's type.
    :param data: what `encode` produced, possibly with canaries planted.
    :returns: a value of the type.
    :raises CodecError: when the data does not validate.
    """
    try:
        return _adapter(annotation).validate_python(data)
    except Exception as error:  # validation and schema errors alike
        raise CodecError(annotation, str(error)[:200]) from error


def plant(data: object, fields: list[SecretField], seed: int) -> tuple[object, tuple[Canary, ...]]:
    """Replace every string at a secret path with a canary.

    :param data: encoded arguments as {parameter name: data}.
    :param fields: secret fields found for the parameters (paths start with the parameter name).
    :param seed: the check's seed; the same seed plants the same canaries.
    :returns: the data with canaries and the canaries planted, in path order.

    Examples:
        >>> from tesseraline_invariants.application.secret_fields import SecretField, Strength
        >>> f = SecretField(("h", "key"), "H", "Secret marker", Strength.EXACT)
        >>> data, canaries = plant({"h": {"key": "x", "n": 1}}, [f], seed=1)
        >>> data["h"]["key"] == canaries[0].value, data["h"]["n"]
        (True, 1)
    """
    planted: list[Canary] = []
    copy = json.loads(json.dumps(data))
    for f in fields:
        canary = make_canary(seed, len(planted), f.dotted)
        if _set_at(copy, f.path, canary.value):
            planted.append(canary)
    return copy, tuple(planted)


def input_hash(data: object) -> str:
    """A short, stable hash of encoded arguments: the only trace of an input in logs and audit.

    Examples:
        >>> input_hash({"a": 1}) == input_hash({"a": 1})
        True
    """
    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _set_at(node: object, path: tuple[str, ...], value: str) -> bool:
    """Set every string at the path; "x[]" steps into each list item or dict value."""
    if not path or not isinstance(node, dict):
        return False
    head, rest = path[0], path[1:]
    name = head.removesuffix("[]")
    if name not in node:
        return False
    if head.endswith("[]"):
        return _set_in_each(node[name], rest, value)
    if rest:
        return _set_at(node[name], rest, value)
    if isinstance(node[name], str):
        node[name] = _shaped(node[name], value)
        return True
    return False


def _set_in_each(target: object, rest: tuple[str, ...], value: str) -> bool:
    """Apply the rest of the path to each item of a list, or each value of a dict."""
    if isinstance(target, dict):
        target = list(target.values()) if rest else []
    if not isinstance(target, list):
        return False
    if rest:
        done = False
        for item in target:  # every item, no short-circuit: each one gets its canary
            done = _set_at(item, rest, value) or done
        return done
    hits = [i for i, item in enumerate(target) if isinstance(item, str)]
    for i in hits:
        target[i] = _shaped(target[i], value)
    return bool(hits)


def _shaped(original: str, canary: str) -> str:
    """The canary in the shape of the value it replaces, so the code's validation accepts it.

    An e-mail address keeps its domain (the canary becomes the part before "@"); anything else is
    replaced whole. A field whose validation still refuses the canary makes the call raise, and the
    promise is reported "not checked", never passed.

    Examples:
        >>> _shaped("ada@example.co", "tsqcanaryab12")
        'tsqcanaryab12@example.co'
        >>> _shaped("Ada", "tsqcanaryab12")
        'tsqcanaryab12'
    """
    at = original.rfind("@")
    if 0 < at < len(original) - 1 and " " not in original:
        return canary + original[at:]
    return canary


@lru_cache(maxsize=512)
def _adapter(annotation: Any) -> TypeAdapter[Any]:  # noqa: ANN401 - any type can be adapted
    return TypeAdapter(annotation)
