"""Which promises a change may affect: their module, or a project module they import, changed.

`tesseraline-invariants/src/tesseraline_invariants/application/impact.py`

Imports are read from source with `ast`, never executed. Only project files count; third-party
packages are ignored. The answer over-approximates on purpose and is worded "may be affected": a
promise left out is not called safe, only not reached by a project import from a changed file.
Dynamic imports and data files are not seen, a stated limit.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from tesseraline_invariants.application.registry import Registered


@dataclass(frozen=True, slots=True)
class Affected:
    """One promise a change may affect, and why."""

    promise_id: str
    reason: str


def affected(
    items: list[Registered], changed: set[Path], modules: Mapping[str, Path]
) -> list[Affected]:
    """The promises whose module, or a project module it imports, is among the changed files.

    :param items: registered promises.
    :param changed: changed files, resolved paths.
    :param modules: project module name -> file, for every module that can be resolved.
    :returns: one entry per promise that may be affected, with the first chain reaching a change.
    """
    graph = imports_of(modules)
    names_by_file = {path: name for name, path in modules.items()}
    found = []
    for item in items:
        start = item.function.__module__
        chain = _first_changed(start, graph, modules, changed)
        if chain is None:
            continue
        hit = names_by_file.get(modules[chain[-1]], chain[-1])
        if len(chain) == 1:
            reason = f"its module changed: {modules[start].name}"
        else:
            reason = f"imports changed {hit} (via {' -> '.join(chain)})"
        found.append(Affected(item.promise.promise_id, reason))
    return found


def imports_of(modules: Mapping[str, Path]) -> dict[str, list[str]]:
    r"""Project modules each project module imports, read from its source.

    :param modules: project module name -> file.
    :returns: module name -> sorted names of the project modules it imports.

    Examples:
        >>> import tempfile
        >>> from pathlib import Path
        >>> root = Path(tempfile.mkdtemp())
        >>> _ = (root / "a.py").write_text("import b\nimport json\n")
        >>> _ = (root / "b.py").write_text("x = 1\n")
        >>> imports_of({"a": root / "a.py", "b": root / "b.py"})["a"]
        ['b']
    """
    graph: dict[str, list[str]] = {}
    for name, path in modules.items():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            graph[name] = []
            continue
        package = name if path.name == "__init__.py" else name.rpartition(".")[0]
        wanted = set()
        for node in ast.walk(tree):
            for target in _targets(node, package):
                wanted |= {m for m in modules if target == m or target.startswith(f"{m}.")}
        graph[name] = sorted(wanted - {name})
    return graph


def _targets(node: ast.AST, package: str) -> list[str]:
    """The module names an import statement may load (`from a import b` may load a or a.b)."""
    if isinstance(node, ast.Import):
        return [a.name for a in node.names]
    if not isinstance(node, ast.ImportFrom):
        return []
    base = node.module or ""
    if node.level:
        parts = package.split(".") if package else []
        keep = parts[: len(parts) - node.level + 1] if node.level > 1 else parts
        base = ".".join([*keep, base] if base else keep)
    return [base, *(f"{base}.{a.name}" for a in node.names)] if base else []


def _first_changed(
    start: str, graph: Mapping[str, list[str]], modules: Mapping[str, Path], changed: set[Path]
) -> list[str] | None:
    """Breadth-first from the promise's module to the nearest changed module; the chain, or None."""
    if start not in modules:
        return None
    queue: list[list[str]] = [[start]]
    seen = {start}
    while queue:
        chain = queue.pop(0)
        if modules[chain[-1]].resolve() in changed:
            return chain
        for nxt in graph.get(chain[-1], []):
            if nxt not in seen:
                seen.add(nxt)
                queue.append([*chain, nxt])
    return None
