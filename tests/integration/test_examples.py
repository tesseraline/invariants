"""The examples run through the real command: the success criteria, end to end.

`tesseraline-invariants/tests/integration/test_examples.py`

Each test copies an example project into a temporary folder and runs `invariants` in a separate
process, so the promise registry and imported modules never leak between tests.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
GENERATED = shutil.ignore_patterns(
    "invariants", "__pycache__"
)  # outputs of earlier runs stay behind
SECRET_VALUES = ("example-password", "example-token", "tsqcanary")


def run(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        "-m",
        "tesseraline_invariants.entrypoints.cli",
        "--project",
        str(project),
        *args,
    ]
    return subprocess.run(command, capture_output=True, text=True, check=False, timeout=300)


@pytest.fixture
def caught(tmp_path: Path) -> Path:
    return Path(shutil.copytree(EXAMPLES / "caught", tmp_path / "caught", ignore=GENERATED))


@pytest.fixture
def passing(tmp_path: Path) -> Path:
    return Path(shutil.copytree(EXAMPLES / "passing", tmp_path / "passing", ignore=GENERATED))


def test_caught_finds_every_mistake_and_names_what_it_cannot_check(caught: Path) -> None:
    done = run(caught, "check")
    assert done.returncode == 1, done.stdout + done.stderr
    assert done.stdout.count("BROKEN       ") == 4
    assert "found in the output (plain)" in done.stdout
    assert "found in the output (base64)" in done.stdout
    assert "lost ['15%']" in done.stdout
    assert "dry_run not declared" in done.stdout
    assert "attempted network access to telemetry.example" in done.stdout
    assert list((caught / "invariants" / "regressions").glob("*.json"))


def test_passing_passes_with_exit_zero_even_in_strict_mode(passing: Path) -> None:
    done = run(passing, "check", "--strict")
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.count("PASS         ") == 4


def test_no_secret_value_reaches_the_terminal_the_log_or_the_audit(caught: Path) -> None:
    done = run(caught, "-v", "check")
    audit = (caught / "invariants" / "audit.jsonl").read_text(encoding="utf-8")
    for channel in (done.stdout, done.stderr, audit):
        for value in SECRET_VALUES:
            assert value not in channel
    assert "promise_check_failed" in done.stderr
    assert audit.count('"schema": 1') == 6


def test_a_removed_promise_fails_until_the_lock_is_updated(passing: Path) -> None:
    texts = passing / "passing_example" / "texts.py"
    source = texts.read_text(encoding="utf-8")
    texts.write_text(
        source.replace('@invariant(preserves("numbers"), dry_run=True)\n', ""), "utf-8"
    )
    done = run(passing, "check")
    assert done.returncode == 2
    assert "REMOVED      passing_example.texts:shorten#preserves" in done.stdout
    assert run(passing, "lock", "--update").returncode == 0
    assert run(passing, "check").returncode == 0


def test_a_weakened_promise_is_reported_as_changed(passing: Path) -> None:
    texts = passing / "passing_example" / "texts.py"
    source = texts.read_text(encoding="utf-8")
    texts.write_text(
        source.replace('preserves("numbers")', 'preserves("numbers", both_ways=False)'), "utf-8"
    )
    done = run(passing, "check")
    assert done.returncode == 2
    assert "CHANGED      passing_example.texts:shorten#preserves" in done.stdout


def test_an_unknown_setting_is_a_configuration_error(passing: Path) -> None:
    pyproject = passing / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace("max_examples", "max_exampels"), "utf-8"
    )
    done = run(passing, "check")
    assert done.returncode == 3
    assert "max_exampels" in done.stdout


def test_an_untyped_boundary_stops_the_import_with_a_named_error(passing: Path) -> None:
    texts = passing / "passing_example" / "texts.py"
    source = texts.read_text(encoding="utf-8")
    texts.write_text(
        source.replace("def shorten(text: str) -> str:", "def shorten(text) -> str:"), "utf-8"
    )
    done = run(passing, "check")
    assert done.returncode == 3
    assert "UntypedBoundaryError" in done.stdout


@pytest.mark.slow
def test_two_hundred_promises_with_factory_inputs_in_under_ten_seconds(tmp_path: Path) -> None:
    """`check` on 200 promises with factory inputs finishes in under 10 s on a laptop."""
    import time  # noqa: PLC0415 - only this slow test needs it

    lines = [
        "from dataclasses import dataclass",
        "from tesseraline_invariants import Secret, invariant, never_contains",
        "@dataclass(frozen=True)",
        "class Handle:",
        "    table: str",
        "    key: Secret[str]",
        "def handles() -> list[Handle]:",
        "    return [Handle('a', 'k1'), Handle('b', 'k2')]",
    ]
    for i in range(200):
        lines += [
            "@invariant(never_contains(Secret), dry_run=True)",
            f"def describe_{i}(handle: Handle) -> str:",
            "    return handle.table",
        ]
    (tmp_path / "perfmod.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.invariants]\nmodules = ["perfmod"]\n'
        '[tool.invariants.factories]\n"perfmod:Handle" = "perfmod:handles"\n',
        encoding="utf-8",
    )
    started = time.perf_counter()
    done = run(tmp_path, "check")
    assert done.returncode == 0, done.stdout[-500:]
    assert time.perf_counter() - started < 10
