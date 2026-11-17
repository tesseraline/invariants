"""Every promise declared with `@invariant`, collected when its module is imported.

`tesseraline-invariants/src/tesseraline_invariants/application/registry.py`

The decorator writes into `DEFAULT_REGISTRY`; tests and the check runner can use their own registry.
Nothing here calls a promised function.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tesseraline_invariants.application.declaration import qualified_name
from tesseraline_invariants.domain.promise import Promise

if TYPE_CHECKING:
    from collections.abc import Callable

    from tesseraline_invariants.domain.kinds import Invariant


@dataclass(frozen=True, slots=True)
class Registered:
    """A promise together with the function and invariant it came from."""

    promise: Promise
    function: Callable[..., object]
    invariant: Invariant
    is_async: bool
    resolved: bool = True


@dataclass(slots=True)
class PromiseRegistry:
    """The promises known in this process, in declaration order.

    Examples:
        >>> from tesseraline_invariants.domain.kinds import NeverContains
        >>> reg = PromiseRegistry()
        >>> def f(x: int) -> int: ...
        >>> reg.add(f, NeverContains(("Secret",)), dry_run=True).promise.kind
        'never_contains'
        >>> len(reg.all())
        1
    """

    _items: dict[str, Registered] = field(default_factory=dict)

    def add(
        self,
        function: Callable[..., object],
        invariant: Invariant,
        dry_run: bool,
        resolved: bool = True,
    ) -> Registered:
        """Record one invariant on one function; a second identical declaration replaces the first.

        :param function: the promised function.
        :param invariant: one of NeverContains, Preserves, Holds.
        :param dry_run: the author's statement that the function may run in a check.
        :param resolved: False when a forward reference must be resolved at the first check.
        :returns: the registered promise.
        """
        promise = Promise(qualified_name(function), invariant.kind, invariant.params(), dry_run)
        item = Registered(
            promise, function, invariant, inspect.iscoroutinefunction(function), resolved
        )
        self._items[promise.promise_id] = item
        return item

    def all(self) -> list[Registered]:
        """Every registered promise, sorted by id so reports and the lock are stable."""
        return [self._items[k] for k in sorted(self._items)]

    def clear(self) -> None:
        """Forget every promise (tests only)."""
        self._items.clear()


DEFAULT_REGISTRY = PromiseRegistry()
