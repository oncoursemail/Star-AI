"""Desktop instance ownership without Qt, network, database, or keyring."""
from pathlib import Path

import pytest

from star.single_instance import DesktopInstance, bypass_single_instance, instance_identity


class Signal:
    def __init__(self):
        self.callback = None

    def connect(self, callback):
        self.callback = callback


class FakeQt:
    locks = set()
    servers = {}
    stale = set()

    class Lock:
        def __init__(self, path):
            self.path = path

        def setStaleLockTime(self, value):
            assert value == 0

        def tryLock(self, timeout):
            if self.path in FakeQt.stale:
                FakeQt.stale.remove(self.path)
                FakeQt.locks.discard(self.path)
            if self.path in FakeQt.locks:
                return False
            FakeQt.locks.add(self.path)
            return True

        def unlock(self):
            FakeQt.locks.remove(self.path)

    class Server:
        def __init__(self):
            self.newConnection = Signal()
            self.pending = []
            self.name = None

        def listen(self, name):
            if name in FakeQt.servers:
                return False
            self.name = name
            FakeQt.servers[name] = self
            return True

        @staticmethod
        def removeServer(name):
            FakeQt.servers.pop(name, None)

        def hasPendingConnections(self):
            return bool(self.pending)

        def nextPendingConnection(self):
            return self.pending.pop(0)

        def close(self):
            FakeQt.servers.pop(self.name, None)

    class Socket:
        def __init__(self):
            self.server = None
            self.payload = b""

        def connectToServer(self, name):
            self.server = FakeQt.servers.get(name)

        def waitForConnected(self, timeout):
            return self.server is not None

        def write(self, payload):
            self.payload = payload
            return len(payload)

        def waitForBytesWritten(self, timeout):
            peer = FakeQt.Peer(self.payload)
            self.server.pending.append(peer)
            self.server.newConnection.callback()
            return True

        def disconnectFromServer(self):
            pass

    class Peer:
        def __init__(self, payload):
            self.payload = payload

        def waitForReadyRead(self, timeout):
            return True

        def readAll(self):
            return self.payload

        def disconnectFromServer(self):
            pass

        def deleteLater(self):
            pass


@pytest.fixture(autouse=True)
def clean_fake_qt():
    FakeQt.locks.clear()
    FakeQt.servers.clear()
    FakeQt.stale.clear()
    yield
    FakeQt.locks.clear()
    FakeQt.servers.clear()
    FakeQt.stale.clear()


def start(folder, activation):
    return DesktopInstance(folder, activation, lock_type=FakeQt.Lock,
                           server_type=FakeQt.Server, socket_type=FakeQt.Socket,
                           attempts=1)


def test_first_start_acquires_and_second_signals_without_becoming_owner(tmp_path):
    focused = []
    first = start(tmp_path, lambda: focused.append(True))
    assert first.primary
    second = start(tmp_path, lambda: None)
    assert not second.primary
    assert focused == [True]
    second.close()
    first.close()
    assert start(tmp_path, lambda: None).primary


def test_stale_lock_and_socket_recovered(tmp_path):
    name, lock_path = instance_identity(tmp_path)
    FakeQt.locks.add(str(lock_path))
    FakeQt.stale.add(str(lock_path))
    FakeQt.servers[name] = object()
    first = start(tmp_path, lambda: None)
    assert first.primary
    first.close()


def test_doctors_and_test_harness_unaffected():
    for doctor in ("--doctor", "--ui-doctor", "--build-doctor"):
        assert bypass_single_instance(["star_desktop.py", doctor], {})
    assert bypass_single_instance(["star_desktop.py"], {"PYTEST_CURRENT_TEST": "case"})


def test_explicit_opt_out_and_normal_launch():
    assert bypass_single_instance(["star_desktop.py"], {"STAR_ALLOW_MULTIPLE_INSTANCES": "1"})
    assert not bypass_single_instance(["star_desktop.py"], {})


def test_isolation_by_user_and_folder(tmp_path):
    assert instance_identity(tmp_path, "account-a") != instance_identity(tmp_path, "account-b")
    assert instance_identity(tmp_path, "account-a") != instance_identity(tmp_path / "other", "account-a")


def test_unreachable_owner_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr("star.single_instance.time.sleep", lambda delay: None)
    _, path = instance_identity(tmp_path)
    FakeQt.locks.add(str(path))
    with pytest.raises(RuntimeError, match="could not be contacted"):
        start(tmp_path, lambda: None)
