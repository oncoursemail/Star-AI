"""STAR Knowledge HTTP service (standard library only).

  GET  /health                       liveness, index counts, source commits            (no key)
  GET  /stats                        index and request counters                         (Bearer key)
  POST /search      {query, mode?, top?, per_page?}  cited passages from the official docs  (Bearer key)
  POST /api-lookup  {symbols: ["A:B", "C.D"]}   exact Roblox engine class/member lookup (Bearer key)
  POST /luau/check  {code, mode?}               compile + type-analyse, never executes  (Bearer key)
  POST /luau/run    {code, tests?, time_limit_s?, memory_limit_mb?}  opt-in sandbox run  (Bearer key)

The same routes also answer under /v1/ (the prototype's paths).

Hardening:
  * the bearer key is any line of the key file the STAR Brain uses; it is compared in constant
    time and never logged;
  * routes are an exact-match table and no request field is ever used as a file path, so there
    is nothing to traverse;
  * bodies need a Content-Length within a per-route limit; the embedding request and each Luau
    tool have their own time limits; concurrency is capped per route;
  * connections: at most MAX_CONNECTIONS sockets are served at once and at most MAX_PER_CLIENT
    per client address; one more is answered 503 from the accept loop without starting a thread.
    A connection has HEADER_DEADLINE seconds in total to deliver its request line and headers
    and BODY_DEADLINE more for the body (absolute deadlines, not per-read timeouts), so idle or
    trickling connections cannot hold the service;
  * repeated searches are answered from a small in-memory cache that is keyed by the index
    generation, so a refreshed index never serves old passages;
  * the access log has the route, status, duration and body size, never the query or the code
    (set STAR_KB_LOG_QUERIES=1 to add the first 80 characters of a query while debugging).
"""
from __future__ import annotations

from collections import OrderedDict
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import re
import sys
import threading
import time

from . import luaucheck, luaurun
from .client import Brain, DEFAULT_KEY_FILE
from .search import Searcher, VectorCache, built_stamp
from .store import now

SERVICE_MODES = ("vector", "bm25", "hybrid")   # rerank costs about 14 s per query and is not offered
DEFAULT_MODE = "vector"
MAX_BODY = 16_384
MAX_LUAU_BODY = 96 * 1024
MAX_QUERY = 600
MAX_TOP = 10
MAX_PER_PAGE = 3
# Passages one page may contribute to a reply. 2 is the long-standing default. With 1 the reply
# covers more pages: measured on the full index in `vector` mode, an expected page was in the
# top 5 for 37 instead of 35 of the 40 held-out questions and 15 instead of 14 of the 25 golden
# prompts (development set unchanged, 27 of 30). The price is the second section of the same page.
DEFAULT_PER_PAGE = int(os.environ.get("STAR_KB_PER_PAGE", "2"))
MAX_SYMBOLS = 40
SOCKET_TIMEOUT = 15.0           # one write may block this long
MAX_CONNECTIONS = int(os.environ.get("STAR_KB_MAX_CONNECTIONS", "48"))   # sockets served at once (one thread each)
MAX_PER_CLIENT = int(os.environ.get("STAR_KB_MAX_PER_CLIENT", "16"))     # ... of which one client address may hold
HEADER_DEADLINE = 5.0           # seconds from accept until the request line and all headers have arrived
BODY_DEADLINE = 10.0            # seconds from the end of the headers until the whole body has arrived
CACHE_ENTRIES = 512             # search-result cache size
CACHE_TTL = 900.0               # ... and the age (seconds) after which an entry is recomputed
VECTOR_RECHECK = 300.0          # how often the number of stored vectors is re-read (seconds); a rebuild is seen at once
_BUSY = (b"HTTP/1.1 503 Service Unavailable\r\nContent-Type: application/json\r\nContent-Length: 16\r\n"
         b"Retry-After: 1\r\nConnection: close\r\n\r\n" + b'{"error":"busy"}')
