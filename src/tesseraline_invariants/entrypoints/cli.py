"""The `invariants` command: check, list, lock --update, impact, rules, scan.

`tesseraline-invariants/src/tesseraline_invariants/entrypoints/cli.py`

This half imports only the standard library, so `rules` and `scan` work on a bare install and a
missing extra is reported, not crashed on. Exit codes: 0 every promise holds
and the scan is clean, 1 a promise broke (or was not checked in strict mode) or the scan found an
unguarded exit, 2 a promise was removed or changed without `lock --update`, 3 configuration, import
or installation error.
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess  # nosec B404
import sys
from importlib.resources import files
from pathlib import Path

CONFIG_ERROR = 3
CHECK_EXTRA = ("hypothesis", "pydantic", "structlog")


def main(argv: list[str] | None = None) -> int:
    """Run one command and return its exit code.

    :param argv: arguments without the program name; sys.argv[1:] when None.
    :returns: the exit code.
    """
    args = parser().parse_args(argv)
    if args.command == "rules":
        print(rules_path())
        return 0
    if args.command == "scan":
        return scan(args.paths, Path(args.project), args.exclude)
    missing = [m for m in CHECK_EXTRA if importlib.util.find_spec(m) is None]
    if missing:
        hint = "pip install 'tesseraline-invariants[check]'"
        print(f"install the check extra: {hint} (missing {', '.join(missing)})")
        return CONFIG_ERROR
    from tesseraline_invariants.entrypoints.cli_run import run  # noqa: PLC0415

    return run(args)


def rules_path() -> Path:
    """Where the Semgrep rules for unguarded exits are installed."""
    return Path(str(files("tesseraline_invariants") / "rules" / "unguarded-exits.yml"))


def scan(paths: list[str], project: Path, exclude: list[str] | None = None) -> int:
    """Run the rules with Semgrep: 0 clean, 1 an unguarded exit found, 3 Semgrep missing or failing.

    Semgrep runs offline: no metrics and no version check, so a scan never calls out.

    :param paths: files or folders; src/ (or the project) when empty.
    :param project: the folder the paths are relative to.
    :param exclude: path patterns left out of this scan only (Semgrep ``--exclude``), unlike a
        ``.semgrepignore`` that hides files from every Semgrep run in the project.
    :returns: the exit code.
    """
    semgrep: str | None = shutil.which("semgrep") or _beside_python("semgrep")
    if semgrep is None:
        print("semgrep is not installed: uv tool install semgrep (or pipx install semgrep)")
        return CONFIG_ERROR
    targets = paths or [str(project / "src") if (project / "src").is_dir() else str(project)]
    command = [
        semgrep,
        "--config",
        str(rules_path()),
        "--error",
        "--metrics=off",
        "--disable-version-check",
        "--quiet",
        *(f"--exclude={pattern}" for pattern in exclude or []),
        *targets,
    ]
    done = subprocess.run(command, check=False, cwd=project)  # noqa: S603  # nosec B603
    return {0: 0, 1: 1}.get(done.returncode, CONFIG_ERROR)


def _beside_python(name: str) -> str | None:
    candidate = Path(sys.executable).parent / name
    return str(candidate) if candidate.is_file() else None


def parser() -> argparse.ArgumentParser:
    """The command line: every subcommand and its options."""
    parser = argparse.ArgumentParser(
        prog="invariants", description="Check what functions promise about their output."
    )
    parser.add_argument(
        "--project", default=".", help="folder with pyproject.toml (default: current folder)"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="developer log at info level, on stderr"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="check every promise")
    check.add_argument(
        "--strict", action="store_true", help="a promise that is not checked fails the run"
    )
    check.add_argument(
        "--since", default="", help="check only promises a change since this git ref may affect"
    )
    impact = commands.add_parser("impact", help="list the promises a change may affect")
    impact.add_argument("--since", required=True, help="a git ref: commit, branch or tag")
    commands.add_parser("list", help="list every promise and whether it can be called")
    commands.add_parser("rules", help="print the path of the Semgrep rules for unguarded exits")
    scan = commands.add_parser(
        "scan", help="run the Semgrep rules for unguarded exits (needs semgrep)"
    )
    scan.add_argument(
        "paths", nargs="*", help="files or folders (default: src/ if it exists, else .)"
    )
    scan.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="a path left out of this scan (repeat)",
    )
    lock = commands.add_parser("lock", help="record the current promises in invariants.lock")
    lock.add_argument("--update", action="store_true", required=True, help="write the lock file")
    return parser


if __name__ == "__main__":
    sys.exit(main())
