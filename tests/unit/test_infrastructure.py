"""Unit tests for settings, the factory, the report's exit codes and the command run in-process.

`tesseraline-invariants/tests/unit/test_infrastructure.py`
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tesseraline_invariants.application.check import Report
from tesseraline_invariants.application.lock import LockDiff
from tesseraline_invariants.application.registry import DEFAULT_REGISTRY
from tesseraline_invariants.domain.exceptions import AdapterContractError, ConfigurationError
from tesseraline_invariants.domain.promise import CheckResult, Outcome
from tesseraline_invariants.entrypoints.cli import main
from tesseraline_invariants.infrastructure.factory import build, import_promises
from tesseraline_invariants.infrastructure.settings import Settings, load_settings

MODULE = """
from dataclasses import dataclass
from tesseraline_invariants import Secret, invariant, never_contains

@dataclass(frozen=True)
class Handle:
    table: str
    key: Secret[str]

@invariant(never_contains(Secret), dry_run=True)
def describe(handle: Handle) -> str:
    return handle.table
"""


class NotASink:
    pass


@pytest.fixture
def project(tmp_path: Path) -> Path:
    name = f"inproc_{tmp_path.name.replace('-', '_')}"
    (tmp_path / f"{name}.py").write_text(MODULE, encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        f'[tool.invariants]\nmodules = ["{name}"]\nmax_examples = 20\n', encoding="utf-8"
    )
    DEFAULT_REGISTRY.clear()
    yield tmp_path
    DEFAULT_REGISTRY.clear()
    sys.modules.pop(name, None)


def test_settings_defaults_when_the_table_is_absent(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    assert load_settings(tmp_path) == Settings()


@pytest.mark.parametrize(
    ("body", "where"),
    [
        ("[tool.invariants]\nstrict = 'maybe'\n", "strict"),
        ("[tool.invariants]\nmax_examples = 0\n", "max_examples"),
    ],
)
def test_invalid_settings_name_the_setting(tmp_path: Path, body: str, where: str) -> None:
    (tmp_path / "pyproject.toml").write_text(body, encoding="utf-8")
    with pytest.raises(ConfigurationError) as caught:
        load_settings(tmp_path)
    assert where in caught.value.setting


def test_missing_pyproject_is_a_configuration_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        load_settings(tmp_path)


def test_factory_refuses_a_class_that_misses_its_port(tmp_path: Path) -> None:
    settings = Settings(audit_sink=f"{__name__}:NotASink")
    with pytest.raises(AdapterContractError) as caught:
        build(settings, tmp_path)
    assert caught.value.missing == ("write",)


@pytest.mark.parametrize("path", ["no_colon", "nowhere.at.all:Thing", f"{__name__}:Missing"])
def test_factory_names_what_cannot_be_found(tmp_path: Path, path: str) -> None:
    with pytest.raises(ConfigurationError):
        build(Settings(secret_types=(path,)), tmp_path)


def test_an_unimportable_module_is_a_configuration_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        import_promises(Settings(modules=("surely_not_a_module_here",)), tmp_path)


@pytest.mark.parametrize(
    ("outcomes", "diff", "strict", "code"),
    [
        ([Outcome.PASSED], LockDiff(), False, 0),
        ([Outcome.PASSED, Outcome.BROKEN], LockDiff(), False, 1),
        ([Outcome.NOT_CHECKED], LockDiff(), False, 0),
        ([Outcome.NOT_CHECKED], LockDiff(), True, 1),
        ([Outcome.BROKEN], LockDiff(removed=("x",)), False, 2),
    ],
)
def test_exit_codes(outcomes: list[Outcome], diff: LockDiff, strict: bool, code: int) -> None:
    results = tuple(CheckResult(f"p{i}", o) for i, o in enumerate(outcomes))
    assert Report(results, diff, strict).exit_code == code


def test_command_in_process_check_list_and_lock(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--project", str(project), "check"]) == 0
    assert "PASS" in capsys.readouterr().out
    assert main(["--project", str(project), "list"]) == 0
    assert "(dry_run)" in capsys.readouterr().out
    assert main(["--project", str(project), "lock", "--update"]) == 0
    assert (project / "invariants.lock").read_text(encoding="utf-8").count("\n") == 1


def test_command_reports_a_configuration_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.invariants]\nunknown = 1\n", encoding="utf-8")
    assert main(["--project", str(tmp_path), "check"]) == 3
    assert "configuration error" in capsys.readouterr().out