EMBED_TIMEOUT = 5.0             # below the desktop client's 8 s search timeout, so a busy brain degrades to BM25 in time
MAX_INFLIGHT = 32
DRAIN_LIMIT = 1024 * 1024       # an oversized body is read and dropped up to here, then refused
MAX_LUAU_INFLIGHT = 2
PASSAGE_TEXT = 900
_SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}(?:[.:][A-Za-z_][A-Za-z0-9_]{0,63}){0,2}$")
_INHERITS = re.compile(r"^Inherits: (.+)$", re.M)
GLOBAL_PAGES = ("Luau globals", "Roblox globals")   # print, require, typeof, game, workspace, script, ...


def _member_row(db, heading: str):
    return db.execute(
        """SELECT c.kind, c.heading, c.anchor, c.text, d.url, d.path, d.title, d.source
           FROM chunks c JOIN docs d ON d.id=c.doc_id
           WHERE c.heading=? AND c.kind IN ('api-member','api-overview','enum') ORDER BY c.ord LIMIT 1""",
        (heading,)).fetchone()


def api_lookup(db, symbols: list[str], sources: dict | None = None) -> list[dict]:
    """Exact lookup of `Class`, `Class.Member`, `Class:Member`, `Enum.Name`, `Enum.Name.Item` or a
    global (`print`, `workspace`) in the engine reference.

    A member that the class inherits (`Frame.BackgroundColor3`) is resolved through the
    "Inherits:" line of the class overview and reported with `inherited_from`. An enum item that
    the enum does not have is reported as not found.
    """
    out = []
    stamp = now()
    for raw in symbols[:MAX_SYMBOLS]:
        symbol = str(raw).strip()[:120]
        if not _SYMBOL.match(symbol):
            out.append({"symbol": symbol, "found": False, "reason": "not a Class, Class.Member or Class:Member name"})
            continue
        owner, _, member = symbol.replace(":", ".").partition(".")
        inherited_from = ""
        if owner == "Enum" and member:  # Enum.EasingStyle -> the enum page; Enum.EasingStyle.Linear -> its item
            enum, _, item = member.partition(".")
            row = _member_row(db, "Enum." + enum)
            if row is None and not item:   # Enum:GetEnumItems(): a method of the Enum data type itself
                row = _member_row(db, "Enum > " + enum)
            if row is not None and item:
                # an enum page lists its items as "- Enum.Name.Item = value"; a long enum spans several chunks
                row = db.execute(
                    """SELECT c.kind, c.heading, c.anchor, c.text, d.url, d.path, d.title, d.source
                       FROM chunks c JOIN docs d ON d.id=c.doc_id
                       WHERE c.heading=? AND c.kind='enum' AND instr(c.text, ?) > 0 ORDER BY c.ord LIMIT 1""",
                    ("Enum." + enum, f"- Enum.{enum}.{item} =")).fetchone()
                if row is None:
                    out.append({"symbol": symbol, "found": False, "reason": f"Enum.{enum} exists but has no item {item}"})
                    continue
        elif member:
            member = member.split(".")[0]
            row = _member_row(db, f"{owner} > {member}")
            if row is None:
                overview = _member_row(db, owner)
                chain = _INHERITS.search(overview["text"]) if overview is not None else None
                for parent in (re.split(r"\s*[>,]\s*", chain.group(1)) if chain else [])[:12]:
                    row = _member_row(db, f"{parent.strip()} > {member}")
                    if row is not None:
                        inherited_from = parent.strip()
                        break
        else:
            row = _member_row(db, owner) or _member_row(db, "Enum." + owner)
            for page in GLOBAL_PAGES if row is None else ():
                row = row or _member_row(db, f"{page} > {owner}")
        if row is None:
            out.append({"symbol": symbol, "found": False})
            continue
        src = (sources or {}).get(row["source"], {})
        item = {"symbol": symbol, "found": True, "kind": row["kind"], "heading": row["heading"],
                "title": row["title"], "signature": row["text"].split("\n", 1)[0][:300],
                "deprecated": "DEPRECATED" in row["text"],
                "url": row["url"] + ("#" + row["anchor"] if row["anchor"] else ""), "path": row["path"],
                "source": row["source"], "commit": src.get("commit_sha", ""), "licence": src.get("licence", ""),
                "retrieved_at": stamp, "text": row["text"][:PASSAGE_TEXT * 2]}
        if inherited_from:
            item["inherited_from"] = inherited_from
        out.append(item)
    return out


