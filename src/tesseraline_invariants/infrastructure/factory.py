"""Build everything a check needs from settings; the only place that names concrete adapters.

`tesseraline-invariants/src/tesseraline_invariants/infrastructure/factory.py`

Classes and callables are named in settings as "module:attribute". A class
that does not satisfy its port is refused with `AdapterContractError`; a module that cannot be
imported is a `ConfigurationError` (exit 3), never skipped silently.
"""

from __future__ import annotations

import functools
import importlib
import shutil
import subprocess  # nosec B404
import sys
from typing import TYPE_CHECKING, cast

from tesseraline_invariants.adapters.catalogue_inputs import CatalogueInputs
from tesseraline_invariants.adapters.file_regression_store import FileRegressionStore
from tesseraline_invariants.adapters.json_lines_files import (
    JsonLinesAuditSink,
    JsonLinesLockStore,
    SystemClock,
)
from tesseraline_invariants.application.check import Records
from tesseraline_invariants.application.runner import RunnerSettings
from tesseraline_invariants.application.secret_fields import SecretRules
from tesseraline_invariants.domain.exceptions import AdapterContractError, ConfigurationError
from tesseraline_invariants.infrastructure.capture import captured_exits
from tesseraline_invariants.infrastructure.network_block import check_workdir, isolated
from tesseraline_invariants.infrastructure.settings import load_settings

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tesseraline_invariants.infrastructure.settings import Settings
    from tesseraline_invariants.ports.audit_sink import AuditSink
    from tesseraline_invariants.ports.secret_rule import SecretRule


def prepare(project: Path) -> tuple[Settings, RunnerSettings, Records]:
    """Everything one check needs, the same for the command and the pytest plugin.

    :param project: the folder holding pyproject.toml.
    :returns: settings, runner settings and records; the modules named in settings are imported.
    :raises ConfigurationError: settings, a module, a class or a callable is wrong (exit 3).
    """
    settings = load_settings(project)
    import_promises(settings, project)
    run, records = build(settings, project)
    return settings, run, records


def import_promises(settings: Settings, project: Path) -> None:
    """Import the modules named in settings, so their decorators register promises.

    :param settings: validated settings.
    :param project: the project folder; it and its src/ folder are put on the import path.
    :raises ConfigurationError: a module cannot be imported (the import error is chained).
    """
    for folder in (project / "src", project):
        if str(folder) not in sys.path:
            sys.path.insert(0, str(folder))
    for name in settings.modules:
        try:
            importlib.import_module(name)
        except Exception as error:
            raise ConfigurationError(
                name, f"cannot be imported: {type(error).__name__}: {error}"
            ) from error


def build(settings: Settings, project: Path) -> tuple[RunnerSettings, Records]:
    """Build the runner settings and the records from validated settings.

    :param settings: validated settings.
    :param project: the folder holding pyproject.toml; relative paths start here.
    :returns: what `run_check` needs.
    :raises ConfigurationError: a named class or callable cannot be found.
    :raises AdapterContractError: a named class does not satisfy its port.
    """
    rules = SecretRules(
        types=tuple(_class(p) for p in settings.secret_types),
        name_patterns=settings.secret_fields,
        hooks=tuple(
            cast("SecretRule", _adapter(p, "SecretRule", ("is_secret",)))
            for p in settings.secret_rules
        ),
    )
    source = CatalogueInputs(
        {_class(t): _callable(f) for t, f in settings.factories.items()},
        {_class(t): _callable(f) for t, f in settings.fakes.items()},
    )
    run = RunnerSettings(
        source,
        FileRegressionStore(project / settings.regressions_dir),
        rules,
        functools.partial(isolated, check_workdir()),
        settings.max_examples,
        settings.seed,
        captured_exits,
    )
    audit = (
        cast("AuditSink", _adapter(settings.audit_sink, "AuditSink", ("write",)))
        if settings.audit_sink
        else JsonLinesAuditSink(project / settings.audit_file)
    )
    records = Records(
        JsonLinesLockStore(project / settings.lock_file),
        audit,
        SystemClock(),
        _code_version(project),
    )
    return run, records


def _resolve(path: str) -> object:
    module, _, attribute = path.partition(":")
    if not module or not attribute:
        raise ConfigurationError(path, 'expected "module:attribute"')
    try:
        return getattr(importlib.import_module(module), attribute)
    except (ImportError, AttributeError) as error:
        raise ConfigurationError(path, f"cannot be found: {error}") from error


def _class(path: str) -> type:
    found = _resolve(path)
    if not isinstance(found, type):
        raise ConfigurationError(path, "is not a class")
    return found


def _callable(path: str) -> Callable[[], object]:
    found = _resolve(path)
    if not callable(found):
        raise ConfigurationError(path, "is not callable")
    return found


def _adapter(path: str, port: str, methods: tuple[str, ...]) -> object:
    cls = _class(path)
    missing = tuple(m for m in methods if not callable(getattr(cls, m, None)))
    if missing:
        raise AdapterContractError(port, path, missing)
    return cls()


def _code_version(project: Path) -> str:
    git: str | None = shutil.which("git")
    if not git:
        return ""
    done = subprocess.run(  # noqa: S603 - fixed arguments, git found by shutil.which
        [git, "rev-parse", "--short", "HEAD"],
        cwd=project,
        capture_output=True,  # nosec B603
        text=True,
        check=False,
        timeout=10,
    )
    return done.stdout.strip() if done.returncode == 0 else ""
