"""Exercise the actual HTTP handler, authorization and socket-derived admission key."""
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
import importlib.util
import json
from pathlib import Path
import secrets
import sys
import threading
from types import ModuleType

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server" / "knowledge"))
from starkb import luaurun


@pytest.fixture
def http_module(monkeypatch):
    # The document index needs server-only numpy/yaml packages. This route never
    # reads it: substitute only those unrelated imports, not Service, the real
    # HTTP handler, authorization, the queue or the runner. Keep substitutions
    # scoped so other service tests cannot inherit them.
    search = ModuleType("starkb.search")
    def no_documents(*args, **kwargs):
        pytest.fail("the run route touched document retrieval")
    search.Searcher = no_documents
    search.VectorCache = lambda **kwargs: object()
    search.built_stamp = no_documents
    store = ModuleType("starkb.store")
    store.now = lambda: "test"
    path = Path(__file__).resolve().parents[1] / "server" / "knowledge" / "starkb" / "serve.py"
    spec = importlib.util.spec_from_file_location("starkb._run_http_test", path)
    module = importlib.util.module_from_spec(spec)
    with monkeypatch.context() as patch:
        patch.setitem(sys.modules, "starkb.search", search)
        patch.setitem(sys.modules, "starkb.store", store)
        spec.loader.exec_module(module)
    return module


@pytest.fixture
def service(tmp_path, monkeypatch, http_module):
    monkeypatch.delenv("STAR_KB_LUAU_RUN", raising=False)
    token = secrets.token_hex(24)
    state = http_module.Service(tmp_path / "unused.sqlite3", [token.encode()], brain=object())
    server = http_module.Server(("127.0.0.1", 0), http_module.make_handler(state))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    def post(body=None, *, auth=True, path="/luau/run", headers=None):
        conn = HTTPConnection(*server.server_address, timeout=3)
        raw = json.dumps(body if body is not None else {"code": "return 42"})
        fields = {"Content-Type": "application/json", **(headers or {})}
        if auth:
            fields["Authorization"] = "Bearer " + token
        try:
            conn.request("POST", path, body=raw, headers=fields)
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()
    try:
        yield state, post
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


def test_http_auth_and_disabled_default(service):
    state, post = service
    assert post(auth=False)[0] == 401
    status, reply = post()
    assert status == 503 and reply["executed"] is False


def test_http_path_and_validation(service, http_module):
    state, post = service
    calls = []
    def runner(*args, **kwargs):
        calls.append((args, kwargs))
        return {"ok": True, "executed": True, "status": "pass"}
    state.luau_runs = luaurun.RunService(enabled=True, runner=runner)
    assert post(path="/v1/luau/run")[0] == 200
    assert post({"code": "return 1", "time_limit_s": False})[0] == 400
    assert post({"code": "x" * http_module.MAX_LUAU_BODY})[0] == 413
    assert post(path="/luau/run/extra")[0] == 404
    assert post(auth=False)[0] == 401
    assert len(calls) == 1


def test_http_cannot_spoof_client_and_recovers(service):
    state, post = service
    entered, release = threading.Event(), threading.Event()
    def runner(*args, **kwargs):
        entered.set()
        assert release.wait(2)
        return {"ok": True, "executed": True, "status": "pass"}
    state.luau_runs = luaurun.RunService(enabled=True, runner=runner)
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(post)
        assert entered.wait(2)
        try:
            status, reply = post({"code": "return 1", "client": "different"},
                                 headers={"X-Forwarded-For": "different"})
            assert status == 429 and reply["executed"] is False
        finally:
            release.set()
        assert first.result()[0] == 200
    assert post()[0] == 200