class ResultCache:
    """Small LRU for search replies. The key includes the index generation, so entries made on an
    older index are never returned; they age out."""

    def __init__(self, entries: int = CACHE_ENTRIES, ttl: float = CACHE_TTL, clock=time.monotonic):
        self.entries, self.ttl, self.clock = entries, ttl, clock
        self._items: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
        self.hits = self.misses = 0

    def get(self, key):
        with self._lock:
            item = self._items.get(key)
            if item is None or self.clock() - item[0] > self.ttl:
                self._items.pop(key, None)
                self.misses += 1
                return None
            self._items.move_to_end(key)
            self.hits += 1
            return item[1]

    def put(self, key, value) -> None:
        with self._lock:
            self._items[key] = (self.clock(), value)
            self._items.move_to_end(key)
            while len(self._items) > self.entries:
                self._items.popitem(last=False)

    def stats(self) -> dict:
        with self._lock:
            return {"entries": len(self._items), "max_entries": self.entries, "ttl_s": self.ttl,
                    "hits": self.hits, "misses": self.misses}


class DeadlineReader(io.RawIOBase):
    """Socket reads against an ABSOLUTE deadline. A socket timeout alone restarts with every read,
    so a client that sends one byte every few seconds would keep its thread for ever."""

    def __init__(self, sock, seconds: float):
        super().__init__()
        self._sock = sock
        self.deadline = time.monotonic() + seconds

    def extend(self, seconds: float) -> None:
        self.deadline = time.monotonic() + seconds

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int:
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError("request deadline passed")
        self._sock.settimeout(left)
        return self._sock.recv_into(buffer)


