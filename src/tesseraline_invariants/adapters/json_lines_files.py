"""The default audit sink, lock store and clock: JSON lines files next to pyproject.toml.

`tesseraline-invariants/src/tesseraline_invariants/adapters/json_lines_files.py`

The lock is one JSON object per line with sorted keys, sorted by id, so a change diffs and merges
line by line. The audit file is append-only.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class JsonLinesAuditSink:
    """Satisfies `ports.AuditSink`: one line per record, appended."""

    def __init__(self, path: Path) -> None:
        """Keep the path; folders are created on the first write.

        :param path: usually `invariants/audit.jsonl`.
        """
        self._path = path

    def write(self, record: dict[str, object]) -> None:
        """Append one record."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as out:
            out.write(json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n")


class JsonLinesLockStore:
    """Satisfies `ports.LockStore`.

    Examples:
        >>> import tempfile
        >>> from pathlib import Path
        >>> store = JsonLinesLockStore(Path(tempfile.mkdtemp()) / "invariants.lock")
        >>> store.write([{"id": "b"}, {"id": "a"}])
        >>> [e["id"] for e in store.read()]
        ['a', 'b']
    """

    def __init__(self, path: Path) -> None:
        """Keep the path of the lock file.

        :param path: usually `invariants.lock` next to pyproject.toml.
        """
        self._path = path

    def read(self) -> list[dict[str, object]]:
        """Every recorded promise; empty when the file does not exist."""
        if not self._path.is_file():
            return []
        lines = self._path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    def write(self, entries: list[dict[str, object]]) -> None:
        """Replace the lock, one sorted line per promise."""
        ordered = sorted(entries, key=lambda e: str(e.get("id", "")))
        text = "".join(json.dumps(e, sort_keys=True, ensure_ascii=True) + "\n" for e in ordered)
        self._path.write_text(text, encoding="utf-8")


class SystemClock:
    """Satisfies `ports.Clock` with the real UTC time."""

    def now(self) -> str:
        """The current UTC time, second precision."""
        return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
