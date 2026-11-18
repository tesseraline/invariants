"""Unit tests for checking one promise: leaks found, safe code passes, the rest "not checked".

`tesseraline-invariants/tests/unit/test_runner.py`
"""

from __future__ import annotations

import base64
import json
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pytest

from tesseraline_invariants import Secret, holds, invariant, never_contains, preserves
from tesseraline_invariants.adapters.catalogue_inputs import CatalogueInputs
from tesseraline_invariants.adapters.file_regression_store import FileRegressionStore
from tesseraline_invariants.application.registry import PromiseRegistry
from tesseraline_invariants.application.runner import RunnerSettings, check_promise
from tesseraline_invariants.application.secret_fields import SecretRules
from tesseraline_invariants.domain.canary import PREFIX
from tesseraline_invariants.domain.promise import CheckResult, Outcome
from tesseraline_invariants.infrastructure.network_block import blocked_network


@dataclass(frozen=True, slots=True)
class Handle:
    table: str
    credentials: Secret[str]


class Audit(Protocol):
    def record(self, line: str) -> None: ...


class Mailer(Protocol):
    def send(self) -> None: ...


class FakeAudit:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def record(self, line: str) -> None:
        self.lines.append(line)


@pytest.fixture
def run(tmp_path: Path) -> RunnerSettings:
    source = CatalogueInputs({Handle: lambda: Handle("orders", "real-looking")}, {Audit: FakeAudit})
    return RunnerSettings(
        source, FileRegressionStore(tmp_path), SecretRules(), blocked_network, 60, 1
    )


def check(
    function: object, promise: object, run: RunnerSettings, dry_run: bool = True
) -> CheckResult:
    reg = PromiseRegistry()
    invariant(promise, dry_run=dry_run, registry=reg)(function)  # type: ignore[arg-type]
    return check_promise(reg.all()[0], run)


def leaking(handle: Handle) -> str:
    return json.dumps({"table": handle.table, "handle": repr(handle)})


def safe(handle: Handle) -> str:
    return json.dumps({"table": handle.table})


def test_a_leak_is_broken_and_the_case_is_saved(run: RunnerSettings) -> None:
    result = check(leaking, never_contains(Secret), run)
    assert result.outcome is Outcome.BROKEN
    assert result.reason == "secret from handle.credentials found in the output (plain)"
    assert PREFIX not in result.reason
    assert run.store.load(result.promise_id)


def test_a_base64_leak_is_found(run: RunnerSettings) -> None:
    def encoded(handle: Handle) -> str:
        return base64.b64encode(f"{handle.table}:{handle.credentials}".encode()).decode()

    result = check(encoded, never_contains(Secret), run)
    assert result.outcome is Outcome.BROKEN
    assert result.reason.endswith("(base64)")


def test_safe_code_passes_after_many_calls(run: RunnerSettings) -> None:
    result = check(safe, never_contains(Secret), run)
    assert result.outcome is Outcome.PASSED
    assert result.calls > 10


def test_saved_regression_is_replayed_first(run: RunnerSettings) -> None:
    first = check(leaking, never_contains(Secret), run)
    again = check(leaking, never_contains(Secret), run)
    assert again.outcome is Outcome.BROKEN
    assert again.calls == 1
    assert again.input_hash == first.input_hash


@pytest.mark.parametrize(
    ("dry_run", "reason"),
    [(False, "dry_run not declared")],
)
def test_without_dry_run_nothing_is_called(run: RunnerSettings, dry_run: bool, reason: str) -> None:
    called = []

    def f(handle: Handle) -> str:
        called.append(1)
        return ""

    result = check(f, never_contains(Secret), run, dry_run=dry_run)
    assert (result.outcome, result.reason, called) == (Outcome.NOT_CHECKED, reason, [])


def test_a_dependency_gets_its_fake_and_a_missing_fake_is_named(run: RunnerSettings) -> None:
    def with_audit(audit: Audit, handle: Handle) -> str:
        audit.record("exported")
        return handle.table

    assert check(with_audit, never_contains(Secret), run).outcome is Outcome.PASSED

    def with_mailer(mailer: Mailer, handle: Handle) -> str:
        return ""

    result = check(with_mailer, never_contains(Secret), run)
    assert (result.outcome, result.reason) == (Outcome.NOT_CHECKED, "no fake for Mailer")


def test_never_contains_without_any_secret_field_is_not_a_pass(run: RunnerSettings) -> None:
    def plain(n: int) -> str:
        return str(n)

    result = check(plain, never_contains(Secret), run)
    assert result.outcome is Outcome.NOT_CHECKED
    assert "no secret field" in result.reason


def test_network_access_is_blocked_and_named(run: RunnerSettings) -> None:
    def phones_home(handle: Handle) -> str:
        socket.getaddrinfo("telemetry.example", 443)
        return ""

    result = check(phones_home, never_contains(Secret), run)
    assert result.outcome is Outcome.NOT_CHECKED
    assert result.reason == "attempted network access to telemetry.example"


def test_a_function_that_always_raises_is_not_checked(run: RunnerSettings) -> None:
    def refuses(handle: Handle) -> str:
        raise ValueError

    result = check(refuses, never_contains(Secret), run)
    assert (result.outcome, result.reason) == (Outcome.NOT_CHECKED, "every call raised ValueError")


