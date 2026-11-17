"""Unit tests for encoding, planting canaries and building inputs.

`tesseraline-invariants/tests/unit/test_inputs.py`
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pytest
from hypothesis import given, settings
from pydantic import BaseModel, SecretStr

from tesseraline_invariants import Secret
from tesseraline_invariants.adapters.catalogue_inputs import CatalogueInputs
from tesseraline_invariants.adapters.file_regression_store import FileRegressionStore
from tesseraline_invariants.application.codec import CodecError, decode, encode, input_hash, plant
from tesseraline_invariants.application.inputs import fakes_for, known_inputs, plan, strategy_for
from tesseraline_invariants.application.secret_fields import SecretRules, find_secret_fields


@dataclass(frozen=True, slots=True)
class Handle:
    table: str
    credentials: Secret[str]


@dataclass(frozen=True, slots=True)
class Batch:
    handles: list[Handle]


class Login(BaseModel):
    user: str
    password: SecretStr


class Clock(Protocol):
    def now(self) -> int: ...


class FixedClock:
    def now(self) -> int:
        return 0


def plant_into(annotation: object, value: object, name: str) -> tuple[object, list[str]]:
    data = {name: encode(annotation, value)}
    fields = find_secret_fields(annotation, SecretRules(), name)
    planted, canaries = plant(data, fields, seed=5)
    return decode(annotation, planted[name]), [c.value for c in canaries]  # type: ignore[index]


def test_canary_reaches_a_frozen_dataclass() -> None:
    rebuilt, values = plant_into(Handle, Handle("t", "real-looking"), "h")
    assert isinstance(rebuilt, Handle)
    assert rebuilt.credentials == values[0]
    assert rebuilt.table == "t"


def test_canary_reaches_every_item_of_a_list() -> None:
    rebuilt, values = plant_into(Batch, Batch([Handle("a", "x"), Handle("b", "y")]), "b")
    assert [h.credentials for h in rebuilt.handles] == [values[0], values[0]]  # type: ignore[attr-defined]


def test_canary_reaches_a_pydantic_secret() -> None:
    rebuilt, values = plant_into(Login, Login(user="u", password=SecretStr("p")), "login")
    assert rebuilt.password.get_secret_value() == values[0]  # type: ignore[attr-defined]


def test_unbuildable_type_is_a_codec_error() -> None:
    class Opaque:
        pass

    with pytest.raises(CodecError) as caught:
        encode(Opaque, Opaque())
    assert caught.value.annotation is Opaque


def test_input_hash_is_stable_and_short() -> None:
    assert input_hash({"a": [1, 2]}) == input_hash({"a": [1, 2]})
    assert len(input_hash({"a": 1})) == 16


def test_plan_fakes_and_missing_fake() -> None:
    def f(clock: Clock, handle: Handle) -> str:
        return handle.table

    params = plan(f)
    assert [p.dependency for p in params] == [True, False]
    found = fakes_for(params, CatalogueInputs({}, {Clock: FixedClock}))
    assert isinstance(found, dict)
    assert isinstance(found["clock"], FixedClock)
    assert fakes_for(params, CatalogueInputs({}, {})) == "no fake for Clock"


def test_known_inputs_regressions_first_then_factories(tmp_path: Path) -> None:
    def f(handle: Handle) -> str:
        return handle.table

    store = FileRegressionStore(tmp_path)
    store.save("p", {"handle": {"table": "old", "credentials": "c"}})
    source = CatalogueInputs({Handle: lambda: [Handle("a", "x"), Handle("b", "y")]}, {})
    got = known_inputs(plan(f), "p", source, store, limit=10)
    assert [g["handle"]["table"] for g in got] == ["old", "a", "b"]  # type: ignore[index]


def test_known_inputs_respect_the_limit(tmp_path: Path) -> None:
    def f(n: int) -> int:
        return n

    source = CatalogueInputs({int: lambda: list(range(50))}, {})
    assert len(known_inputs(plan(f), "p", source, FileRegressionStore(tmp_path), limit=7)) == 7


def test_strategy_for_simple_and_dataclass_types() -> None:
    def f(handle: Handle, n: int) -> str:
        return ""

    strategy = strategy_for(plan(f))
    assert not isinstance(strategy, str)

    @given(strategy)
    @settings(max_examples=5, database=None)
    def check(example: dict[str, object]) -> None:
        assert isinstance(example["handle"], Handle)
        assert isinstance(example["n"], int)

    check()
