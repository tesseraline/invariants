"""Every error the library raises, under one base.

`tesseraline-invariants/src/tesseraline_invariants/domain/exceptions.py`

Data lives on attributes; the message is for people. Declaration errors are raised when a function
is decorated, configuration errors when settings or adapters are
loaded.
"""

from __future__ import annotations


class InvariantsError(Exception):
    """Base of every error raised by tesseraline-invariants."""


class DeclarationError(InvariantsError):
    """A promise cannot be checked as declared; raised at decoration time."""

    def __init__(self, function: str, name: str, detail: str) -> None:
        """Keep the function and the parameter (or "return") the error is about.

        :param function: qualified name of the decorated function.
        :param name: parameter name, or "return" for the return value.
        :param detail: what is wrong, for people.
        """
        super().__init__(f"{function}: {name}: {detail}")
        self.function = function
        self.name = name


class UntypedBoundaryError(DeclarationError):
    """A parameter or the return value has no type annotation.

    Examples:
        >>> err = UntypedBoundaryError("pkg.f", "handle")
        >>> (err.function, err.name)
        ('pkg.f', 'handle')
    """

    def __init__(self, function: str, name: str) -> None:
        """Name the function and the untyped boundary.

        :param function: qualified name of the decorated function.
        :param name: parameter name, or "return".
        """
        super().__init__(function, name, "has no type annotation, so its secrets cannot be tracked")


class UntrackablePayloadError(DeclarationError):
    """A boundary is typed as dict, Any or object, which hides its fields.

    Examples:
        >>> UntrackablePayloadError("pkg.f", "return", "dict").annotation
        'dict'
    """

    def __init__(self, function: str, name: str, annotation: str) -> None:
        """Name the boundary and the annotation that hides its fields.

        :param function: qualified name of the decorated function.
        :param name: parameter name, or "return".
        :param annotation: the annotation as written.
        """
        super().__init__(
            function,
            name,
            f"is typed {annotation}; pass the data through a dataclass or a Pydantic model",
        )
        self.annotation = annotation


class UsageError(InvariantsError):
    """The public API was called with something it cannot use (no promise, an unknown kind)."""

    def __init__(self, what: str, detail: str) -> None:
        """Name the call and what is wrong.

        :param what: the API name, e.g. "preserves".
        :param detail: what is wrong and what is accepted.
        """
        super().__init__(f"{what}: {detail}")
        self.what = what


class NetworkBlockedError(InvariantsError):
    """A promised function tried to reach the network during a check."""

    def __init__(self, host: str) -> None:
        """Name the host only, never the request.

        :param host: what the function tried to reach.
        """
        super().__init__(f"attempted network access to {host}")
        self.host = host


class ConfigurationError(InvariantsError):
    """Settings are missing, malformed, or name something that cannot be imported."""

    def __init__(self, setting: str, detail: str) -> None:
        """Name the setting and what is wrong with it.

        :param setting: the key under [tool.invariants], or a module path.
        :param detail: what is wrong, for people.
        """
        super().__init__(f"{setting}: {detail}")
        self.setting = setting


class AdapterContractError(ConfigurationError):
    """A class named in settings does not satisfy the Protocol of its port."""

    def __init__(self, port: str, class_path: str, missing: tuple[str, ...]) -> None:
        """Name the port, the class and the methods it lacks.

        :param port: the Protocol name, e.g. "AuditSink".
        :param class_path: the "module:attribute" path from settings.
        :param missing: method names the class does not define.
        """
        super().__init__(class_path, f"does not satisfy {port}; missing {', '.join(missing)}")
        self.port = port
        self.class_path = class_path
        self.missing = missing
