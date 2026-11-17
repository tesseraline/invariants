"""Check one promise: call the function on many inputs with fakes and canaries, judge every output.

`tesseraline-invariants/src/tesseraline_invariants/application/runner.py`

Only `dry_run=True` functions are called. Inputs: regressions, factories,
then Hypothesis, which also shrinks a failing input to a minimal one; that minimal input is saved as
a regression. A promise that cannot be exercised is "not checked" with its reason, never passed: no
dry_run, no fake, no buildable input, no secret field to plant for never_contains, a network
attempt, or every call raising.
"""

from __future__ import annotations

import asyncio
import json
import typing
from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from hypothesis import HealthCheck, Verbosity, given, reject, settings
from hypothesis.errors import Unsatisfiable

from tesseraline_invariants.application.codec import CodecError, decode, encode, input_hash, plant
from tesseraline_invariants.application.declaration import check_boundaries
from tesseraline_invariants.application.inputs import (
    Parameter,
    fakes_for,
    known_inputs,
    plan,
    strategy_for,
)
from tesseraline_invariants.application.rendering import first_form, render, render_inputs
from tesseraline_invariants.application.secret_fields import (
    SecretField,
    SecretRules,
    find_secret_fields,
)
from tesseraline_invariants.domain.exceptions import DeclarationError, NetworkBlockedError
from tesseraline_invariants.domain.kinds import NeverContains, Preserves
from tesseraline_invariants.domain.promise import Call, CheckResult, Outcome, Violation

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager

    from tesseraline_invariants.application.registry import Registered
    from tesseraline_invariants.ports.input_source import InputSource
    from tesseraline_invariants.ports.regression_store import RegressionStore


@dataclass(frozen=True, slots=True)
class RunnerSettings:
    """What a check needs besides the promise; built by the factory from settings."""

    source: InputSource
    store: RegressionStore
    rules: SecretRules
    isolation: Callable[[], AbstractContextManager[None]]
    max_examples: int = 100
    seed: int = 0
    capture: Callable[[], AbstractContextManager[list[tuple[str, str]]]] = field(
        default=lambda: nullcontext([])
    )


class _Broken(Exception):  # noqa: N818 - control flow inside Hypothesis, never leaves this module
    def __init__(self, violation: Violation, case: dict[str, object]) -> None:
        super().__init__(violation.summary)
        self.violation, self.case = violation, case


class _Blocked(Exception):  # noqa: N818 - control flow inside Hypothesis, never leaves this module
    def __init__(self, host: str) -> None:
        super().__init__(host)
        self.host = host


@dataclass(slots=True)
class _Probe:
    """Everything one promise's calls share."""

    item: Registered
    params: list[Parameter]
    fakes: dict[str, object]
    secrets: list[SecretField]
    returns: object
    run: RunnerSettings
    calls: int = 0
    raised: str = ""

    def attempt(
        self, encoded: dict[str, object]
    ) -> tuple[Violation | None, dict[str, object]] | None:
        """Plant, rebuild, call and judge one input; None when unusable or the function raised."""
        planted, canaries = plant(encoded, self.secrets, self.run.seed)
        data = [p for p in self.params if not p.dependency]
        try:
            values = {p.name: decode(p.annotation, planted[p.name]) for p in data}  # type: ignore[index]
        except CodecError:
            return None
        fakes = fakes_for(
            self.params, self.run.source
        )  # fresh fakes per call: no state from earlier calls
        if isinstance(fakes, str):
            return None
        try:
            with self.run.isolation(), self.run.capture() as exits:
                output = _call(self.item.function, {**fakes, **values}, self.item.is_async)
        except NetworkBlockedError as blocked:
            raise _Blocked(blocked.host) from blocked
        except Exception as error:
            self.raised = type(error).__name__
            return None
        self.calls += 1
        preserves = isinstance(self.item.invariant, Preserves)
        call = Call(
            inputs=tuple(values[p.name] for p in data),
            output=output,
            input_text=render_inputs((values[p.name], p.annotation) for p in data),
            output_text=(first_form if preserves else render)(output, self.returns),
            canaries=canaries,
            exits=(
                *exits,
                *((f"what {type(f).__name__} received", _state(f)) for f in fakes.values()),
            ),
        )
        return self.item.invariant.judge(call), planted  # type: ignore[return-value]