def test_async_functions_run_through_the_same_runner(run: RunnerSettings) -> None:
    async def leaks_async(handle: Handle) -> str:
        return handle.credentials

    assert check(leaks_async, never_contains(Secret), run).outcome is Outcome.BROKEN


def test_preserves_finds_a_changed_number(run: RunnerSettings) -> None:
    def drops_digits(text: str) -> str:
        return "".join(c for c in text if not c.isdigit())

    result = check(drops_digits, preserves("numbers"), run)
    assert result.outcome is Outcome.BROKEN
    assert result.violation is not None
    assert result.reason.startswith("numbers: ")


def test_preserves_passes_on_a_faithful_restyle(run: RunnerSettings) -> None:
    def shout(text: str) -> str:
        return text.upper()

    assert check(shout, preserves("numbers"), run).outcome is Outcome.PASSED


def test_holds_finds_a_wrong_total_and_shrinks_it(run: RunnerSettings) -> None:
    def total(items: list[int]) -> int:
        return sum(items[:3])

    result = check(total, holds(lambda i, o: o == sum(i), name="total adds up"), run)
    assert result.outcome is Outcome.BROKEN
    saved = run.store.load(result.promise_id)[-1]
    assert len(saved["items"]) == 4  # minimal: three are summed, the fourth is lost  # type: ignore[arg-type]


def test_relative_writes_land_in_a_temporary_folder_not_the_project(tmp_path: Path) -> None:
    from tesseraline_invariants.infrastructure.network_block import isolated  # noqa: PLC0415

    workdir = tmp_path / "work"
    workdir.mkdir()
    source = CatalogueInputs({Handle: lambda: Handle("orders", "x")}, {})
    run = RunnerSettings(
        source,
        FileRegressionStore(tmp_path / "reg"),
        SecretRules(),
        lambda: isolated(str(workdir)),
        5,
        1,
    )

    def writes(handle: Handle) -> str:
        Path("side-effect.txt").write_text(handle.table, encoding="utf-8")
        return handle.table

    assert check(writes, never_contains(Secret), run).outcome is Outcome.PASSED
    assert (workdir / "side-effect.txt").is_file()
    assert not Path("side-effect.txt").exists()


def test_a_secret_written_to_a_log_or_handed_to_a_dependency_is_caught(tmp_path: Path) -> None:
    import logging  # noqa: PLC0415

    import structlog  # noqa: PLC0415

    from tesseraline_invariants.infrastructure.capture import captured_exits  # noqa: PLC0415

    source = CatalogueInputs({Handle: lambda: Handle("orders", "x")}, {Audit: FakeAudit})
    run = RunnerSettings(
        source, FileRegressionStore(tmp_path), SecretRules(), blocked_network, 20, 1, captured_exits
    )

    def logs_with_structlog(handle: Handle) -> str:
        structlog.get_logger().info("exported", handle=repr(handle))
        return handle.table

    def logs_with_logging(handle: Handle) -> str:
        logging.getLogger("export").warning("exported %s", handle.credentials)
        return handle.table

    def tells_the_audit(audit: Audit, handle: Handle) -> str:
        audit.record(f"exported {handle}")
        return handle.table

    def careful(audit: Audit, handle: Handle) -> str:
        structlog.get_logger().info("exported", table=handle.table)
        audit.record(f"exported {handle.table}")
        return handle.table

    assert (
        "found in a structlog event"
        in check(logs_with_structlog, never_contains(Secret), run).reason
    )
    assert (
        "found in a standard log record"
        in check(logs_with_logging, never_contains(Secret), run).reason
    )
    assert (
        "found in what FakeAudit received"
        in check(tells_the_audit, never_contains(Secret), run).reason
    )
    assert check(careful, never_contains(Secret), run).outcome is Outcome.PASSED


def test_a_secret_held_by_a_fake_inside_a_fake_is_found(tmp_path: Path) -> None:
    class Ledger(Protocol):
        def keep(self, line: str) -> None: ...

    class FakeLedger:
        def __init__(self) -> None:
            self.audit = FakeAudit()

        def keep(self, line: str) -> None:
            self.audit.record(line)

    source = CatalogueInputs({Handle: lambda: Handle("orders", "x")}, {Ledger: FakeLedger})
    run = RunnerSettings(
        source, FileRegressionStore(tmp_path), SecretRules(), blocked_network, 10, 1
    )

    def deep(ledger: Ledger, handle: Handle) -> str:
        ledger.keep(handle.credentials)
        return handle.table

    reg = PromiseRegistry()
    invariant(never_contains(Secret), dry_run=True, registry=reg)(deep)
    item = reg.all()[0]

    item.function.__annotations__["ledger"] = (
        Ledger  # a local Protocol: give the annotation directly
    )
    assert "found in what FakeLedger received" in check_promise(item, run).reason


def test_a_secret_parameter_is_planted_like_a_secret_field(run: RunnerSettings) -> None:
    def echoes(level: str, key: Secret[str] | None = None) -> str:
        return f"{level}: {key}"

    def ignores(level: str, key: Secret[str] | None = None) -> str:
        return level

    assert check(echoes, never_contains(Secret), run).outcome is Outcome.BROKEN
    assert check(ignores, never_contains(Secret), run).outcome is Outcome.PASSED
