"""Port: where a check gets example values and fakes.

`tesseraline-invariants/src/tesseraline_invariants/ports/input_source.py`
"""

from __future__ import annotations

from typing import Protocol


class InputSource(Protocol):
    """Give example values for data types and fakes for dependencies."""

    def examples(self, annotation: object) -> list[object]:
        """Example values of a type from the user's factories.

        :param annotation: a parameter's type.
        :returns: zero or more values; none means the type has no factory.
        """
        ...

    def fake_for(self, protocol: type) -> object | None:
        """A fake for a dependency typed as a Protocol.

        :param protocol: the Protocol class.
        :returns: an instance, or None when the user registered no fake.
        """
        ...
