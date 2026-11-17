"""The three kinds of invariant: never_contains, preserves, holds.

`tesseraline-invariants/src/tesseraline_invariants/domain/kinds.py`

Each kind judges one `Call` and returns a `Violation` or None. Which fields get canaries, how output
becomes text and which inputs are tried is the application layer's job; the kinds only judge.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tesseraline_invariants.domain.canary import found_in
from tesseraline_invariants.domain.preservation import Kind, difference
from tesseraline_invariants.domain.promise import Call, Violation

type Predicate = Callable[[object, object], bool]


@dataclass(frozen=True, slots=True)
class NeverContains:
    """No planted secret leaves: not in the output, a log event, or what a dependency received.

    Examples:
        >>> from tesseraline_invariants.domain.canary import make_canary
        >>> c = make_canary(1, 0, "Handle.credentials")
        >>> NeverContains(("Secret",)).judge(Call((), None, "", "{}", (c,))) is None
        True
        >>> NeverContains(("Secret",)).judge(Call((), None, "", c.value, (c,))).summary
        'secret from Handle.credentials found in the output (plain)'
    """

    markers: tuple[str, ...]
    kind: str = "never_contains"

    def params(self) -> tuple[tuple[str, str], ...]:
        """What the lock records about this invariant."""
        return (("markers", ",".join(sorted(self.markers))),)

    def judge(self, call: Call) -> Violation | None:
        """Search the output, then every other exit, for every canary planted in the input."""
        places = (("the output", call.output_text), *call.exits)
        for canary in call.canaries:
            for where, text in places:
                form = found_in(text, canary)
                if form:
                    return Violation(
                        summary=f"secret from {canary.field} found in {where} ({form})",
                        canary_id=canary.canary_id,
                    )
        return None


@dataclass(frozen=True, slots=True)
class Preserves:
    """Every number, date, quote or link of the input survives; by default nothing new appears.

    Examples:
        >>> p = Preserves((Kind.NUMBERS,), both_ways=True)
        >>> p.judge(Call((), None, "rose 15%", "rose 51%")).summary
        'numbers: 1 lost, 1 new'
    """

    kinds: tuple[Kind, ...]
    both_ways: bool = True
    kind: str = "preserves"

    def params(self) -> tuple[tuple[str, str], ...]:
        """What the lock records about this invariant."""
        return (("kinds", ",".join(sorted(self.kinds))), ("both_ways", str(self.both_ways).lower()))

    def judge(self, call: Call) -> Violation | None:
        """Compare the input text with the output text for each kind."""
        for k in self.kinds:
            lost, new = difference(k, call.input_text, call.output_text, self.both_ways)
            if lost or new:
                return Violation(
                    summary=f"{k}: {len(lost)} lost, {len(new)} new",
                    detail=f"{k}: lost {lost}, new {new}",
                )
        return None


@dataclass(frozen=True, slots=True)
class Holds:
    """A predicate over the input and the output is true.

    Examples:
        >>> h = Holds(lambda i, o: o == i * 2, "double", "abc123")
        >>> h.judge(Call((3,), 6, "3", "6")) is None
        True
        >>> h.judge(Call((3,), 7, "3", "7")).summary
        'double is false'
    """

    predicate: Predicate
    name: str
    source_hash: str
    kind: str = "holds"

    def params(self) -> tuple[tuple[str, str], ...]:
        """What the lock records: the predicate's name and a hash of its source (an edit shows)."""
        return (("predicate", self.name), ("source", self.source_hash))

    def judge(self, call: Call) -> Violation | None:
        """Call the predicate with the input (one value, or a tuple of several) and the output."""
        given = call.inputs[0] if len(call.inputs) == 1 else call.inputs
        try:
            ok = self.predicate(given, call.output)
        except Exception as error:  # a failing predicate is a broken promise
            return Violation(summary=f"{self.name} raised {type(error).__name__}")
        return None if ok else Violation(summary=f"{self.name} is false")


type Invariant = NeverContains | Preserves | Holds
