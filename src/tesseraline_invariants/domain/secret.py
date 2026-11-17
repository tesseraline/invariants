"""The `Secret` marker: `Secret[str]` or `Annotated[str, Secret]` marks a value that never leaves.

`tesseraline-invariants/src/tesseraline_invariants/domain/secret.py`

At runtime `Secret[str]` is `Annotated[str, Secret]`, so a type checker sees a plain `str` and the
library sees the mark. Other ways to mark a secret (Pydantic types, settings, metadata) are
recognised in the application layer; this module only knows its
own mark.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, get_args, get_origin

if TYPE_CHECKING:
    type Secret[T] = Annotated[T, "tesseraline-secret"]
else:

    class Secret:
        """Marker for a secret value; use as `Secret[str]` or `Annotated[str, Secret]`.

        Examples:
            >>> from typing import get_args
            >>> get_args(Secret[str])[1] is Secret
            True
        """

        __slots__ = ()

        def __class_getitem__(cls, item: Any) -> Any:  # noqa: ANN401 - mirrors typing.Annotated
            """Return `Annotated[item, Secret]`."""
            return Annotated[item, cls]


def carries_secret_mark(annotation: object) -> bool:
    """Tell whether an annotation is marked with our own `Secret`.

    :param annotation: a resolved annotation, e.g. from `typing.get_type_hints(...,
      include_extras=True)`.
    :returns: True for `Secret[X]` and `Annotated[X, Secret]`, also inside `X | None`.

    Examples:
        >>> carries_secret_mark(Secret[str])
        True
        >>> carries_secret_mark(str)
        False
    """
    if get_origin(annotation) is Annotated:
        return any(_is_mark(meta) for meta in get_args(annotation)[1:])
    return any(carries_secret_mark(arg) for arg in get_args(annotation) if arg is not None)


def _is_mark(meta: object) -> bool:
    return meta is _MARK


_MARK: object = get_args(Secret[int])[1]
