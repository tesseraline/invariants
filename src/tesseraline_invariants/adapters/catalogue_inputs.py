"""Example values and fakes from the user's own code, named in settings or passed in.

`tesseraline-invariants/src/tesseraline_invariants/adapters/catalogue_inputs.py`

`[tool.invariants.factories]` maps a type to a factory ("pkg.mod:Type" =
"pkg.examples.data:make_type"); a factory returns one value or a list. `[tool.invariants.fakes]`
maps a Protocol to a fake class built with no arguments. Satisfies `ports.InputSource`.
"""

from __future__ import annotations

import typing
from collections.abc import Callable, Iterable, Mapping
from typing import get_args, get_origin


class CatalogueInputs:
    """Factories and fakes, keyed by the class they produce or stand in for.

    Examples:
        >>> cat = CatalogueInputs({int: lambda: [1, 2]}, {})
        >>> cat.examples(int), cat.examples(str)
        ([1, 2], [])
    """

    def __init__(
        self,
        factories: Mapping[type, Callable[[], object]],
        fakes: Mapping[type, Callable[[], object]],
    ) -> None:
        """Keep the mappings; nothing is called until a check asks.

        :param factories: type -> callable returning one value or an iterable of values.
        :param fakes: Protocol -> callable returning a fake instance.
        """
        self._factories = dict(factories)
        self._fakes = dict(fakes)

    def examples(self, annotation: object) -> list[object]:
        """Values from the factory registered for the type (Annotated and Optional unwrapped)."""
        bare = _bare(annotation)
        factory = self._factories.get(bare) if isinstance(bare, type) else None
        if factory is None:
            return []
        made = factory()
        if isinstance(made, Iterable) and not isinstance(made, (str, bytes, dict)):
            return list(made)
        return [made]

    def fake_for(self, protocol: type) -> object | None:
        """A new fake for the Protocol, or None."""
        maker = self._fakes.get(protocol)
        return maker() if maker else None


def _bare(annotation: object) -> object:
    """Strip Annotated and `| None`: a factory for Handle also serves `Secret[Handle] | None`."""
    if get_origin(annotation) is typing.Annotated:
        return _bare(get_args(annotation)[0])
    args = [a for a in get_args(annotation) if a is not type(None)]
    if get_origin(annotation) in (typing.Union, type(int | None)) and len(args) == 1:
        return _bare(args[0])
    return annotation
