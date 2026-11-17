"""Port: a team's own rule for what counts as a secret.

`tesseraline-invariants/src/tesseraline_invariants/ports/secret_rule.py`
"""

from __future__ import annotations

from typing import Protocol


class SecretRule(Protocol):
    """Decide whether one field of one type holds a secret."""

    def is_secret(self, owner: type, field: str) -> bool:
        """Answer for one field.

        :param owner: the class that declares the field.
        :param field: the field's name.
        :returns: True when the field holds a secret.
        """
        ...
