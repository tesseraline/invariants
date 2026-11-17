"""The test items of the pytest plugin: one per promise, one for the lock (needs the "check" extra).

`tesseraline-invariants/src/tesseraline_invariants/entrypoints/pytest_items.py`

Off unless `--invariants` is given. Then each promise is an item: broken fails with the summary
(never a secret value), not checked is skipped with its reason, or fails with `--invariants-strict`;
one more item fails when a promise was removed or changed without `invariants lock --update`. Same
runner, settings and audit sink as the `invariants` command.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tesseraline_invariants.application.check import Records, audit_record
from tesseraline_invariants.application.lock import compare
from tesseraline_invariants.application.registry import DEFAULT_REGISTRY
from tesseraline_invariants.application.runner import check_promise
from tesseraline_invariants.domain.exceptions import ConfigurationError
from tesseraline_invariants.domain.promise import Outcome
from tesseraline_invariants.infrastructure.factory import prepare

if TYPE_CHECKING:
    from tesseraline_invariants.application.registry import Registered
    from tesseraline_invariants.application.runner import RunnerSettings


class PromiseBrokenError(Exception):
    """Raised by a promise item when its promise broke; pytest shows the summary only."""

    def __init__(self, summary: str, input_hash: str) -> None:
        """Keep the log-safe summary and the hash of the saved minimal input.

        :param summary: the violation's summary (never a value).
        :param input_hash: the saved regression's input hash.
        """
        super().__init__(f"{summary}; minimal input saved (input {input_hash})")
        self.summary, self.input_hash = summary, input_hash


def collect(session: pytest.Session, config: pytest.Config, items: list[pytest.Item]) -> None:
    """Append one item per promise, and one for the lock."""
    project = Path(config.getoption("--invariants-project") or config.rootpath).resolve()
    try:
        _settings, run, records = prepare(project)
    except ConfigurationError as error:
        items.append(
            SetupItem.from_parent(session, name="invariants[configuration]", message=str(error))
        )
        return
    strict = bool(config.getoption("--invariants-strict"))
    registered = DEFAULT_REGISTRY.all()
    items.append(
        LockItem.from_parent(
            session, name="invariants[lock]", registered=registered, records=records
        )
    )
    for item in registered:
        name = f"invariants[{item.promise.promise_id}]"
        items.append(
            PromiseItem.from_parent(
                session, name=name, item=item, run=run, records=records, strict=strict
            )
        )


class PromiseItem(pytest.Item):
    """One promise as one test."""

    def __init__(
        self,
        *,
        item: Registered,
        run: RunnerSettings,
        records: Records,
        strict: bool,
        **kwargs: object,
    ) -> None:
        """Keep what the check needs."""
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.promise_item, self.run, self.records, self.strict = item, run, records, strict

    def runtest(self) -> None:
        """Check the promise, write its audit record, fail or skip as the outcome says."""
        result = check_promise(self.promise_item, self.run)
        self.records.audit.write(audit_record(result, self.records))
        if result.outcome is Outcome.BROKEN:
            raise PromiseBrokenError(result.reason, result.input_hash)
        if result.outcome is Outcome.NOT_CHECKED:
            if self.strict:
                pytest.fail(f"not checked: {result.reason}", pytrace=False)
            pytest.skip(f"not checked: {result.reason}")

    def repr_failure(
        self,
        excinfo: pytest.ExceptionInfo[BaseException],
        style: object = None,  # noqa: ARG002
    ) -> str:
        """The summary only: no traceback, never input data."""
        return str(excinfo.value)

    def reportinfo(self) -> tuple[Path, int, str]:
        """Where the item points: the promised function's file."""
        code = getattr(self.promise_item.function, "__code__", None)
        path = Path(code.co_filename) if code else Path()
        return path, (code.co_firstlineno - 1) if code else 0, self.name


class LockItem(pytest.Item):
    """Fails when a promise was removed or changed without `invariants lock --update`."""

    def __init__(self, *, registered: list[Registered], records: Records, **kwargs: object) -> None:
        """Keep the promises and the lock."""
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.registered, self.records = registered, records

    def runtest(self) -> None:
        """Compare the code's promises with the lock."""
        diff = compare([r.promise for r in self.registered], self.records.lock.read())
        if diff.blocks:
            lines = [f"removed: {r}" for r in diff.removed] + [
                f"changed: {n} (was {o})" for o, n in diff.changed
            ]
            pytest.fail(
                "\n".join([*lines, "accept with `invariants lock --update`"]), pytrace=False
            )

    def reportinfo(self) -> tuple[Path, int, str]:
        """Where the item points: the lock."""
        return Path("invariants.lock"), 0, self.name


class SetupItem(pytest.Item):
    """Reports a configuration error as one failing test."""

    def __init__(self, *, message: str, **kwargs: object) -> None:
        """Keep the message."""
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.message = message

    def runtest(self) -> None:
        """Fail with the configuration error."""
        pytest.fail(f"configuration error: {self.message}", pytrace=False)

    def reportinfo(self) -> tuple[Path, int, str]:
        """Where the item points: pyproject.toml."""
        return Path("pyproject.toml"), 0, self.name
