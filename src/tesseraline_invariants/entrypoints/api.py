"""The decorator and the three invariant builders: what an author writes next to a function.

`tesseraline-invariants/src/tesseraline_invariants/entrypoints/api.py`

`@invariant` checks the declaration at once, registers one
promise per invariant and returns the function unchanged, so a promised function costs nothing at
run time.
"""

from __future__ import annotations

import hashlib
import inspect
import io
import textwrap
import tokenize
from collections.abc import Callable
from typing import TypeVar

from tesseraline_invariants.application.declaration import check_boundaries
from tesseraline_invariants.application.registry import DEFAULT_REGISTRY, PromiseRegistry
from tesseraline_invariants.domain.exceptions import UsageError
from tesseraline_invariants.domain.kinds import (
    Holds,
    Invariant,
    NeverContains,
    Predicate,
    Preserves,
)
from tesseraline_invariants.domain.preservation import Kind

F = TypeVar("F", bound=Callable[..., object])


def invariant(
    *promises: Invariant, dry_run: bool = False, registry: PromiseRegistry | None = None
) -> Callable[[F], F]:
    """Declare what a function promises about its output.

    :param promises: one or more of `never_contains(...)`, `preserves(...)`, `holds(...)`.
    :param dry_run: the author's statement that the function is safe to run when every dependency
        it takes is a fake. Without it the promise is listed, never called.
    :param registry: where to record the promises; the default one unless a test passes its own.
    :returns: a decorator that returns the function unchanged.
    :raises UsageError: when no promise is given.
    :raises UntypedBoundaryError: a parameter or the return value has no annotation.
    :raises UntrackablePayloadError: a boundary is typed dict, Any or object.

    Examples:
        >>> from tesseraline_invariants.application.registry import PromiseRegistry
        >>> reg = PromiseRegistry()
        >>> @invariant(preserves("numbers"), dry_run=True, registry=reg)
        ... def restyle(text: str) -> str:
        ...     return text.upper()
        >>> restyle("up 15%"), [r.promise.kind for r in reg.all()]
        ('UP 15%', ['preserves'])
    """
    if not promises:
        raise UsageError("invariant", "give at least one promise")
    target = registry if registry is not None else DEFAULT_REGISTRY

    def decorate(function: F) -> F:
        resolved = check_boundaries(function)
        for promise in promises:
            target.add(function, promise, dry_run=dry_run, resolved=resolved)
        return function

    return decorate


def never_contains(*markers: object) -> NeverContains:
    """Promise that no secret planted in the input appears in the output.

    :param markers: what counts as secret; `Secret` covers every way a secret is marked (0005).
    :returns: the invariant.

    Examples:
        >>> from tesseraline_invariants.domain.secret import Secret
        >>> never_contains(Secret).params()
        (('markers', 'Secret'),)
    """
    names = tuple(getattr(m, "__name__", str(m)) for m in markers) or ("Secret",)
    return NeverContains(names)


def preserves(*kinds: str, both_ways: bool = True) -> Preserves:
    """Promise that every number, date, quote or link of the input is still in the output.

    :param kinds: any of "numbers", "dates", "quotes", "links".
    :param both_ways: also forbid items that appear only in the output (default, decision on gap 5).
    :returns: the invariant.
    :raises UsageError: for an unknown kind.

    Examples:
        >>> preserves("numbers", "dates").params()
        (('kinds', 'dates,numbers'), ('both_ways', 'true'))
    """
    try:
        return Preserves(tuple(Kind(k) for k in kinds), both_ways=both_ways)
    except ValueError as error:
        known = ", ".join(k.value for k in Kind)
        raise UsageError("preserves", f"unknown kind in {kinds}; known: {known}") from error


def holds(predicate: Predicate, name: str = "") -> Holds:
    """Promise that a predicate over the input and the output is true.

    :param predicate: called as predicate(input, output); several parameters arrive as a tuple.
    :param name: how reports name it; defaults to the predicate's own name.
    :returns: the invariant; its lock entry hashes the predicate's source, so an edit shows.

    Examples:
        >>> holds(lambda i, o: o >= 0, name="non-negative").params()[0]
        ('predicate', 'non-negative')
    """
    try:
        source = _normalized(inspect.getsource(predicate))
    except (OSError, TypeError):
        source = (
            predicate.__code__.co_code.hex() if hasattr(predicate, "__code__") else repr(predicate)
        )
    digest = hashlib.sha256(source.encode()).hexdigest()[:12]
    return Holds(predicate, name or getattr(predicate, "__qualname__", "predicate"), digest)


_LAYOUT = {tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.COMMENT}


def _normalized(source: str) -> str:
    r"""The source as its tokens only, so reformatting does not look like a changed promise.

    Examples:
        >>> _normalized("holds(lambda i, o:  o == i)  # same") == _normalized(
        ...     "holds(\n    lambda i, o: o == i\n)"
        ... )
        True
    """
    try:
        tokens = tokenize.generate_tokens(io.StringIO(textwrap.dedent(source)).readline)
        return " ".join(t.string for t in tokens if t.type not in _LAYOUT and t.string)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return " ".join(source.split())
