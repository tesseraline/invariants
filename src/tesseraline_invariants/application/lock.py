"""Compare the promises in the code with those recorded in `invariants.lock` (decision 0009).

`tesseraline-invariants/src/tesseraline_invariants/application/lock.py`

A promise that is in the lock but no longer in the code was removed; one whose function and kind
remain but whose parameters changed was changed (possibly weakened). Both fail with exit 2 until
`lock --update` records them, so deleting a decorator to get a green build shows in review.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tesseraline_invariants.domain.promise import Promise


@dataclass(frozen=True, slots=True)
class LockDiff:
    """What differs between the code and the lock."""

    removed: tuple[str, ...] = ()
    changed: tuple[tuple[str, str], ...] = ()
    added: tuple[str, ...] = ()

    @property
    def blocks(self) -> bool:
        """True when a promise was removed or changed: exit 2 until the lock is updated."""
        return bool(self.removed or self.changed)


def compare(current: list[Promise], recorded: list[dict[str, object]]) -> LockDiff:
    """Compare promises in the code with lock entries.

    :param current: promises collected from the code.
    :param recorded: entries read from the lock.
    :returns: removed ids, (old id, new id) pairs for changed ones, added ids.

    Examples:
        >>> from tesseraline_invariants.domain.promise import Promise
        >>> a = Promise("m:f", "preserves", (("kinds", "numbers"),))
        >>> b = Promise("m:f", "preserves", (("kinds", "dates"),))
        >>> compare([b], [a.lock_entry()]).changed == ((a.promise_id, b.promise_id),)
        True
        >>> compare([], [a.lock_entry()]).removed == (a.promise_id,)
        True
    """
    now = {p.promise_id: p for p in current}
    old = {str(e.get("id")): e for e in recorded}
    gone = [i for i in old if i not in now]
    new = [i for i in now if i not in old]
    changed: list[tuple[str, str]] = []
    for old_id in list(gone):
        entry = old[old_id]
        match = next(
            (
                n
                for n in new
                if (now[n].function, now[n].kind) == (entry.get("function"), entry.get("kind"))
            ),
            None,
        )
        if match:
            changed.append((old_id, match))
            gone.remove(old_id)
            new.remove(match)
    return LockDiff(tuple(sorted(gone)), tuple(sorted(changed)), tuple(sorted(new)))


def entries(current: list[Promise]) -> list[dict[str, object]]:
    """The lock entries for the promises in the code, for `lock --update`."""
    return [p.lock_entry() for p in current]
