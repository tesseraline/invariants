"""Unit tests for the import graph behind `impact --since`.

`tesseraline-invariants/tests/unit/test_import_graph.py`
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tesseraline_invariants.application.impact import affected, imports_of
from tesseraline_invariants.application.registry import PromiseRegistry
from tesseraline_invariants.domain.kinds import NeverContains


@pytest.fixture
def tree(tmp_path: Path) -> dict[str, Path]:
    files = {
        "app/__init__.py": "",
        "app/models.py": "import json\n",
        "app/exports.py": "from .models import Handle\n",
        "app/deep/__init__.py": "",
        "app/deep/report.py": "from ..exports import x\nfrom app import models\n",
        "other.py": "import app.models\n",
    }
    for rel, body in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(body, encoding="utf-8")
    names = {
        "app": "app/__init__.py",
        "app.models": "app/models.py",
        "app.exports": "app/exports.py",
        "app.deep": "app/deep/__init__.py",
        "app.deep.report": "app/deep/report.py",
        "other": "other.py",
    }
    return {name: (tmp_path / rel).resolve() for name, rel in names.items()}


def test_relative_and_absolute_imports_resolve_to_project_modules(tree: dict[str, Path]) -> None:
    graph = imports_of(tree)
    assert graph["app.exports"] == ["app", "app.models"]
    assert "app.exports" in graph["app.deep.report"]
    assert "app.models" in graph["app.deep.report"]
    assert graph["app.models"] == []  # json is not a project module


def test_affected_follows_the_chain_and_names_it(
    tree: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    def describe() -> str:
        return ""

    monkeypatch.setattr(describe, "__module__", "app.deep.report")
    reg = PromiseRegistry()
    reg.add(describe, NeverContains(("Secret",)), dry_run=True)
    hits = affected(reg.all(), {tree["app.models"]}, tree)
    assert len(hits) == 1
    assert "app.models" in hits[0].reason
    assert affected(reg.all(), {tree["other"]}, tree) == []


def test_a_module_outside_the_map_is_never_reported(tree: dict[str, Path]) -> None:
    def outside() -> str:
        return ""

    reg = PromiseRegistry()
    reg.add(outside, NeverContains(("Secret",)), dry_run=True)
    assert affected(reg.all(), set(tree.values()), tree) == []
