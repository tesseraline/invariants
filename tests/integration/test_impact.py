"""`invariants impact --since` and `check --since` in a real git repository.

`tesseraline-invariants/tests/integration/test_impact.py`
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def git(project: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=project, check=True, capture_output=True)


def invariants(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
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
def repo(tmp_path: Path) -> Path:
    project = Path(shutil.copytree(EXAMPLES / "passing", tmp_path / "passing"))
    git(project, "init", "-q")
    git(project, "-c", "user.name=t", "-c", "user.email=t@example.org", "add", ".")
    git(
        project, "-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "-m", "base"
    )
    return project


def touch(path: Path) -> None:
    path.write_text(path.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")


def test_a_shared_model_change_reaches_every_promise_that_imports_it(repo: Path) -> None:
    touch(repo / "passing_example" / "models.py")
    done = invariants(repo, "impact", "--since", "HEAD")
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.count("MAY BE AFFECTED") == 4
    via = "via passing_example.exports -> passing_example.models"
    assert f"imports changed passing_example.models ({via})" in done.stdout


def test_a_change_in_one_module_reaches_only_its_promises(repo: Path) -> None:
    touch(repo / "passing_example" / "texts.py")
    done = invariants(repo, "impact", "--since", "HEAD")
    assert done.stdout.count("MAY BE AFFECTED") == 2
    assert "its module changed: texts.py" in done.stdout
    assert "exports" not in done.stdout.split("promises may be affected")[0]


def test_an_unrelated_change_affects_nothing_and_check_since_checks_nothing(repo: Path) -> None:
    (repo / "notes.txt").write_text("hello\n", encoding="utf-8")
    assert "0 of 4 promises may be affected" in invariants(repo, "impact", "--since", "HEAD").stdout
    done = invariants(repo, "check", "--since", "HEAD")
    assert done.returncode == 0
    assert "0 passed, 0 broken, 0 not checked" in done.stdout


def test_check_since_checks_only_the_affected_promises(repo: Path) -> None:
    touch(repo / "passing_example" / "texts.py")
    done = invariants(repo, "check", "--since", "HEAD")
    assert done.returncode == 0
    assert done.stdout.count("PASS ") == 2


@pytest.mark.parametrize("ref", ["--output=x", "HEAD; rm -rf /", ""])
def test_a_malformed_reference_is_refused_before_git_sees_it(repo: Path, ref: str) -> None:
    done = invariants(repo, "impact", "--since", ref)
    assert done.returncode in (
        2,
        3,
    )  # argparse refuses an empty value with 2; a bad ref is a configuration error
    assert "rm -rf" not in done.stderr or done.returncode == 3
