"""Build the inputs a check tries: regressions, then factories, then Hypothesis (decision 0007).

`tesseraline-invariants/src/tesseraline_invariants/application/inputs.py`

Parameters typed as a Protocol are dependencies and get the user's fake;
every other parameter is data. Inputs are encoded data, {parameter name: data}, so canaries can be
planted and regressions stored the same way. When nothing can be built the reason is returned: a
promise is "not checked", never passed.
"""

from __future__ import annotations

import inspect
import itertools
import typing
from dataclasses import dataclass
from typing import TYPE_CHECKING

from hypothesis import strategies as st

from tesseraline_invariants.application.codec import CodecError, encode

if TYPE_CHECKING:
    from collections.abc import Callable

    from tesseraline_invariants.ports.input_source import InputSource
    from tesseraline_invariants.ports.regression_store import RegressionStore


@dataclass(frozen=True, slots=True)
class Parameter:
    """One parameter of a promised function."""

    name: str
    annotation: object
    dependency: bool


def plan(function: Callable[..., object]) -> list[Parameter]:
    """Split a function's parameters into data and dependencies.

    :param function: a promised function whose annotations resolve.
    :returns: parameters in signature order.

    Examples:
        >>> from typing import Protocol
        >>> class Repo(Protocol):
        ...     def get(self) -> int: ...
        >>> def f(repo: Repo, n: int) -> int: ...
        >>> [(p.name, p.dependency) for p in plan(f)]
        [('repo', True), ('n', False)]
    """
    hints = typing.get_type_hints(function, include_extras=True)
    return [
        Parameter(name, hints[name], _is_protocol(hints[name]))
        for name in inspect.signature(function).parameters
    ]


def fakes_for(params: list[Parameter], source: InputSource) -> dict[str, object] | str:
    """A fake for every dependency, or the reason the promise cannot be checked.

    :param params: the function's parameters.
    :param source: where the user's fakes come from.
    :returns: {parameter name: fake}, or "no fake for X".
    """
    found: dict[str, object] = {}
    for p in params:
        if p.dependency:
            fake = source.fake_for(p.annotation)  # type: ignore[arg-type]
            if fake is None:
                return f"no fake for {getattr(p.annotation, '__name__', p.annotation)}"
            found[p.name] = fake
    return found


def known_inputs(
    params: list[Parameter],
    promise_id: str,
    source: InputSource,
    store: RegressionStore,
    limit: int,
) -> list[dict[str, object]]:
    """Saved regressions first, then every combination of factory examples, up to the limit.

    :param params: the function's parameters.
    :param promise_id: whose regressions to replay.
    :param source: the user's factories.
    :param store: saved regressions.
    :param limit: at most this many inputs.
    :returns: encoded inputs for the data parameters.
    """
    data = [p for p in params if not p.dependency]
    found = list(store.load(promise_id))
    per_param: list[list[object]] = []
    for p in data:
        try:
            per_param.append([encode(p.annotation, v) for v in source.examples(p.annotation)])
        except CodecError:
            per_param.append([])
    if all(per_param):
        combos = itertools.islice(itertools.product(*per_param), limit)
        found.extend({p.name: v for p, v in zip(data, combo, strict=True)} for combo in combos)
    return found[:limit]


def strategy_for(params: list[Parameter]) -> st.SearchStrategy[dict[str, object]] | str:
    """A Hypothesis strategy for the data parameters, or why none can be built.

    :param params: the function's parameters.
    :returns: a strategy producing {parameter name: typed value}, or the reason.
    """
    fields: dict[str, st.SearchStrategy[object]] = {}
    for p in params:
        if p.dependency:
            continue
        try:
            strategy: st.SearchStrategy[object] = st.from_type(p.annotation)  # type: ignore[arg-type]
            strategy.validate()
        except Exception as error:
            return f"Hypothesis cannot build {p.annotation!r} ({type(error).__name__})"
        fields[p.name] = strategy
    return st.fixed_dictionaries(fields)


def _is_protocol(annotation: object) -> bool:
    return isinstance(annotation, type) and bool(getattr(annotation, "_is_protocol", False))
