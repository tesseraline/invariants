"""A production install without extras: the decorator works, the check names the extra (0013).

`tesseraline-invariants/tests/integration/test_bare_install.py`
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = """from dataclasses import dataclass
from tesseraline_invariants import Secret, invariant, never_contains


@dataclass(frozen=True)
class H:
    key: Secret[str]


@invariant(never_contains(Secret), dry_run=True)
def f(h: H) -> str:
    return "ok"
"""


def sh(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args), cwd=cwd, capture_output=True, text=True, check=False, timeout=600
    )


@pytest.mark.slow
def test_bare_install_runs_the_decorator_and_names_the_missing_extra(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is needed to build and install the package")
    assert (
        sh(uv, "build", "-q", "--wheel", "--out-dir", str(tmp_path / "dist"), cwd=ROOT).returncode
        == 0
    )
    wheel = next((tmp_path / "dist").glob("*.whl"))
    assert sh(uv, "venv", "-q", "-p", "3.12", str(tmp_path / "venv"), cwd=tmp_path).returncode == 0
    python = tmp_path / "venv" / "bin" / "python"
    assert (
        sh(
            uv,
            "pip",
            "install",
            "-q",
            "--python",
            str(python),
            "--no-deps",
            str(wheel),
            cwd=tmp_path,
        ).returncode
        == 0
    )
    project = tmp_path / "proj"
    project.mkdir()
    (project / "mod.py").write_text(MODULE, encoding="utf-8")
    (project / "pyproject.toml").write_text(
        '[tool.invariants]\nmodules = ["mod"]\n', encoding="utf-8"
    )
    assert sh(str(python), "-c", "import mod", cwd=project).returncode == 0
    check = sh(str(tmp_path / "venv" / "bin" / "invariants"), "check", cwd=project)
    assert check.returncode == 3
    assert "tesseraline-invariants[check]" in check.stdout
