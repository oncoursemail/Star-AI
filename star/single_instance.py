"""Single desktop owner and activation channel; no database access."""
from __future__ import annotations

import getpass
import hashlib
import os
from pathlib import Path
import tempfile
import time


def instance_identity(home: Path, user: str | None = None) -> tuple[str, Path]:
    """Keep both Qt IPC and the lock distinct for each user/data folder."""
    folder = str(Path(home).expanduser().resolve()).casefold()
    account = user if user is not None else getpass.getuser()
    digest = hashlib.sha256((account.casefold() + "\0" + folder).encode("utf-8")).hexdigest()[:32]
    name = "star-desktop-" + digest
    return name, Path(tempfile.gettempdir()) / (name + ".lock")


def bypass_single_instance(argv=None, environ=None) -> bool:
    args = argv if argv is not None else __import__("sys").argv
    env = environ if environ is not None else os.environ
    return (env.get("STAR_ALLOW_MULTIPLE_INSTANCES", "").strip().lower() in {"1", "true", "yes"}
            or any(flag in args for flag in (
                "--doctor", "--ui-doctor", "--build-doctor", "--document-doctor"))
            or "PYTEST_CURRENT_TEST" in env)


class DesktopInstance:
    """Hold the lock until shutdown and listen for activation from later launches."""

    def __init__(self, home: Path, on_activate, *, lock_type=None,
                 server_type=None, socket_type=None, attempts=20):
        if lock_type is None:
            from PySide6.QtCore import QLockFile
            from PySide6.QtNetwork import QLocalServer, QLocalSocket
            lock_type, server_type, socket_type = QLockFile, QLocalServer, QLocalSocket
        self.name, lock_path = instance_identity(home)
        self.lock = lock_type(str(lock_path))
        self.lock.setStaleLockTime(0)  # PID-based stale detection, not elapsed wall time
        self.server = None
        self.primary = False
        self._socket_type = socket_type
        if self.lock.tryLock(0):
            self._start_server(server_type, on_activate)
            self.primary = True
            return
        for _ in range(attempts):
            socket = socket_type()
            socket.connectToServer(self.name)
            if socket.waitForConnected(1000):
                socket.write(b"activate")
                socket.waitForBytesWritten(1000)
                socket.disconnectFromServer()
                return
            time.sleep(0.1)
        # Never open the database without exclusive ownership.
        raise RuntimeError("An existing STAR window owns this data folder but could not be contacted")

    def _start_server(self, server_type, on_activate):
        # QLocalServer.removeServer handles a socket name orphaned by a crash.
        # Only the lock owner may remove an old endpoint.
        self.server = server_type()
        if not self.server.listen(self.name):
            server_type.removeServer(self.name)
            if not self.server.listen(self.name):
                self.lock.unlock()
                raise RuntimeError("Could not create STAR desktop activation channel")

        def accept():
            while self.server.hasPendingConnections():
                peer = self.server.nextPendingConnection()
                peer.waitForReadyRead(100)
                if bytes(peer.readAll()) == b"activate":
                    on_activate()
                peer.disconnectFromServer()
                peer.deleteLater()
        self.server.newConnection.connect(accept)

    def close(self):
        if self.primary:
            self.server.close()
            self.lock.unlock()
            self.primary = False