def load_keys(key_file: str) -> list[bytes]:
    path = Path(key_file)
    if not path.is_file():
        return []
    return [line.strip().encode() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class Service:
    """Shared state for all request threads."""

    def __init__(self, db_path: Path, keys: list[bytes], brain: Brain | None = None):
        self.db_path = db_path
        self.keys = keys
        self.brain = brain or Brain(timeout=EMBED_TIMEOUT, retries=1)
        self.vectors = VectorCache(recheck=VECTOR_RECHECK)
        self.started = time.time()
        self.inflight = threading.BoundedSemaphore(MAX_INFLIGHT)
        self.luau_slots = threading.BoundedSemaphore(MAX_LUAU_INFLIGHT)
        self.luau_runs = luaurun.RunService()
        self.counters: dict[str, int] = {}
        self._count_lock = threading.Lock()
        self.log_queries = os.environ.get("STAR_KB_LOG_QUERIES") == "1"
        self.cache = ResultCache()
        self.server: "Server | None" = None

    def generation(self, searcher: Searcher) -> tuple:
        """What a cached reply depends on: the index build (its stamp is read on every call, it
        is one row) and the vector set this process has loaded. A rebuilt index or newly loaded
        vectors therefore never get an old reply; within one loaded set a reply may be up to
        CACHE_TTL old."""
        searcher.embedded_count()   # loads or re-checks the shared vectors
        return (built_stamp(searcher.db), self.vectors.loaded_at)

    def count(self, name: str) -> None:
        with self._count_lock:
            self.counters[name] = self.counters.get(name, 0) + 1

    def authorized(self, header: str) -> bool:
        supplied = header.encode("utf-8", errors="replace")
        ok = False
        for key in self.keys:   # no early exit: every configured key is compared
            ok = hmac.compare_digest(supplied, b"Bearer " + key) or ok
        return ok

    def searcher(self) -> Searcher:
        return Searcher(self.db_path, brain=self.brain, vectors=self.vectors, readonly=True)

    # -- routes ------------------------------------------------------------------------------
    def health(self) -> dict:
        s = self.searcher()
        try:
            embedded = s.embedded_count()
            return {"ok": True, "service": "star-knowledge",
                    "sources": [{"name": n, "commit": v["commit_sha"], "commit_date": v["commit_date"],
                                 "indexed_at": v["indexed_at"], "licence": v["licence"]}
                                for n, v in s.sources.items()],
                    "chunks": s.chunk_count(), "embedded": embedded, "generated_questions": s.question_count(),
                    "modes": list(SERVICE_MODES), "default_mode": DEFAULT_MODE,
                    "luau_check": luaucheck.available()}
        finally:
            s.close()

    def stats(self) -> dict:
        s = self.searcher()
        try:
            db = s.db
            with self._count_lock:
                counters = dict(self.counters)
            return {
                "ok": True,
                "sources": [dict(r) for r in db.execute(
                    "SELECT name, repo, branch, commit_sha, commit_date, licence, attribution, indexed_at FROM sources")],
                "docs": db.execute("SELECT COUNT(*) FROM docs").fetchone()[0],
                "chunks": db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0],
                "chunks_by_kind": dict(db.execute("SELECT kind, COUNT(*) FROM chunks GROUP BY kind").fetchall()),
                "embedded": s.embedded_count(),
                "generated_questions": s.question_count(),
                "vectors_loaded_at": self.vectors.loaded_at,
                "modes": list(SERVICE_MODES), "default_mode": DEFAULT_MODE,
                "luau": {"available": luaucheck.available(), "version": luaucheck.tool_version(),
                         "max_code_bytes": luaucheck.MAX_CODE_BYTES, "timeout_s": luaucheck.TIMEOUT_SECONDS,
                         "memory_bytes": luaucheck.MEMORY_BYTES},
                "limits": {"max_body": MAX_BODY, "max_luau_body": MAX_LUAU_BODY, "max_query": MAX_QUERY,
                           "max_top": MAX_TOP, "max_per_page": MAX_PER_PAGE, "default_per_page": DEFAULT_PER_PAGE,
                           "embed_timeout_s": EMBED_TIMEOUT,
                           "max_connections": MAX_CONNECTIONS, "max_per_client": MAX_PER_CLIENT,
                           "header_deadline_s": HEADER_DEADLINE, "body_deadline_s": BODY_DEADLINE},
                "connections": self.server.connection_stats() if self.server is not None else {},
                "search_cache": self.cache.stats(),
                "uptime_s": int(time.time() - self.started),
                "requests": counters,
            }
        finally:
            s.close()

    def search(self, body: dict) -> tuple[int, dict]:
        query = body.get("query")
        mode = body.get("mode", DEFAULT_MODE)
        top = body.get("top", 5)
        per_page = body.get("per_page", DEFAULT_PER_PAGE)
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= MAX_QUERY:
            return 400, {"error": f"query must be 1..{MAX_QUERY} characters"}
        if mode not in SERVICE_MODES or type(top) is not int or not 1 <= top <= MAX_TOP:
            return 400, {"error": "mode must be one of " + ", ".join(SERVICE_MODES) + f" and top 1..{MAX_TOP}"}
        if type(per_page) is not int or not 1 <= per_page <= MAX_PER_PAGE:
            return 400, {"error": f"per_page must be 1..{MAX_PER_PAGE}"}
        query = " ".join(query.split())
        started = time.perf_counter()
        s = self.searcher()
        try:
            key = (self.generation(s), mode, top, per_page, query)
            hit = self.cache.get(key)
            if hit is not None:
                return 200, {**hit, "cached": True,
                             "timing_ms": {"total_ms": round((time.perf_counter() - started) * 1000, 1)}}
            passages, timing = s.search(query, mode=mode, top=top, per_doc=per_page, fallback=True, degrade=True)
            degraded = bool(timing.pop("degraded", 0))
            reply = {
                "mode": mode, "mode_used": "bm25" if degraded else mode, "degraded": degraded,
                "timing_ms": timing, "untrusted": True, "cached": False,
                "index": {"chunks": s.chunk_count(), "embedded": s.embedded_count()},
                "attribution": {n: v["attribution"] for n, v in s.sources.items()},
                "passages": [p.as_dict() for p in passages]}
            if not degraded and not timing.get("fallback_failed"):   # only a full-quality reply is worth repeating
                self.cache.put(key, reply)
            return 200, reply
        finally:
            s.close()

    def lookup(self, body: dict) -> tuple[int, dict]:
        symbols = body.get("symbols")
        if (not isinstance(symbols, list) or not 1 <= len(symbols) <= MAX_SYMBOLS
                or not all(isinstance(item, str) for item in symbols)):
            return 400, {"error": f"symbols must be a list of 1..{MAX_SYMBOLS} names"}
        s = self.searcher()
        try:
            return 200, {"untrusted": True, "results": api_lookup(s.db, symbols, s.sources)}
        finally:
            s.close()

    def luau(self, body: dict) -> tuple[int, dict]:
        code = body.get("code")
        mode = body.get("mode")
        if not isinstance(code, str) or (mode is not None and mode not in ("strict", "nonstrict")):
            return 400, {"error": "code must be text and mode strict or nonstrict"}
        if not self.luau_slots.acquire(blocking=True, timeout=5):
            return 503, {"error": "busy"}
        s = None
        try:
            # The index knows every engine class, data type and enum; the standalone type checker
            # knows none, so `player: Player` must not count as an error in the code.
            s = self.searcher()
            return 200, luaucheck.check(code, mode=mode, known_type=lambda name: luaucheck.is_engine_type(s.db, name))
        except ValueError as exc:
            return 400, {"error": str(exc)}
        except RuntimeError:
            return 503, {"error": "Luau tools are not installed on this server"}
        finally:
            if s is not None:
                s.close()
            self.luau_slots.release()


