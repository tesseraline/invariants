"""Unit tests for finding secret fields.

`tesseraline-invariants/tests/unit/test_secret_fields.py`
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated

import attrs
import pytest
from pydantic import BaseModel, SecretStr

from tesseraline_invariants import Secret
from tesseraline_invariants.application.secret_fields import (
    SecretRules,
    Strength,
    find_secret_fields,
)
from tesseraline_invariants.domain.exceptions import DeclarationError


class Token(str):
    """A team's own secret type."""


@dataclass
class Handle:
    table: str
    credentials: Secret[str]
    note: Annotated[str, Secret] = ""


@dataclass
class Batch:
    handles: list[Handle]
    owner: Handle | None = None
    by_name: dict[str, Handle] = field(default_factory=dict)


@dataclass
class Node:
    name: str
    parent: Node | None = None


class Login(BaseModel):
    user: str
    password: SecretStr
    pin: Annotated[str, Secret]


@dataclass
class Mixed:
    api_key: str
    session: Token
    flagged: str = field(default="", metadata={"secret": True})
    plain: str = ""


@attrs.define
class AttrsHandle:
    key: str = attrs.field(metadata={"secret": True})
    name: str = ""


class OnlyPlainRule:
    def is_secret(self, owner: type, field: str) -> bool:
        return owner is Mixed and field == "plain"


NO_RULES = SecretRules()


def paths(root: object, rules: SecretRules = NO_RULES, prefix: str = "x") -> list[str]:
    return [f.dotted for f in find_secret_fields(root, rules, prefix)]


def test_our_marker_in_both_spellings() -> None:
    assert paths(Handle) == ["x.credentials", "x.note"]


def test_nested_through_lists_optionals_and_dict_values() -> None:
    assert paths(Batch) == [
        "x.by_name[].credentials",
        "x.by_name[].note",
        "x.handles[].credentials",
        "x.handles[].note",
        "x.owner.credentials",
        "x.owner.note",
    ]


def test_cycles_stop() -> None:
    assert paths(Node) == []


def test_pydantic_secret_types_and_marker() -> None:
    found = {f.dotted: f.rule for f in find_secret_fields(Login, SecretRules(), "login")}
    assert found == {"login.password": "Pydantic SecretStr", "login.pin": "Secret marker"}


def test_user_types_metadata_hook_and_names() -> None:
    rules = SecretRules(types=(Token,), name_patterns=("*key*",), hooks=(OnlyPlainRule(),))
    found = {f.dotted: (f.rule, f.strength) for f in find_secret_fields(Mixed, rules, "m")}
    assert found == {
        "m.api_key": ("secret by name", Strength.HEURISTIC),
        "m.session": ("secret type Token", Strength.EXACT),
        "m.flagged": ("field metadata", Strength.EXACT),
        "m.plain": ("custom rule", Strength.CUSTOM),
    }


def test_name_patterns_are_off_by_default() -> None:
    assert paths(Mixed) == ["x.flagged"]


def test_a_field_marked_several_ways_is_reported_once_with_the_strongest_rule() -> None:
    @dataclass
    class Both:
        api_key: Secret[str]

    found = find_secret_fields(Both, SecretRules(name_patterns=("api_key",)), "b")
    assert [(f.dotted, f.strength) for f in found] == [("b.api_key", Strength.EXACT)]


def test_attrs_metadata() -> None:
    assert paths(AttrsHandle) == ["x.key"]


def test_return_value_walks_without_a_prefix() -> None:
    assert paths(list[Handle], prefix="") == ["[].credentials", "[].note"]


def test_unresolvable_hints_fail_loudly_instead_of_hiding_a_secret() -> None:
    @dataclass
    class Local:
        hidden: Missing  # type: ignore[name-defined]  # noqa: F821

    with pytest.raises(DeclarationError):
        find_secret_fields(Local, NO_RULES, "x")
