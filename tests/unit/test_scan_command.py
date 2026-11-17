"""The scan command runs Semgrep offline and scopes its exclusions to itself."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from tesseraline_invariants.entrypoints import cli

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_scan_runs_offline_with_scoped_excludes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[list[str]] = []

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        seen.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/semgrep")
    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    assert cli.scan(["src"], tmp_path, ["migrations/"]) == 0
    command = seen[0]
    assert "--metrics=off" in command
    assert "--disable-version-check" in command
    assert "--exclude=migrations/" in command
    assert command[-1] == "src"
