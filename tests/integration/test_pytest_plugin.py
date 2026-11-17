"""The pytest plugin, run in a separate process on copies of the examples.

`tesseraline-invariants/tests/integration/test_pytest_plugin.py`
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
GENERATED = shutil.ignore_patterns(
    "invariants", "__pycache__"
)  # outputs of earlier runs stay behind


def copy(pytester: pytest.Pytester, name: str) -> Path:
    shutil.copytree(EXAMPLES / name, pytester.path, dirs_exist_ok=True, ignore=GENERATED)
    return pytester.path


def test_off_without_the_flag(pytester: pytest.Pytester) -> None:
    copy(pytester, "caught")
    result = pytester.runpytest_subprocess("-p", "no:cacheprovider")
    assert result.ret == pytest.ExitCode.NO_TESTS_COLLECTED


def test_caught_fails_the_four_broken_and_skips_the_two_not_checked(
    pytester: pytest.Pytester,
) -> None:
    copy(pytester, "caught")
    result = pytester.runpytest_subprocess("--invariants", "-p", "no:cacheprovider")
    result.assert_outcomes(failed=4, passed=1, skipped=2)
    assert "found in the output (base64)" in result.stdout.str()
    assert "example-password" not in result.stdout.str()


def test_strict_turns_not_checked_into_failures(pytester: pytest.Pytester) -> None:
    copy(pytester, "caught")
    result = pytester.runpytest_subprocess(
        "--invariants", "--invariants-strict", "-p", "no:cacheprovider"
    )
    result.assert_outcomes(failed=6, passed=1)


def test_passing_passes(pytester: pytest.Pytester) -> None:
    copy(pytester, "passing")
    result = pytester.runpytest_subprocess("--invariants", "-p", "no:cacheprovider")
    result.assert_outcomes(passed=5)


def test_a_removed_promise_fails_the_lock_item(pytester: pytest.Pytester) -> None:
    project = copy(pytester, "passing")
    texts = project / "passing_example" / "texts.py"
    texts.write_text(
        texts.read_text(encoding="utf-8").replace(
            '@invariant(preserves("numbers"), dry_run=True)\n', ""
        ),
        encoding="utf-8",
    )
    result = pytester.runpytest_subprocess("--invariants", "-p", "no:cacheprovider")
    result.assert_outcomes(failed=1, passed=3)
    assert "removed: passing_example.texts:shorten#preserves" in result.stdout.str()


def test_a_configuration_error_is_one_failing_item(pytester: pytest.Pytester) -> None:
    project = copy(pytester, "passing")
    pyproject = project / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace("max_examples", "max_exampels"), "utf-8"
    )
    result = pytester.runpytest_subprocess("--invariants", "-p", "no:cacheprovider")
    result.assert_outcomes(failed=1)
    assert "configuration error" in result.stdout.str()
