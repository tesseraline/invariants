"""Find every secret field reachable from a type, and say which rule marked it.

`tesseraline-invariants/src/tesseraline_invariants/application/secret_fields.py`

Rules, strongest first: our `Secret` mark, Pydantic `SecretStr`
and `SecretBytes`, the user's own secret types, field metadata `{"secret": True}` (dataclasses,
attrs), a user `SecretRule` hook, and field-name patterns (opt-in, heuristic). A field marked
several ways is reported once, with the strongest kind. The walk follows dataclasses, Pydantic
models and attrs classes, through `X | None`, lists, tuples, sets and dict values, and stops at
cycles.
"""

from __future__ import annotations

import dataclasses
import fnmatch
import typing
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Any, get_args, get_origin

from pydantic import BaseModel, SecretBytes, SecretStr

from tesseraline_invariants.domain.exceptions import DeclarationError
from tesseraline_invariants.domain.secret import carries_secret_mark

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tesseraline_invariants.ports.secret_rule import SecretRule


class Strength(IntEnum):
    """How sure a marking is; higher wins when a field is marked several ways."""

    HEURISTIC = 1
    CUSTOM = 2
    EXACT = 3


@dataclass(frozen=True, slots=True)
class SecretField:
    """One secret field, by path from the type the walk started at.

    Examples:
        >>> SecretField(("handle", "credentials"), "Handle", "Secret marker", Strength.EXACT).dotted
        'handle.credentials'
    """

    path: tuple[str, ...]
    owner: str
    rule: str
    strength: Strength

    @property
    def dotted(self) -> str:
        """The path as text, e.g. "handle.credentials" or "items[].token"."""
        return ".".join(self.path)


@dataclass(frozen=True, slots=True)
class SecretRules:
    """What the user configured; the default recognises the exact markers only."""

    types: tuple[type, ...] = ()
    name_patterns: tuple[str, ...] = ()
    hooks: tuple[SecretRule, ...] = field(default=())


def find_secret_fields(root: object, rules: SecretRules, prefix: str = "") -> list[SecretField]:
    """Every secret field reachable from a type annotation.

    :param root: a type or annotation, e.g. a dataclass or `list[Handle]`.
    :param rules: the user's settings for what else counts as secret.
    :param prefix: the name the walk starts under (a parameter name, or "" for a return value).
    :returns: one entry per field path, strongest rule kept, sorted by path.

    Examples:
        >>> from dataclasses import make_dataclass
        >>> from tesseraline_invariants.domain.secret import Secret
        >>> Handle = make_dataclass("Handle", [("table", str), ("credentials", Secret[str])])
        >>> [f.dotted for f in find_secret_fields(Handle, SecretRules(), "handle")]
        ['handle.credentials']
    """
    best: dict[tuple[str, ...], SecretField] = {}
    start = (prefix,) if prefix else ()
    for found in _walk(root, start, rules, set()):
        if found.path not in best or found.strength > best[found.path].strength:
            best[found.path] = found
    return [best[k] for k in sorted(best)]


def _walk(
    tp: object, path: tuple[str, ...], rules: SecretRules, seen: set[int]
) -> Iterator[SecretField]:
    origin, args = get_origin(tp), get_args(tp)
    if origin is typing.Annotated:
        yield from _walk(args[0], path, rules, seen)
        return
    if origin is not None:
        inner = args[1:] if origin is dict else args
        step = (
            path
            if origin in (typing.Union, _UNION)
            else (*path[:-1], f"{path[-1]}[]")
            if path
            else ("[]",)
        )
        for arg in inner:
            if arg is not type(None) and arg is not Ellipsis:
                yield from _walk(arg, step, rules, seen)
        return
    if not isinstance(tp, type) or id(tp) in seen:
        return
    seen = seen | {id(tp)}
    for name, annotation, metadata in _fields_of(tp):
        here = (*path, name)
        rule = _rule_for(tp, name, annotation, metadata, rules)
        if rule:
            yield SecretField(here, tp.__name__, *rule)
        yield from _walk(annotation, here, rules, seen)


def _fields_of(tp: type) -> Iterator[tuple[str, object, typing.Mapping[str, Any]]]:
    if issubclass(tp, BaseModel):
        for name, info in tp.model_fields.items():
            annotation: object = info.annotation
            if info.metadata:
                annotation = typing.Annotated[annotation, *info.metadata]
            extra = info.json_schema_extra
            yield name, annotation, extra if isinstance(extra, dict) else {}
        return
    if not (dataclasses.is_dataclass(tp) or hasattr(tp, "__attrs_attrs__")):
        return
    try:
        hints = typing.get_type_hints(tp, include_extras=True)
    except (NameError, TypeError) as error:
        # a secret hidden behind an unresolvable hint must never pass as "no secret here"
        raise DeclarationError(
            tp.__qualname__, "fields", f"type hints cannot be resolved: {error}"
        ) from error
    if dataclasses.is_dataclass(tp):
        for f in dataclasses.fields(tp):
            yield f.name, hints.get(f.name, f.type), f.metadata
    else:
        for a in tp.__attrs_attrs__:  # type: ignore[attr-defined]
            yield a.name, hints.get(a.name, a.type), a.metadata


def _rule_for(
    owner: type,
    name: str,
    annotation: object,
    metadata: typing.Mapping[str, Any],
    rules: SecretRules,
) -> tuple[str, Strength] | None:
    base = get_args(annotation)[0] if get_origin(annotation) is typing.Annotated else annotation
    checks: tuple[tuple[bool, str, Strength], ...] = (
        (carries_secret_mark(annotation), "Secret marker", Strength.EXACT),
        (
            base in (SecretStr, SecretBytes),
            f"Pydantic {getattr(base, '__name__', '')}",
            Strength.EXACT,
        ),
        (
            _is_user_type(base, rules),
            f"secret type {getattr(base, '__name__', '')}",
            Strength.EXACT,
        ),
        (metadata.get("secret") is True, "field metadata", Strength.EXACT),
        (any(hook.is_secret(owner, name) for hook in rules.hooks), "custom rule", Strength.CUSTOM),
        (_matches_name(name, rules), "secret by name", Strength.HEURISTIC),
    )
    return next(((label, strength) for hit, label, strength in checks if hit), None)


def _is_user_type(base: object, rules: SecretRules) -> bool:
    return isinstance(base, type) and any(issubclass(base, t) for t in rules.types)


def _matches_name(name: str, rules: SecretRules) -> bool:
    return any(fnmatch.fnmatch(name.lower(), p.lower()) for p in rules.name_patterns)


_UNION = type(int | None)
