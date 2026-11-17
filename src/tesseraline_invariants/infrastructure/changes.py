"""What changed since a git reference, and which project modules are loaded.

`tesseraline-invariants/src/tesseraline_invariants/infrastructure/changes.py`

The reference is checked before git sees it (no option, no shell). Changed files are the tracked
files that differ from the reference plus new untracked ones. Project modules are the loaded modules
whose file lies in the project folder, outside virtual environments and site-packages.
"""

from __future__ import annotations

import re
import shutil
import subprocess  # nosec B404
import sys
from pathlib import Path

from tesseraline_invariants.domain.exceptions import ConfigurationError

_REF = re.compile(r"[A-Za-z0-9_./~^@{}-]{1,200}")
_SKIP = ("site-packages", ".venv", "venv", ".tox")


def changed_files(project: Path, since: str) -> set[Path]:
    """Files that differ from a git reference, as resolved paths.

    :param project: a folder inside the git repository.
    :param since: a commit, branch or tag, e.g. "main" or "HEAD~3".
    :returns: changed tracked files and new untracked files.
    :raises ConfigurationError: the reference is malformed, git is missing, or git refuses.
    """
    if not _REF.fullmatch(since) or since.startswith("-"):
        raise ConfigurationError("--since", f"not a git reference: {since!r}")
    git: str | None = shutil.which("git")
    if git is None:
        raise ConfigurationError("--since", "git is not installed")
    top = _git(git, project, "rev-parse", "--show-toplevel").strip()
    names = _git(git, project, "diff", "--name-only", since, "--").splitlines()
    names += _git(git, project, "ls-files", "--others", "--exclude-standard").splitlines()
    return {(Path(top) / n).resolve() for n in names if n.strip()}


def project_modules(project: Path) -> dict[str, Path]:
    """Loaded modules whose source file is in the project folder.

    :param project: the folder holding pyproject.toml.
    :returns: module name -> resolved file.
    """
    root = project.resolve()
    found = {}
    for name, module in list(sys.modules.items()):
        file = getattr(module, "__file__", None)
        if not file or not file.endswith(".py"):
            continue
        path = Path(file).resolve()
        if path.is_relative_to(root) and not any(part in _SKIP for part in path.parts):
            found[name] = path
    return found


def _git(git: str, cwd: Path, *args: str) -> str:
    done = subprocess.run(  # noqa: S603  # nosec B603 - fixed program, arguments checked above
        [git, *args], cwd=cwd, capture_output=True, text=True, check=False, timeout=30
    )
    if done.returncode != 0:
        raise ConfigurationError("--since", f"git {args[0]} failed: {done.stderr.strip()[:200]}")
    return done.stdout
