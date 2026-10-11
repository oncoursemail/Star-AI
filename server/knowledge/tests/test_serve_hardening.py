"""Connection cap, absolute request deadlines and the search cache of the HTTP service.

Run on the PC:  python -m pytest -q server/knowledge/tests   (a tiny index is built in a temp folder;
no server, no model and no Luau tools are needed: only BM25 search is exercised).
"""
import json
from pathlib import Path
import socket
import sys
import threading
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from starkb import serve, store  # noqa: E402

KEY = b"test-key-not-a-real-one"


def build_index(path: Path) -> None:
    db = store.connect(path)
    db.execute(store.FTS)
    db.execute("INSERT INTO sources VALUES('creator-docs','https://example.invalid/docs.git','main','c0ffee',"
               "'2026-01-01T00:00:00+00:00','CC-BY-4.0','Example','2026-01-01T00:00:00+00:00')")
    doc = db.execute("INSERT INTO docs(source,path,kind,title,url) VALUES('creator-docs','content/en-us/a.md','guide',"
                     "'Tweens','https://example.invalid/a')").lastrowid
    for n, text in enumerate(["TweenService creates tweens for parts.", "Remote events cross the client-server boundary."]):
        rowid = db.execute("INSERT INTO chunks(doc_id,ord,kind,heading,anchor,text,idents,text_sha) VALUES(?,?,?,?,?,?,?,?)",
                           (doc, n, "guide", f"Section {n}", "", text, "", f"sha{n}")).lastrowid
        db.execute("INSERT INTO chunks_fts(rowid,title,heading,idents,text,questions) VALUES(?,?,?,?,?,?)",
                   (rowid, "Tweens", f"Section {n}", "", text, ""))
    db.execute("INSERT OR REPLACE INTO meta VALUES('built_at','2026-01-01T00:00:00+00:00')")
    db.commit()
    db.close()


@pytest.fixture()
def running(tmp_path, monkeypatch):
    monkeypatch.setattr(serve, "HEADER_DEADLINE", 0.6)
    monkeypatch.setattr(serve, "BODY_DEADLINE", 0.6)
    index = tmp_path / "kb.sqlite3"
    build_index(index)
    service = serve.Service(index, [KEY], brain=object())
    server = serve.Server(("127.0.0.1", 0), serve.make_handler(service), max_connections=4, max_per_client=3)
    service.server = server
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    try:
        yield service, server, server.server_address[1], index
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def connect(port: int) -> socket.socket:
    sock = socket.create_connection(("127.0.0.1", port), timeout=5)
    return sock


def read_all(sock: socket.socket, limit: float = 5.0) -> bytes:
    sock.settimeout(limit)
    data = b""
    try:
        while True:
            part = sock.recv(65536)
            if not part:
                break
            data += part
    except (TimeoutError, ConnectionError):
        pass
    return data


def post(port: int, path: str, body: dict, key: bytes = KEY) -> tuple[int, dict]:
    raw = json.dumps(body).encode()
    sock = connect(port)
    sock.sendall(b"POST " + path.encode() + b" HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer " + key +
                 b"\r\nContent-Type: application/json\r\nContent-Length: " + str(len(raw)).encode() + b"\r\n\r\n" + raw)
    data = read_all(sock)
    sock.close()
    head, _, payload = data.partition(b"\r\n\r\n")
    return int(head.split()[1]), json.loads(payload)


def test_an_idle_connection_is_dropped_at_the_header_deadline(running):
    _, _, port, _ = running
    sock = connect(port)
    started = time.monotonic()
    assert read_all(sock, 4.0) == b""          # closed by the server, nothing was sent
    assert time.monotonic() - started < 2.5
    sock.close()


def test_a_trickling_client_cannot_extend_the_header_deadline(running):
    _, _, port, _ = running
    sock = connect(port)
    started = time.monotonic()
    closed = False
    for byte in b"GET /health HTTP/1.1\r\nHost: abcdefghijklmnopqrstuvwxyz":
        try:
            sock.sendall(bytes([byte]))
        except OSError:
            closed = True
            break
        time.sleep(0.1)                         # every single read succeeds well inside a socket timeout
        if time.monotonic() - started > 3:
            break
    if not closed:
        closed = read_all(sock, 1.0) == b""
    assert closed and time.monotonic() - started < 3.5
    sock.close()


def test_a_body_that_never_arrives_is_given_up_after_the_body_deadline(running):
    service, _, port, _ = running
    sock = connect(port)
    sock.sendall(b"POST /search HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer " + KEY + b"\r\nContent-Length: 50\r\n\r\n{")
    started = time.monotonic()
    read_all(sock, 4.0)
    assert time.monotonic() - started < 2.5
    sock.close()
    time.sleep(0.1)
    assert service.counters.get("search:408") == 1


def test_one_client_cannot_hold_more_than_its_share_and_the_service_recovers(running):
    _, server, port, _ = running
    held = [connect(port) for _ in range(3)]    # three idle sockets: this client's whole share
    time.sleep(0.15)
    extra = connect(port)
    answer = read_all(extra, 2.0)
    extra.close()
    assert answer.startswith(b"HTTP/1.1 503") and answer.endswith(b'{"error":"busy"}')
    assert server.connection_stats()["refused"] == 1
    time.sleep(1.0)                             # the idle sockets run into the header deadline
    for sock in held:
        sock.close()
    status, reply = post(port, "/search", {"query": "tween", "mode": "bm25"})
    assert status == 200 and reply["passages"]
    assert server.connection_stats()["open"] <= 1


def test_a_repeated_search_is_served_from_the_cache_until_the_index_changes(running):
    service, _, port, index = running
    first = post(port, "/search", {"query": "remote  events", "mode": "bm25", "top": 3})[1]
    again = post(port, "/search", {"query": "remote events", "mode": "bm25", "top": 3})[1]   # same after whitespace
    other = post(port, "/search", {"query": "remote events", "mode": "bm25", "top": 2})[1]
    assert first["cached"] is False and again["cached"] is True and other["cached"] is False
    assert again["passages"] == first["passages"]
    db = store.connect(index)
    db.execute("INSERT OR REPLACE INTO meta VALUES('built_at','2026-02-02T00:00:00+00:00')")   # a rebuild
    db.commit()
    db.close()
    assert post(port, "/search", {"query": "remote events", "mode": "bm25", "top": 3})[1]["cached"] is False
    assert service.cache.stats()["hits"] == 1


def test_the_cache_forgets_old_and_surplus_entries():
    clock = [0.0]
    cache = serve.ResultCache(entries=2, ttl=10.0, clock=lambda: clock[0])
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1
    cache.put("c", 3)                           # "b" was used least recently
    assert cache.get("b") is None and cache.get("a") == 1 and cache.get("c") == 3
    clock[0] = 11.0
    assert cache.get("a") is None