ROUTES = {
    ("GET", "/health"): ("health", False, 0),
    ("GET", "/stats"): ("stats", True, 0),
    ("POST", "/search"): ("search", True, MAX_BODY),
    ("POST", "/api-lookup"): ("lookup", True, MAX_BODY),
    ("POST", "/luau/check"): ("luau", True, MAX_LUAU_BODY),
    ("POST", "/luau/run"): ("luau_run", True, MAX_LUAU_BODY),
}


def make_handler(service: Service):
    class Handler(BaseHTTPRequestHandler):
        server_version = "star-knowledge/1.0"
        sys_version = ""
        protocol_version = "HTTP/1.1"
        timeout = SOCKET_TIMEOUT

        def setup(self):
            super().setup()
            try:
                self.rfile.close()
            except Exception:
                pass
            self._reader = DeadlineReader(self.connection, HEADER_DEADLINE)
            self.rfile = io.BufferedReader(self._reader, 65536)

        def log_message(self, fmt, *args):  # the default access log would print the raw request line
            pass

        def log_error(self, fmt, *args):    # the base class reports a request-line/header timeout here
            if "timed out" in fmt:
                service.count("other:408")
                print(f"{now()} - other 408 header deadline", flush=True)

        def _send(self, status: int, body: dict) -> None:
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.connection.settimeout(SOCKET_TIMEOUT)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(raw)
            self.close_connection = True

        def _handle(self, method: str) -> None:
            started = time.perf_counter()
            path = self.path.split("?", 1)[0]
            if path.startswith("/v1/"):
                path = path[3:]
            route = ROUTES.get((method, path))
            name, status, size, extra = (route[0] if route else "other"), 500, 0, ""
            self._reader.extend(BODY_DEADLINE)   # the headers arrived in time; the body gets its own deadline
            if not service.inflight.acquire(blocking=False):
                self._send(503, {"error": "busy"})
                return
            try:
                if route is None:
                    status = 404
                    return self._send(404, {"error": "not found"})
                _, needs_key, limit = route
                if needs_key and not service.authorized(self.headers.get("Authorization", "")):
                    status = 401
                    return self._send(401, {"error": "unauthorized"})
                body: dict = {}
                if method == "POST":
                    try:
                        size = int(self.headers.get("Content-Length", ""))
                    except ValueError:
                        size = -1
                    if not 0 < size <= limit:
                        status = 413 if size > limit else 411
                        # read (and drop) a bounded amount so the client gets the answer, not a reset
                        left = min(max(size, 0), DRAIN_LIMIT)
                        while left > 0:
                            chunk = self.rfile.read(min(left, 65536))
                            if not chunk:
                                break
                            left -= len(chunk)
                        return self._send(status, {"error": f"send a JSON body of 1..{limit} bytes with Content-Length"})
                    try:
                        body = json.loads(self.rfile.read(size))
                        if not isinstance(body, dict):
                            raise ValueError
                    except (ValueError, UnicodeDecodeError):
                        status = 400
                        return self._send(400, {"error": "invalid JSON object"})
                if name == "health":
                    status, reply = 200, service.health()
                elif name == "stats":
                    status, reply = 200, service.stats()
                elif name == "luau_run":
                    status, reply = service.luau_runs.handle(body, str(self.client_address[0]))
                else:
                    status, reply = getattr(service, name)(body)
                    if name == "search" and service.log_queries and isinstance(body.get("query"), str):
                        extra = " q=" + json.dumps(body["query"][:80])
                if reply.get("cached"):
                    extra += " cache=hit"
                self._send(status, reply)
            except TimeoutError:                # the body did not arrive before its deadline
                status = 408
                self.close_connection = True
            except (BrokenPipeError, ConnectionError):
                status = 499
            except Exception as exc:  # never leak internals; the type name is enough to diagnose
                status = 500
                extra = " exc=" + type(exc).__name__
                try:
                    self._send(500, {"error": "internal error"})
                except Exception:
                    pass
            finally:
                service.inflight.release()
                service.count(f"{name}:{status}")
                print(f"{now()} {method} {name} {status} {int((time.perf_counter() - started) * 1000)}ms "
                      f"in={size}{extra}", flush=True)

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

    return Handler


