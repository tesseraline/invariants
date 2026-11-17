"""The Semgrep rules for users: each fires on its pattern, stays quiet on the safe form (v0.2).

`tesseraline-invariants/tests/integration/test_user_rules.py`
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
SAMPLE = """
import base64, dataclasses, json
from dataclasses import asdict

def bad(handle, log, db):
    json.dumps(handle.__dict__)                              # whole-object-to-json
    json.dumps(asdict(handle))                               # whole-object-to-json
    handle.model_dump_json()                                 # whole-object-to-json
    json.dumps({"handle": repr(handle)})                     # repr-in-output
    text = f"handle={handle!r}"                              # not flagged (ids in messages)
    log.info("exported", handle=asdict(handle))              # whole-object-to-log
    base64.b64encode(f"{handle.table}:{handle.key}".encode())  # encoding-is-not-hiding
    db.execute("select * from handles")                      # select-star

def good(handle, log, db):
    json.dumps({"table": handle.table})
    log.info("exported", table=handle.table)
    base64.b64encode(handle.table.encode())
    db.execute("select table_name from handles")
"""


def rules_path() -> str:
    command = [sys.executable, "-m", "tesseraline_invariants.entrypoints.cli", "rules"]
    return subprocess.run(command, capture_output=True, text=True, check=True).stdout.strip()


def semgrep(target: Path) -> list[tuple[str, int]]:
    semgrep_bin = shutil.which("semgrep") or str(Path(sys.executable).parent / "semgrep")
    command = [
        semgrep_bin,
        "--config",
        rules_path(),
        "--metrics=off",
        "--disable-version-check",
        "--quiet",
        "--json",
        str(target),
    ]
    out = json.loads(subprocess.run(command, capture_output=True, text=True, check=False).stdout)
    return sorted((r["check_id"].rsplit(".", 1)[-1], r["start"]["line"]) for r in out["results"])


@pytest.fixture(scope="module")
def sample_hits(tmp_path_factory: pytest.TempPathFactory) -> list[tuple[str, int]]:
    path = tmp_path_factory.mktemp("rules") / "sample.py"
    path.write_text(SAMPLE, encoding="utf-8")
    return semgrep(path)


def test_every_rule_fires_on_its_pattern(sample_hits: list[tuple[str, int]]) -> None:
    by_rule = {}
    for rule, line in sample_hits:
        by_rule.setdefault(rule, []).append(line)
    assert by_rule == {
        "invariants-whole-object-to-json": [6, 7, 8],
        "invariants-repr-in-output": [9],
        "invariants-whole-object-to-log": [11],
        "invariants-encoding-is-not-hiding": [12],
        "invariants-select-star": [13],
    }


def test_the_safe_forms_stay_quiet(sample_hits: list[tuple[str, int]]) -> None:
    assert all(line < 15 for _, line in sample_hits)


def test_the_caught_example_leaks_are_flagged_and_the_passing_one_is_clean() -> None:
    caught = semgrep(EXAMPLES / "caught" / "caught_example" / "exports.py")
    rules = {rule for rule, _ in caught}
    assert rules == {"invariants-repr-in-output", "invariants-encoding-is-not-hiding"}
    assert semgrep(EXAMPLES / "passing") == []


def test_scan_command_fails_on_caught_and_passes_on_passing() -> None:
    def scan(project: Path) -> int:
        command = [
            sys.executable,
            "-m",
            "tesseraline_invariants.entrypoints.cli",
            "--project",
            str(project),
            "scan",
            str(project),
        ]
        return subprocess.run(command, capture_output=True, text=True, check=False).returncode

    assert scan(EXAMPLES / "caught") == 1
    assert scan(EXAMPLES / "passing") == 0
