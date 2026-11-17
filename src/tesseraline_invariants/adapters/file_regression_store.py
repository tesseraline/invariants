"""Regressions as JSON files under `invariants/regressions/`, one file per promise.

`tesseraline-invariants/src/tesseraline_invariants/adapters/file_regression_store.py`

File names are a hash of the promise id, so any id is safe as a name; the id is kept inside the
file. The cases hold canaries where secrets were, never a real secret value.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class FileRegressionStore:
    """Satisfies `ports.RegressionStore`.

    Examples:
        >>> import tempfile
        >>> from pathlib import Path
        >>> store = FileRegressionStore(Path(tempfile.mkdtemp()))
        >>> store.save("m:f#holds:1", {"x": 3})
        >>> store.save("m:f#holds:1", {"x": 3})
        >>> store.load("m:f#holds:1")
        [{'x': 3}]
    """

    def __init__(self, folder: Path) -> None:
        """Keep the folder; it is created on the first save.

        :param folder: usually `invariants/regressions` next to pyproject.toml.
        """
        self._folder = folder

    def load(self, promise_id: str) -> list[dict[str, object]]:
        """Saved cases for one promise, oldest first."""
        path = self._path(promise_id)
        if not path.is_file():
            return []
        cases = json.loads(path.read_text(encoding="utf-8")).get("cases", [])
        return [c for c in cases if isinstance(c, dict)]

    def save(self, promise_id: str, case: dict[str, object]) -> None:
        """Add a case unless the same one is stored already."""
        cases = self.load(promise_id)
        if case in cases:
            return
        self._folder.mkdir(parents=True, exist_ok=True)
        body = {"promise": promise_id, "cases": [*cases, case]}
        self._path(promise_id).write_text(
            json.dumps(body, indent=1, sort_keys=True) + "\n", "utf-8"
        )

    def _path(self, promise_id: str) -> Path:
        return self._folder / f"{hashlib.sha256(promise_id.encode()).hexdigest()[:16]}.json"
