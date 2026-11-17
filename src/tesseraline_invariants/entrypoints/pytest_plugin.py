"""pytest plugin: `pytest --invariants` checks every promise as one test item (decision 0011).

`tesseraline-invariants/src/tesseraline_invariants/entrypoints/pytest_plugin.py`

Loaded by every pytest run in a project that installs the package, so it imports nothing beyond
pytest until `--invariants` is given. Without the "check" extra it adds one
failing item that says which extra to install, instead of breaking the test run.
"""

from __future__ import annotations

import importlib.util

import pytest

CHECK_EXTRA = ("hypothesis", "pydantic", "structlog")


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add the opt-in flags."""
    group = parser.getgroup("invariants", "tesseraline-invariants")
    group.addoption("--invariants", action="store_true", help="check every promise as a test item")
    group.addoption(
        "--invariants-strict", action="store_true", help="a promise that is not checked fails"
    )
    group.addoption(
        "--invariants-project", default="", help="folder with pyproject.toml (default: rootdir)"
    )


def pytest_collection_modifyitems(
    session: pytest.Session, config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Append the promise items when `--invariants` is given."""
    if not config.getoption("--invariants"):
        return
    missing = [m for m in CHECK_EXTRA if importlib.util.find_spec(m) is None]
    if missing:
        items.append(
            MissingExtraItem.from_parent(session, name="invariants[install]", missing=missing)
        )
        return
    from tesseraline_invariants.entrypoints.pytest_items import collect  # noqa: PLC0415

    collect(session, config, items)


class MissingExtraItem(pytest.Item):
    """One failing item when the check extra is not installed."""

    def __init__(self, *, missing: list[str], **kwargs: object) -> None:
        """Keep the names of the missing packages."""
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.missing = missing

    def runtest(self) -> None:
        """Fail with the install hint."""
        hint = "pip install 'tesseraline-invariants[check]'"
        pytest.fail(f"{hint} (missing {', '.join(self.missing)})", pytrace=False)

    def reportinfo(self) -> tuple[str, int, str]:
        """Where the item points: nowhere in particular."""
        return "pyproject.toml", 0, self.name
