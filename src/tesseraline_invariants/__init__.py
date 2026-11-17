"""tesseraline-invariants: promises about what a function's output may contain.

`tesseraline-invariants/src/tesseraline_invariants/__init__.py`

Five public names (architecture: at most five per module): `Secret`, `invariant`, `never_contains`,
`preserves`, `holds`. Everything else is internal and may change.
"""

from tesseraline_invariants.domain.secret import Secret
from tesseraline_invariants.entrypoints.api import holds, invariant, never_contains, preserves

__all__ = ["Secret", "holds", "invariant", "never_contains", "preserves"]
