"""Offline regression tests for packaged Windows smoke helper."""
import base64
import hashlib
import importlib.util
from pathlib import Path
import socket
import sqlite3
import struct
import threading

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "packaged_smoke.py"
spec = importlib.util.spec_from_file_location("packaged_smoke", SCRIPT)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def frame(payload: bytes, opcode=1, final=True):
    size = len(payload)
    length = (bytes([size]) if size < 126 else
              bytes([126]) + struct.pack(">H", size) if size < 65536 else
              bytes([127]) + struct.pack(">Q", size))
    return bytes([(0x80 if final else 0) | opcode]) + length + payload


def receive_exact(sock, count):
    data = b""
    while len(data) < count:
        piece = sock.recv(count - len(data))
        if not piece:
            raise EOFError
        data += piece
    return data


def server(sock, observed):
    try:
        data = b""
        while b"\r\n\r\n" not in data:
            data += sock.recv(4096)
        key = next(line.split(b":", 1)[1].strip() for line in data.split(b"\r\n")
                   if line.lower().startswith(b"sec-websocket-key:"))
        accept = base64.b64encode(hashlib.sha1(
            key + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest())
        sock.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
                     b"Connection: Upgrade\r\nSec-WebSocket-Accept: " + accept + b"\r\n\r\n")
        first, second = receive_exact(sock, 2)
        assert first & 15 == 1 and second & 128
        length = second & 127
        if length == 126:
            length = struct.unpack(">H", receive_exact(sock, 2))[0]
        elif length == 127:
            length = struct.unpack(">Q", receive_exact(sock, 8))[0]
        mask = receive_exact(sock, 4)
        payload = receive_exact(sock, length)
        import json
        command = json.loads(bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))
        observed.append(command)
        sock.sendall(frame(b"ping", 9) + frame(b'{"id":1,"result":{"payload":"', final=False))
        body = b"x" * 66000
        sock.sendall(frame(body, 0, final=False) + frame(b'"}}', 0))
        first, second = receive_exact(sock, 2)
        assert first & 15 == 10 and second & 128
        mask = receive_exact(sock, 4)
        assert bytes(b ^ mask[i % 4] for i, b in enumerate(receive_exact(sock, second & 127))) == b"ping"
    except Exception as error:
        observed.append(error)
    finally:
        sock.close()


def test_cdp_handshake_masked_frames_ping_fragmented_and_large():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    observed = []

    def accept():
        connection, _ = listener.accept()
        server(connection, observed)

    thread = threading.Thread(target=accept)
    thread.start()
    try:
        with smoke.CDP(f"ws://127.0.0.1:{listener.getsockname()[1]}/devtools/page/1") as client:
            answer = client.call("Runtime.enable")
        assert answer["payload"] == "x" * 66000
    finally:
        thread.join(timeout=5)
        listener.close()
    assert len(observed) == 1
    assert observed[0]["method"] == "Runtime.enable"


def test_refuses_real_profile(tmp_path, monkeypatch):
    real = tmp_path / "actual" / "Roaming"
    (real / "STAR").mkdir(parents=True)
    (tmp_path / "copy" / "Roaming" / "STAR").mkdir(parents=True)
    assert not smoke.safe_profile_root(tmp_path / "actual", str(real))
    assert smoke.safe_profile_root(tmp_path / "copy", str(real))
    monkeypatch.setenv("APPDATA", str(real))
    assert smoke.main(["--exe", "unused", "--profile-root", str(tmp_path / "actual"),
                       "--endpoint", "http://127.0.0.1", "--key-file", "unused",
                       "--shots", str(tmp_path / "shots")]) == 2


def test_key_file_bare_assignment_and_equals(tmp_path):
    file = tmp_path / "key"
    for raw, expected in [("abc=def==\n", "abc=def=="), ("STAR_SERVER_API_KEY=abc=def==\n", "abc=def=="),
                          ("_KEY=has=more=equals\n", "has=more=equals")]:
        file.write_text(raw, encoding="utf-8")
        assert smoke.read_key_file(file) == expected


def test_database_uses_messages_role_and_body(tmp_path):
    db = tmp_path / "conversations.sqlite3"
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE messages (role TEXT, body TEXT)")
        con.executemany("INSERT INTO messages VALUES (?, ?)",
                        [("user", "ACCEPT-MARKER-0002: hello"),
                         ("assistant", "ACCEPT-MARKER-0002"), ("user", "other")])
    assert smoke.count_saved_prompt(db, "ACCEPT-MARKER-0002") == 1
