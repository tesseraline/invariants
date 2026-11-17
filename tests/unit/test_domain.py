"""Unit tests for the domain: canaries, preservation, the three kinds, the Secret mark, errors.

`tesseraline-invariants/tests/unit/test_domain.py`
"""

import base64
import json
from typing import Annotated
from urllib.parse import quote

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tesseraline_invariants.domain.canary import found_in, make_canary
from tesseraline_invariants.domain.exceptions import (
    DeclarationError,
    InvariantsError,
    UntrackablePayloadError,
)
from tesseraline_invariants.domain.kinds import Holds, NeverContains, Preserves
from tesseraline_invariants.domain.preservation import Kind, difference, extract
from tesseraline_invariants.domain.promise import Call, Promise
from tesseraline_invariants.domain.secret import Secret, carries_secret_mark

CANARY = make_canary(seed=11, index=2, field="Handle.credentials")


def test_canary_is_deterministic_and_carries_no_separator() -> None:
    assert make_canary(11, 2) == make_canary(11, 2).__class__(CANARY.canary_id, CANARY.value)
    assert CANARY.value.isalnum()


@given(prefix=st.text(max_size=40), suffix=st.text(max_size=40))
def test_canary_found_in_base64_whatever_surrounds_it(prefix: str, suffix: str) -> None:
    blob = base64.b64encode((prefix + CANARY.value + suffix).encode()).decode()
    assert found_in(blob, CANARY) == "base64"


@pytest.mark.parametrize(
    ("text", "form"),
    [
        (f"token={CANARY.value}", "plain"),
        (json.dumps({"k": CANARY.value}), "plain"),
        (quote(f"a b/{CANARY.value}", safe=""), "plain"),
        ("nothing", None),
    ],
)
def test_canary_forms(text: str, form: str | None) -> None:
    assert found_in(text, CANARY) == form


def test_canary_is_not_found_when_truncated() -> None:
    """A stated limit: truncation hides it."""
    assert found_in(CANARY.value[:-6], CANARY) is None


@pytest.mark.parametrize(
    ("kind", "text", "expected"),
    [
        (Kind.NUMBERS, "1,000 and 1000", ["1000", "1000"]),
        (Kind.NUMBERS, "15 percent, 15 per cent, 15pct, 15%", ["15%"] * 4),
        (Kind.NUMBERS, "on 2026-11-17 it rose 3", ["3"]),
        (Kind.DATES, "November 17, 2026 / 17 November 2026", ["2026-11-17", "2026-11-17"]),
        (Kind.DATES, "31 Smarch 2026", []),
        (Kind.QUOTES, 'he said "no" and “yes”', ["no", "yes"]),
        (Kind.LINKS, "see https://a.example/x.", ["https://a.example/x"]),
    ],
)
def test_extract(kind: Kind, text: str, expected: list[str]) -> None:
    assert sorted(extract(kind, text).elements()) == sorted(expected)


def test_difference_one_way_ignores_new_items() -> None:
    assert difference(Kind.NUMBERS, "1", "1 2", both_ways=False) == ([], [])
    assert difference(Kind.NUMBERS, "1", "1 2", both_ways=True) == ([], ["2"])


def test_never_contains_names_the_field_never_the_value() -> None:
    v = NeverContains(("Secret",)).judge(Call((), None, "", f"x{CANARY.value}", (CANARY,)))
    assert v is not None
    assert CANARY.value not in v.summary + v.detail
    assert v.canary_id == CANARY.canary_id


def test_preserves_reports_counts_in_summary_and_items_in_detail() -> None:
    v = Preserves((Kind.NUMBERS,)).judge(Call((), None, "15% of 200", "15% of 300"))
    assert v is not None
    assert v.summary == "numbers: 1 lost, 1 new"
    assert "200" in v.detail


def test_holds_turns_a_raising_predicate_into_a_violation() -> None:
    def boom(_i: object, _o: object) -> bool:
        raise ZeroDivisionError

    v = Holds(boom, "boom", "h").judge(Call((1, 2), 3, "", ""))
    assert v is not None
    assert v.summary == "boom raised ZeroDivisionError"


def test_secret_mark_recognised_in_all_spellings() -> None:
    assert carries_secret_mark(Secret[str])
    assert carries_secret_mark(Annotated[str, Secret])
    assert carries_secret_mark(Secret[str] | None)
    assert not carries_secret_mark(Annotated[str, "other"])


def test_promise_id_changes_with_parameters() -> None:
    a = Promise("m:f", "preserves", (("kinds", "numbers"),))
    b = Promise("m:f", "preserves", (("kinds", "dates"),))
    assert a.promise_id != b.promise_id
    assert a.lock_entry()["params"] == {"kinds": "numbers"}


def test_errors_share_one_base_and_carry_data() -> None:
    err = UntrackablePayloadError("m.f", "payload", "dict")
    assert isinstance(err, DeclarationError)
    assert isinstance(err, InvariantsError)
    assert (err.function, err.name, err.annotation) == ("m.f", "payload", "dict")