class Server(ThreadingHTTPServer):
    """One thread per connection, but never more than `max_connections` of them, and never more
    than `max_per_client` for one client address. A connection over a limit gets a fixed 503 from
    the accept loop (non-blocking) and is closed; no thread is started for it."""
    daemon_threads = True
    request_queue_size = 64

    def __init__(self, address, handler, *, max_connections: int = MAX_CONNECTIONS,
                 max_per_client: int = MAX_PER_CLIENT):
        super().__init__(address, handler)
        self.max_connections = max_connections
        self.max_per_client = max_per_client
        self._conn_lock = threading.Lock()
        self._open = 0
        self._per_client: dict[str, int] = {}
        self.refused = 0
        self.peak = 0

    def connection_stats(self) -> dict:
        with self._conn_lock:
            return {"open": self._open, "peak": self.peak, "refused": self.refused}

    def _release(self, host: str) -> None:
        with self._conn_lock:
            self._open -= 1
            left = self._per_client.get(host, 1) - 1
            if left > 0:
                self._per_client[host] = left
            else:
                self._per_client.pop(host, None)

    def process_request(self, request, client_address):
        host = str(client_address[0])
        with self._conn_lock:
            ok = self._open < self.max_connections and self._per_client.get(host, 0) < self.max_per_client
            if ok:
                self._open += 1
                self.peak = max(self.peak, self._open)
                self._per_client[host] = self._per_client.get(host, 0) + 1
            else:
                self.refused += 1
        if not ok:
            try:
                request.setblocking(False)   # the accept loop must never wait for a client
                request.send(_BUSY)
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._release(host)
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._release(str(client_address[0]))


def serve(db_path: Path, host: str = "127.0.0.1", port: int = 8091, key_file: str = DEFAULT_KEY_FILE) -> None:
    keys = load_keys(key_file)
    if not keys:
        raise SystemExit("refusing to start without an API key file")
    if not db_path.is_file():
        raise SystemExit("refusing to start without an index (run: python -m starkb build)")
    service = Service(db_path, keys)
    service.health()   # load the vectors once before accepting requests; fails fast on a broken index
    server = Server((host, port), make_handler(service))
    service.server = server
    print(f"star-knowledge listening on http://{host}:{port} luau_check={luaucheck.available()} "
          f"max_connections={server.max_connections} per_client={server.max_per_client}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    sys.exit("run: python -m starkb serve")
