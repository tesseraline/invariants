"""A promise, one call of the promised function, and the result of checking it.

`tesseraline-invariants/src/tesseraline_invariants/domain/promise.py`

Only `Violation.summary`, ids and hashes may reach a log or the audit record (architecture decision
record 0003); `Violation.detail` can carry data from the input and goes to the terminal and the
regression file only.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tesseraline_invariants.domain.canary import Canary


class Outcome(StrEnum):
    """What a check concluded about one promise."""

    PASSED = "passed"
    BROKEN = "broken"
    NOT_CHECKED = "not_checked"
    REMOVED = "removed"


@dataclass(frozen=True, slots=True)
class Promise:
    """One invariant declared on one function.

    Examples:
        >>> p = Promise("pkg.mod:f", "never_contains", (("markers", "Secret"),), dry_run=True)
        >>> p.promise_id.startswith("pkg.mod:f#never_contains:")
        True
    """

    function: str
    kind: str
    params: tuple[tuple[str, str], ...]
    dry_run: bool = False

    @property
    def promise_id(self) -> str:
        """Stable id: function, kind and a short hash of the parameters."""
        digest = hashlib.sha256(json.dumps(self.params, sort_keys=True).encode()).hexdigest()[:8]
        return f"{self.function}#{self.kind}:{digest}"

    def lock_entry(self) -> dict[str, object]:
        """The line this promise takes in invariants.lock (sorted keys, no secrets)."""
        return {
            "id": self.promise_id,
            "function": self.function,
            "kind": self.kind,
            "params": dict(self.params),
        }


@dataclass(frozen=True, slots=True)
class Call:
    """One call of a promised function, as an invariant sees it."""

    inputs: tuple[object, ...]
    output: object
    input_text: str
    output_text: str
    canaries: tuple[Canary, ...] = ()
    exits: tuple[tuple[str, str], ...] = ()  # (where, text): logs and what dependencies received


@dataclass(frozen=True, slots=True)
class Violation:
    """Why a promise broke: a summary safe for logs, a detail for the developer only."""

    summary: str
    detail: str = ""
    canary_id: str = ""


@dataclass(frozen=True, slots=True)
class CheckResult:
    """The result for one promise in one check."""

    promise_id: str
    outcome: Outcome
    reason: str = ""
    calls: int = 0
    input_hash: str = ""
    violation: Violation | None = field(default=None)
