"""Durable no-replay barrier for host-bound Studio mutations.

Host code persists a token before dispatch and confirms only an exact successful
native receipt. This store grants no permission and exposes no model tools.
Reads and explicit play-stop cleanup do not require a successful ledger access.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import quote
from uuid import uuid4

KINDS = frozenset({"script", "luau", "play_start", "play_stop", "undo"})
APP_ID = 0x5354554E
MAX_DB_BYTES = 4 * 1024 * 1024
_TOKEN = re.compile(r"[0-9a-f]{32}")
_SCOPE = re.compile(r"[0-9a-f]{64}")
_INITIALIZED = b"STAR_STUDIO_UNCERTAINTY_V1\n"
_DDL = (
    "CREATE TABLE metadata (version INTEGER NOT NULL)",
    "CREATE TABLE pending (scope TEXT PRIMARY KEY, token TEXT NOT NULL UNIQUE, kind TEXT NOT NULL, created_at INTEGER NOT NULL)",
)


class StudioUncertaintyError(RuntimeError):
    """Bounded public error: no path, source, command or native identifier."""


class StudioWriteBlocked(StudioUncertaintyError):
    pass


@dataclass(frozen=True)
class StudioScope:
    route: str
    session: str
    place_id: int
    universe_id: int
    creator_id: int
    creator_type: str

    def __post_init__(self):
        if (type(self.route) is not str or self.route not in {"local_pc", "host_launcher"}
                or type(self.session) is not str or not 1 <= len(self.session) <= 160
                or self.session != self.session.strip()
                or any(ord(c) < 32 or ord(c) == 127 for c in self.session)
                or any(type(value) is not int or not 0 <= value < 2**63
                       for value in (self.place_id, self.universe_id, self.creator_id))
                or type(self.creator_type) is not str or self.creator_type not in {"User", "Group"}):
            raise StudioUncertaintyError("Studio mutation cannot be bound to a verified native session.")


def _key(scope):
    if type(scope) is not StudioScope:
        raise StudioUncertaintyError("Studio mutation cannot be bound to a verified native session.")
    scope.__post_init__()
    # A connector may assign a different Studio ID after reconnect. It is not a pin.
    payload = [scope.route, scope.session, scope.place_id, scope.universe_id,
               scope.creator_id, scope.creator_type]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _token(token):
    if type(token) is not str or _TOKEN.fullmatch(token) is None:
        raise StudioUncertaintyError("Invalid Studio mutation recovery token.")
    return token


class StudioUncertaintyStore:
    """Explicit host path, lazy disk access, no TTL, automatic retry or replay.

    Constructor performs no I/O: an unavailable ledger must not prevent reads or
    stop cleanup. Every mutation method fails closed when persistence is unsafe.
    Acknowledgement is for trusted host recovery after inspection, never a tool.
    """

    def __init__(self, path):
        self.path = Path(path).absolute()
        self.marker = self.path.with_name(self.path.name + ".initialized")
        self._seen = False

    def _prepare_path(self):
        """Missing prepared state is uncertainty, never a fresh reconnect.

        The fixed marker is committed before DB creation. A crash in between
        leaves a blocked orphan for explicit host inspection, not auto healing.
        Concurrent first initialization may fail closed until its owner finishes.
        """
        if self.path.is_symlink() or self.marker.is_symlink():
            raise OSError("unsafe ledger")
        database_exists, marker_exists = self.path.exists(), self.marker.exists()
        if database_exists or marker_exists:
            if not database_exists or not marker_exists:
                raise OSError("incomplete initialized ledger")
            if not self.marker.is_file() or self.marker.stat().st_size != len(_INITIALIZED):
                raise OSError("invalid initialized marker")
            with self.marker.open("rb") as stream:
                if stream.read(len(_INITIALIZED) + 1) != _INITIALIZED:
                    raise OSError("invalid initialized marker")
            return False
        if self._seen:
            raise OSError("missing ledger")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Never remove this marker on failure: doing so would make a crash look
        # like first use and could silently discard an uncertain mutation.
        fd = os.open(self.marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(_INITIALIZED)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name == "posix":
            directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        return True

    def _validate(self, connection):
        if (connection.execute("PRAGMA application_id").fetchone()[0] != APP_ID
                or connection.execute("PRAGMA user_version").fetchone()[0] != 1):
            raise StudioUncertaintyError("Studio uncertainty ledger is unavailable; mutations remain blocked.")
        rows = connection.execute("SELECT type, name, sql FROM sqlite_master WHERE NOT (type='index' AND name LIKE 'sqlite_autoindex_%' AND sql IS NULL) ORDER BY name").fetchall()
        expected = [("table", "metadata", _DDL[0]), ("table", "pending", _DDL[1])]
        if rows != expected or connection.execute("SELECT version FROM metadata").fetchall() != [(1,)]:
            raise StudioUncertaintyError("Studio uncertainty ledger is invalid; mutations remain blocked.")
        if connection.execute("PRAGMA quick_check(1)").fetchall() != [("ok",)]:
            raise StudioUncertaintyError("Studio uncertainty ledger is invalid; mutations remain blocked.")
        rows = connection.execute("SELECT scope,token,kind,created_at FROM pending LIMIT 10001").fetchall()
        if len(rows) > 10000 or any(type(scope) is not str or _SCOPE.fullmatch(scope) is None
                or type(token) is not str or _TOKEN.fullmatch(token) is None or kind not in KINDS
                or type(created) is not int or not 0 <= created < 10**12
                for scope, token, kind, created in rows):
            raise StudioUncertaintyError("Studio uncertainty ledger is invalid; mutations remain blocked.")

    @contextmanager
    def _open(self):
        connection = None
        try:
            created = self._prepare_path()
            if not self.path.is_file() or self.path.stat().st_size > MAX_DB_BYTES:
                raise OSError("invalid ledger")
            uri = "file:" + quote(self.path.as_posix(), safe="/:") + "?mode=rw"
            connection = sqlite3.connect(uri, uri=True, isolation_level=None, timeout=3)
            connection.execute("PRAGMA trusted_schema=OFF")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("BEGIN IMMEDIATE")
            if created:
                connection.execute(f"PRAGMA application_id={APP_ID}")
                connection.execute("PRAGMA user_version=1")
                for sql in _DDL:
                    connection.execute(sql)
                connection.execute("INSERT INTO metadata(version) VALUES (1)")
            self._validate(connection)
            self._seen = True
            yield connection
            connection.execute("COMMIT")
        except StudioUncertaintyError:
            raise
        except Exception:
            raise StudioUncertaintyError("Studio uncertainty ledger is unavailable; mutations remain blocked.") from None
        finally:
            if connection is not None:
                if connection.in_transaction:
                    connection.rollback()
                connection.close()

    def pending(self, scope):
        """Source-free host status; invalid stored records never authorize writes."""
        key = _key(scope)
        with self._open() as connection:
            rows = connection.execute("SELECT token, kind, created_at FROM pending WHERE scope=?", (key,)).fetchall()
            for token, kind, created in rows:
                if (_TOKEN.fullmatch(token or "") is None or kind not in KINDS
                        or type(created) is not int or not 0 <= created < 10**12):
                    raise StudioUncertaintyError("Studio uncertainty ledger is invalid; mutations remain blocked.")
            return [{"token": token, "kind": kind, "created_at": created} for token, kind, created in rows]

    def begin(self, scope, kind):
        """Commit pending before dispatch; one unresolved mutation blocks this scope."""
        key = _key(scope)
        if type(kind) is not str or kind not in KINDS:
            raise StudioUncertaintyError("Unsupported Studio mutation kind.")
        token = uuid4().hex
        with self._open() as connection:
            if connection.execute("SELECT 1 FROM pending WHERE scope=?", (key,)).fetchone():
                raise StudioWriteBlocked("An earlier Studio mutation is unresolved; host inspection is required before another write.")
            if connection.execute("SELECT count(*) FROM pending").fetchone()[0] >= 10000:
                raise StudioUncertaintyError("Studio uncertainty ledger is full; mutations remain blocked.")
            connection.execute("INSERT INTO pending(scope,token,kind,created_at) VALUES (?,?,?,?)", (key, token, kind, int(time.time())))
        return token

    def confirm(self, scope, token, *, known, ok):
        """Only exact native known+ok confirmation releases this exact pending token."""
        key, token = _key(scope), _token(token)
        with self._open() as connection:
            if known is not True or ok is not True:
                return False
            return connection.execute("DELETE FROM pending WHERE scope=? AND token=?", (key, token)).rowcount == 1

    def acknowledge(self, scope, token):
        """Trusted host inspected/reconciled this exact uncertainty; never model input."""
        key, token = _key(scope), _token(token)
        with self._open() as connection:
            return connection.execute("DELETE FROM pending WHERE scope=? AND token=?", (key, token)).rowcount == 1
