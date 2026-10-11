"""Live check of the connection limits of a running star-knowledge service (not a pytest file).

    python server/knowledge/tests/live_hardening.py http://192.168.1.20:8091 [path-to-key-file]

Opens idle and trickling connections for a few seconds and prints one JSON object. The key is read
from the file (default ~/.star/server_api_key) and is never printed. It needs about 15 seconds and
holds at most one client's share of connections, so other clients keep being served.
"""
import http.client
import json
from pathlib import Path
import socket
import sys
import time
from urllib.parse import urlsplit


def main() -> int:
    base = urlsplit(sys.argv[1])
    host, port = base.hostname, base.port or 80
    key_file = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.home() / ".star" / "server_api_key"
    key = key_file.read_text(encoding="utf-8").splitlines()[0].strip()
    out: dict = {}

    def call(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        conn = http.client.HTTPConnection(host, port, timeout=20)
        raw = json.dumps(body).encode() if body is not None else None
        headers = {"Authorization": "Bearer " + key}
        if raw:
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=raw, headers=headers)
        response = conn.getresponse()
        data = json.loads(response.read() or b"{}")
        conn.close()
        return response.status, data

    limits = call("GET", "/stats")[1]["limits"]
    out["limits"] = {k: limits.get(k) for k in ("max_connections", "max_per_client", "header_deadline_s", "body_deadline_s")}
    share = int(limits["max_per_client"])

    # 1. an idle connection is closed at the header deadline
    sock = socket.create_connection((host, port), timeout=30)
    started = time.monotonic()
    try:
        data = sock.recv(100)
    except OSError:
        data = b"error"
    out["idle_socket_closed_after_s"] = round(time.monotonic() - started, 2)
    out["idle_socket_got_bytes"] = len(data)
    sock.close()

    # 2. a client that sends one byte per second does not get more time
    sock = socket.create_connection((host, port), timeout=30)
    started = time.monotonic()
    closed = False
    for byte in b"GET /health HTTP/1.1\r\nHost: abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz":
        try:
            sock.sendall(bytes([byte]))
            sock.settimeout(1.0)
            try:
                if sock.recv(100) == b"":
                    closed = True
                    break
            except TimeoutError:
                pass
        except OSError:
            closed = True
            break
        if time.monotonic() - started > 25:
            break
    out["trickle_closed"] = closed
    out["trickle_closed_after_s"] = round(time.monotonic() - started, 2)
    sock.close()

    # 3. this client's whole share of idle sockets, then four more: those must get 503 at once,
    #    and a normal request must work again as soon as the idle ones have been dropped
    held = [socket.create_connection((host, port), timeout=30) for _ in range(share)]
    time.sleep(0.3)
    refused, refuse_ms = 0, []
    for _ in range(4):
        t = time.monotonic()
        extra = socket.create_connection((host, port), timeout=10)
        try:
            answer = extra.recv(400)
        except OSError:
            answer = b""
        refuse_ms.append(round((time.monotonic() - t) * 1000))
        refused += answer.startswith(b"HTTP/1.1 503")
        extra.close()
    out["over_share_refused_503"] = f"{refused}/4"
    out["over_share_answer_ms"] = refuse_ms
    started = time.monotonic()
    while time.monotonic() - started < 20:
        try:
            status, _ = call("GET", "/health")
        except (OSError, http.client.HTTPException, ValueError):
            status = 0
        if status == 200:
            break
        time.sleep(0.5)
    out["served_again_after_s"] = round(time.monotonic() - started + 0.3, 2)
    for sock in held:
        sock.close()

    # 4. the cache: the same search twice
    query = {"query": "how do I tween a part", "mode": "bm25", "top": 3}
    first = call("POST", "/search", query)[1]
    second = call("POST", "/search", query)[1]
    out["search_first"] = {"cached": first.get("cached"), "total_ms": first["timing_ms"]["total_ms"]}
    out["search_second"] = {"cached": second.get("cached"), "total_ms": second["timing_ms"]["total_ms"],
                            "same_passages": first["passages"] == second["passages"]}
    stats = call("GET", "/stats")[1]
    out["connections"] = stats.get("connections")
    out["search_cache"] = stats.get("search_cache")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
