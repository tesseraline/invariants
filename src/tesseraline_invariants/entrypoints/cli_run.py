"""The heavy half of the `invariants` command: check, list, lock, impact (needs the "check" extra).

`tesseraline-invariants/src/tesseraline_invariants/entrypoints/cli_run.py`

Exit codes: 0 every promise holds, 1 a promise broke (or was not checked in strict mode), 2 a
promise was removed or changed without `lock --update`, 3 configuration or import error. The
terminal shows the violation's detail (it can hold input data); logs and the audit record never do.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from tesseraline_invariants.application.check import run_check
from tesseraline_invariants.application.impact import affected
from tesseraline_invariants.application.lock import compare, entries
from tesseraline_invariants.application.registry import DEFAULT_REGISTRY
from tesseraline_invariants.domain.exceptions import ConfigurationError
from tesseraline_invariants.domain.promise import Outcome
from tesseraline_invariants.infrastructure.changes import changed_files, project_modules
from tesseraline_invariants.infrastructure.factory import prepare

if TYPE_CHECKING:
    import argparse

    from tesseraline_invariants.application.check import Records, Report
    from tesseraline_invariants.application.registry import Registered

CONFIG_ERROR = 3


def run(args: argparse.Namespace) -> int:
    """Run a command that needs the check machinery and return its exit code.

    :param args: parsed arguments from `cli.parser()`.
    :returns: the exit code.
    """
    level = logging.INFO if args.verbose else logging.WARNING
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(sys.stderr),
    )
    project = Path(args.project).resolve()
    try:
        settings, run, records = prepare(project)
        only = _affected_ids(args, project)
    except ConfigurationError as error:
        print(f"configuration error: {error}")
        return CONFIG_ERROR
    items = DEFAULT_REGISTRY.all()
    if args.command == "impact":
        return 0
    if args.command == "list":
        _print_list(items)
        return 0
    if args.command == "lock":
        _update_lock(items, records)
        return 0
    report = run_check(items, run, records, strict=args.strict or settings.strict, only=only)
    _print_report(report)
    return report.exit_code


def _affected_ids(args: argparse.Namespace, project: Path) -> set[str] | None:
    """For --since: print (impact) or return (check) the promises a change may affect."""
    since = getattr(args, "since", "")
    if not since and args.command != "impact":
        return None
    items = DEFAULT_REGISTRY.all()
    hits = affected(items, changed_files(project, since), project_modules(project))
    if args.command == "impact":
        for hit in hits:
            print(f"MAY BE AFFECTED  {hit.promise_id}: {hit.reason}")
        print(f"{len(hits)} of {len(items)} promises may be affected since {since}")
    return {h.promise_id for h in hits}


def _print_list(items: list[Registered]) -> None:
    for item in items:
        how = "dry_run" if item.promise.dry_run else "not called: dry_run not declared"
        print(f"{item.promise.promise_id}  ({how})")


def _update_lock(items: list[Registered], records: Records) -> None:
    diff = compare([i.promise for i in items], records.lock.read())
    records.lock.write(entries([i.promise for i in items]))
    print(
        f"invariants.lock updated: {len(items)} promises, {len(diff.added)} added, "
        f"{len(diff.removed)} removed, {len(diff.changed)} changed (review the diff)"
    )


def _print_report(report: Report) -> None:
    for removed in report.diff.removed:
        print(f"REMOVED      {removed}  (only `invariants lock --update` accepts this)")
    for old, new in report.diff.changed:
        print(f"CHANGED      {new}  (was {old}; `invariants lock --update` to accept)")
    for r in report.results:
        if r.outcome is Outcome.PASSED:
            print(f"PASS         {r.promise_id}  ({r.calls} calls)")
        elif r.outcome is Outcome.BROKEN:
            saved = f"minimal input saved (input {r.input_hash})"
            print(f"BROKEN       {r.promise_id}: {r.reason}; {saved}")
            if r.violation and r.violation.detail:
                print(f"             {r.violation.detail}")
        else:
            print(f"NOT CHECKED  {r.promise_id}: {r.reason}")
    for added in report.diff.added:
        print(f"NEW          {added}  (record it with `invariants lock --update`)")
    counts = {o: sum(r.outcome is o for r in report.results) for o in Outcome}
    print(
        f"{counts[Outcome.PASSED]} passed, {counts[Outcome.BROKEN]} broken, "
        f"{counts[Outcome.NOT_CHECKED]} not checked; exit {report.exit_code}"
    )
