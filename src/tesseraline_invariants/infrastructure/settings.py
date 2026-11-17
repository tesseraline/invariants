"""Settings from `[tool.invariants]` in pyproject.toml, validated by a strict model at the boundary.

`tesseraline-invariants/src/tesseraline_invariants/infrastructure/settings.py`

Unknown keys are refused (extra="forbid"), so a typo is an error instead of a silently ignored
setting. Paths are relative to the folder that holds pyproject.toml.
"""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from tesseraline_invariants.domain.exceptions import ConfigurationError

if TYPE_CHECKING:
    from pathlib import Path


class Settings(BaseModel):
    """What a team configures; every field has a safe default.

    Examples:
        >>> Settings(modules=("myapp.exporters",)).max_examples
        100
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    modules: tuple[str, ...] = ()
    strict: bool = False
    secret_types: tuple[str, ...] = ()
    secret_fields: tuple[str, ...] = ()
    secret_rules: tuple[str, ...] = ()
    factories: dict[str, str] = Field(default_factory=dict)
    fakes: dict[str, str] = Field(default_factory=dict)
    audit_sink: str = ""
    lock_file: str = "invariants.lock"
    regressions_dir: str = "invariants/regressions"
    audit_file: str = "invariants/audit.jsonl"
    max_examples: int = Field(default=100, ge=1, le=10_000)
    seed: int = 0


def load_settings(project: Path) -> Settings:
    """Read `[tool.invariants]` from the project's pyproject.toml.

    :param project: the folder holding pyproject.toml.
    :returns: validated settings; defaults when the table is absent.
    :raises ConfigurationError: the file cannot be read, or a setting is invalid or unknown.
    """
    path = project / "pyproject.toml"
    try:
        table = (
            tomllib.loads(path.read_text(encoding="utf-8")).get("tool", {}).get("invariants", {})
        )
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ConfigurationError(str(path), f"cannot be read: {error}") from error
    try:
        return Settings.model_validate(table)
    except ValidationError as error:
        first = error.errors()[0]
        where = ".".join(str(p) for p in first["loc"]) or "[tool.invariants]"
        raise ConfigurationError(f"[tool.invariants] {where}", first["msg"]) from error  # noqa: TRY003
