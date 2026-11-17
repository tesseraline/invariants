"""Block network access while promised functions run (a safety net).

`tesseraline-invariants/src/tesseraline_invariants/infrastructure/network_block.py`

`socket.socket.connect`, `connect_ex` and `getaddrinfo` raise `NetworkBlockedError` naming the host
only. Local Unix sockets stay allowed. This is a safety net, not a sandbox: code that bypasses the
socket module is not stopped.
"""

from __future__ import annotations

import atexit
import os
import shutil
import socket
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from tesseraline_invariants.domain.exceptions import NetworkBlockedError

if TYPE_CHECKING:
    from collections.abc import Iterator


@contextmanager
def blocked_network() -> Iterator[None]:
    """Run the block with outward network calls refused.

    Examples:
        >>> import socket
        >>> with blocked_network():
        ...     socket.getaddrinfo("example.org", 443)
        Traceback (most recent call last):
        tesseraline_invariants...NetworkBlockedError: attempted network access to example.org
    """
    original = (socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo)

    def refuse_connect(self: socket.socket, address: object, *_: object) -> None:
        if self.family == getattr(socket, "AF_UNIX", None):
            return original[0](self, address)  # type: ignore[arg-type]
        raise NetworkBlockedError(str(address[0] if isinstance(address, tuple) else address))

    def refuse_lookup(host: object, *_: object, **__: object) -> list[object]:
        raise NetworkBlockedError(str(host))

    socket.socket.connect = refuse_connect  # type: ignore[assignment,method-assign]
    socket.socket.connect_ex = refuse_connect  # type: ignore[assignment,method-assign]
    socket.getaddrinfo = refuse_lookup  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo = original  # type: ignore[method-assign]


@contextmanager
def isolated(workdir: str) -> Iterator[None]:
    """Run the block in a temporary working folder, outward network refused (decision 0001).

    :param workdir: a folder made for this check; relative writes land there, not in the project.

    Examples:
        >>> import os, tempfile
        >>> here = os.getcwd()
        >>> with isolated(tempfile.mkdtemp()):
        ...     os.getcwd() != here
        True
    """
    before = Path.cwd()
    os.chdir(workdir)
    try:
        with blocked_network():
            yield
    finally:
        os.chdir(before)


def check_workdir() -> str:
    """A new temporary folder for one check's calls, removed when the process ends."""
    folder = tempfile.mkdtemp(prefix="invariants-check-")
    atexit.register(shutil.rmtree, folder, ignore_errors=True)
    return folder
