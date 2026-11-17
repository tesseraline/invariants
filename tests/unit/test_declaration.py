"""Unit tests for declaring promises: early errors, registry, the public builders.

`tesseraline-invariants/tests/unit/test_declaration.py`
"""

from dataclasses import dataclass
from typing import Any

import pytest

from tesseraline_invariants import Secret, holds, invariant, never_contains, preserves
from tesseraline_invariants.application.registry import PromiseRegistry
from tesseraline_invariants.domain.exceptions import (
    UntrackablePayloadError,
    UntypedBoundaryError,
    UsageError,
)


@dataclass(frozen=True, slots=True)
class Handle:
    table: str
    credentials: Secret[str]


@pytest.fixture
def reg() -> PromiseRegistry:
    return PromiseRegistry()


def test_decorator_returns_the_same_function_and_registers_each_promise(
    reg: PromiseRegistry,
) -> None:
    def to_json(handle: Handle) -> str:
        return handle.table

    decorated = invariant(never_contains(Secret), preserves("numbers"), dry_run=True, registry=reg)(
        to_json
    )
    assert decorated is to_json
    kinds = sorted(r.promise.kind for r in reg.all())
    assert kinds == ["never_contains", "preserves"]
    assert all(r.promise.dry_run for r in reg.all())


def test_untyped_parameter_fails_at_decoration(reg: PromiseRegistry) -> None:
    def f(x) -> str:  # type: ignore[no-untyped-def]
        return str(x)

    with pytest.raises(UntypedBoundaryError) as caught:
        invariant(never_contains(Secret), registry=reg)(f)
    assert caught.value.name == "x"


def test_untyped_return_fails_at_decoration(reg: PromiseRegistry) -> None:
    def f(x: int):  # type: ignore[no-untyped-def]
        return x

    with pytest.raises(UntypedBoundaryError) as caught:
        invariant(never_contains(Secret), registry=reg)(f)
    assert caught.value.name == "return"


@pytest.mark.parametrize("annotation", [dict, dict[str, int], Any, object, dict | None])
def test_hiding_annotation_fails_at_decoration(annotation: object, reg: PromiseRegistry) -> None:
    def f(payload: int) -> str:
        return ""

    f.__annotations__["payload"] = annotation
    with pytest.raises(UntrackablePayloadError):
        invariant(never_contains(Secret), registry=reg)(f)


def test_forward_reference_is_registered_as_pending(reg: PromiseRegistry) -> None:
    def f(x: "NotYetDefined") -> str:  # type: ignore[name-defined]  # noqa: F821
        return ""

    invariant(never_contains(Secret), registry=reg)(f)
    assert reg.all()[0].resolved is False


def test_async_function_is_marked(reg: PromiseRegistry) -> None:
    async def f(x: int) -> int:
        return x

    invariant(holds(lambda i, o: o == i), dry_run=True, registry=reg)(f)
    assert reg.all()[0].is_async


def test_builders_reject_mistakes() -> None:
    with pytest.raises(UsageError):
        invariant()
    with pytest.raises(UsageError):
        preserves("colours")


def test_holds_hash_changes_with_the_predicate_source() -> None:
    a = holds(lambda i, o: o == i, name="same")
    b = holds(lambda i, o: o != i, name="same")
    assert a.params() != b.params()