def check_promise(item: Registered, run: RunnerSettings) -> CheckResult:
    """Check one registered promise.

    :param item: the promise with its function.
    :param run: inputs, regressions, secret rules, isolation, limits.
    :returns: passed, broken (with a minimal input saved) or not checked (with the reason).
    """
    pid = item.promise.promise_id
    probe = _prepare(item, run)
    if isinstance(probe, str):
        return CheckResult(pid, Outcome.NOT_CHECKED, reason=probe)
    try:
        for case in known_inputs(probe.params, pid, run.source, run.store, run.max_examples):
            result = probe.attempt(case)
            if result and result[0]:
                return _broken(pid, result[0], result[1], probe, run)
        found = _explore(probe)
    except _Blocked as blocked:
        return CheckResult(
            pid, Outcome.NOT_CHECKED, reason=f"attempted network access to {blocked.host}"
        )
    if found is not None:
        return _broken(pid, found.violation, found.case, probe, run)
    if probe.calls == 0:
        why = f"every call raised {probe.raised}" if probe.raised else "no input could be built"
        return CheckResult(pid, Outcome.NOT_CHECKED, reason=why)
    return CheckResult(pid, Outcome.PASSED, calls=probe.calls)


def _prepare(item: Registered, run: RunnerSettings) -> _Probe | str:
    if not item.promise.dry_run:
        return "dry_run not declared"
    try:
        if not item.resolved and not check_boundaries(item.function):
            return "type annotations cannot be resolved"
        params = plan(item.function)
        secrets = [
            f
            for p in params
            if not p.dependency
            for f in find_secret_fields(p.annotation, run.rules, p.name)
        ]
    except DeclarationError as error:
        return str(error)
    fakes = fakes_for(params, run.source)
    if isinstance(fakes, str):
        return fakes
    if isinstance(item.invariant, NeverContains) and not secrets:
        return "no secret field reachable from the input, so nothing can leak"
    returns = typing.get_type_hints(item.function, include_extras=True)["return"]
    return _Probe(item, params, fakes, secrets, returns, run)


def _explore(probe: _Probe) -> _Broken | None:
    strategy = strategy_for(probe.params)
    if isinstance(strategy, str):
        return None
    data = [p for p in probe.params if not p.dependency]

    @settings(
        max_examples=probe.run.max_examples,
        derandomize=True,
        database=None,
        deadline=None,
        suppress_health_check=list(HealthCheck),
        verbosity=Verbosity.quiet,
    )
    @given(strategy)
    def search(values: dict[str, object]) -> None:
        try:
            encoded = {p.name: encode(p.annotation, values[p.name]) for p in data}
        except CodecError:
            reject()
        result = probe.attempt(encoded)
        if result is None:
            reject()
        elif result[0]:
            raise _Broken(result[0], result[1])

    try:
        search()
    except _Broken as broken:
        return broken
    except Unsatisfiable:
        return None
    return None


def _broken(
    pid: str, violation: Violation, case: dict[str, object], probe: _Probe, run: RunnerSettings
) -> CheckResult:
    run.store.save(pid, case)
    return CheckResult(
        pid,
        Outcome.BROKEN,
        reason=violation.summary,
        calls=max(probe.calls, 1),
        input_hash=input_hash(case),
        violation=violation,
    )


def _state(fake: object) -> str:
    """Everything a fake kept from the call, as text, nested objects included (a sink in a ledger).

    Objects with attributes are opened recursively; dataclasses with slots and other values show
    through their repr, which lists their fields. A cycle falls back to the repr of the whole fake.
    """

    def expand(value: object) -> object:
        inner = getattr(value, "__dict__", None)
        return inner if isinstance(inner, dict) else repr(value)

    try:
        return json.dumps(expand(fake), default=expand, sort_keys=True)
    except (ValueError, TypeError, RecursionError):
        return repr(fake)


def _call(function: Callable[..., object], kwargs: dict[str, object], is_async: bool) -> object:
    if is_async:
        return asyncio.run(function(**kwargs))  # type: ignore[arg-type]
    return function(**kwargs)
