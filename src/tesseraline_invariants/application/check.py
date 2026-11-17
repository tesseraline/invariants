"""One whole check: compare with the lock, check every promise, audit, decide the exit code.

`tesseraline-invariants/src/tesseraline_invariants/application/check.py`

Two channels: the developer log gets structlog events, the audit sink gets
one record per promise. Both carry promise ids, outcomes, counts, input hashes and canary ids only,
never a value. Exit codes: 0 every promise holds, 1 a promise broke (or, in strict mode, one was not
checked), 2 a promise was removed or changed without `lock --update`. Configuration errors (exit 3)
are raised before this runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from tesseraline_invariants.application.lock import LockDiff, compare
from tesseraline_invariants.application.runner import check_promise
from tesseraline_invariants.domain.promise import CheckResult, Outcome

if TYPE_CHECKING:
    from tesseraline_invariants.application.registry import Registered
    from tesseraline_invariants.application.runner import RunnerSettings
    from tesseraline_invariants.ports.audit_sink import AuditSink
    from tesseraline_invariants.ports.clock import Clock
    from tesseraline_invariants.ports.lock_store import LockStore

AUDIT_SCHEMA = 1
log = structlog.get_logger("tesseraline_invariants")


@dataclass(frozen=True, slots=True)
class Report:
    """Everything a check found, and the exit code it means."""

    results: tuple[CheckResult, ...]
    diff: LockDiff
    strict: bool

    @property
    def exit_code(self) -> int:
        """0, 1 or 2 as documented at the top of this module."""
        if self.diff.blocks:
            return 2
        if any(r.outcome is Outcome.BROKEN for r in self.results):
            return 1
        if self.strict and any(r.outcome is Outcome.NOT_CHECKED for r in self.results):
            return 1
        return 0


@dataclass(frozen=True, slots=True)
class Records:
    """Where a check writes: the lock it compares with, the audit sink, the clock, the version."""

    lock: LockStore
    audit: AuditSink
    clock: Clock
    code_version: str


def run_check(
    items: list[Registered],
    run: RunnerSettings,
    records: Records,
    strict: bool,
    only: set[str] | None = None,
) -> Report:
    """Check every promise and record the outcome.

    :param items: the registered promises (from the modules named in settings).
    :param run: inputs, regressions, secret rules, isolation and limits.
    :param records: lock, audit sink, clock and code version.
    :param strict: a "not checked" promise fails the run.
    :param only: check just these ids (`--since`); the lock is still compared with every promise.
    :returns: the report; its exit_code is what the command returns.
    """
    diff = compare([i.promise for i in items], records.lock.read())
    for old, new in diff.changed:
        log.warning("promise_changed", promise_id=new, previous_id=old)
    for removed in diff.removed:
        log.warning("promise_removed", promise_id=removed)
    results = []
    for item in items:
        if only is not None and item.promise.promise_id not in only:
            continue
        result = check_promise(item, run)
        results.append(result)
        _log(result)
        records.audit.write(audit_record(result, records))
    return Report(tuple(results), diff, strict)


def _log(result: CheckResult) -> None:
    canary = result.violation.canary_id if result.violation else ""
    event = {Outcome.PASSED: "promise_check_passed", Outcome.BROKEN: "promise_check_failed"}.get(
        result.outcome, "promise_check_not_checked"
    )
    log.info(
        event,
        promise_id=result.promise_id,
        calls=result.calls,
        input_hash=result.input_hash,
        canary_id=canary,
        reason=result.reason,
    )


def audit_record(result: CheckResult, records: Records) -> dict[str, object]:
    """One audit record (schema 1): ids, outcome, counts and hashes, never a value."""
    return {
        "schema": AUDIT_SCHEMA,
        "time": records.clock.now(),
        "code_version": records.code_version,
        "promise": result.promise_id,
        "outcome": result.outcome.value,
        "reason": result.reason,
        "calls": result.calls,
        "input_hash": result.input_hash,
        "canary_id": result.violation.canary_id if result.violation else "",
    }
