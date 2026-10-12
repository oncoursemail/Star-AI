"""Real ASGI authentication and MCP roundtrip; no socket or live services."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import secrets
import sys

import pytest

SPEC = importlib.util.spec_from_file_location(
    "star_workbench_http_app", Path(__file__).parents[1] / "server/workbench/app.py")
app = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = app
SPEC.loader.exec_module(app)
pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux workbench")


async def request(gate, path, token=None, data=b"{}", origin=None):
    httpx = pytest.importorskip("httpx")
    headers = {"content-type": "application/json", "accept": "application/json, text/event-stream"}
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    if origin:
        headers["origin"] = origin
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gate), base_url="http://testserver") as client:
        return await client.post(path, headers=headers, content=data)


async def echo(scope, receive, send):
    body = await receive()
    data = json.dumps({"path": scope["path"], "authorized": app.AUTHORIZED.get(),
                       "headers": [k.decode() for k, _ in scope["headers"]],
                       "bytes": len(body["body"])}).encode()
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": data})


def test_bearer_and_secret_path_constant_time_delay_no_redirect(monkeypatch):
    token, wrong = secrets.token_hex(32), secrets.token_hex(32)
    sleeps, compared = [], []
    compare = app.hmac.compare_digest
    def comparing(left, right):
        compared.append((len(left), len(right)))
        return compare(left, right)
    async def sleeping(duration):
        sleeps.append(duration)
    monkeypatch.setattr(app.hmac, "compare_digest", comparing)
    monkeypatch.setattr(app.asyncio, "sleep", sleeping)
    async def scenario():
        gate = app.Gate(echo, token.encode())
        for path, header in [("/mcp", token), ("/mcp/", token), (f"/mcp/{token}/", None), (f"/mcp/{token}/", token),
                             (f"/mcp/{token}", None)]:  # a pasted address may lose its final slash
            result = await request(gate, path, header)
            assert result.status_code == 200
            assert result.json()["path"] == "/mcp/" and result.json()["authorized"]
            assert "authorization" not in result.json()["headers"]
        for path, header in [("/mcp", None), ("/mcp/", wrong), (f"/mcp/{wrong}/", None),
                             (f"/mcp/{token}/extra", None), (f"/mcp/{token}//", None), (f"/mcp/{wrong}", None),
                             (f"/mcp/{token}/", wrong), (f"/mcp/{wrong}/", token), ("/", token)]:
            result = await request(gate, path, header)
            assert result.status_code == 404 and "location" not in result.headers
            assert token not in result.text and wrong not in result.text
        assert not app.AUTHORIZED.get()
    asyncio.run(scenario())
    assert sleeps == [.2] * 9
    assert compared and all(pair == (32, 32) for pair in compared)


def test_only_http_reaches_the_application_websocket_is_closed_unauthenticated():
    token = secrets.token_hex(32)
    reached, sent = [], []
    async def inner(scope, receive, send):
        reached.append(scope["type"])
    async def send(message):
        sent.append(message)
    async def scenario():
        gate = app.Gate(inner, token.encode())
        await gate({"type": "websocket", "path": f"/mcp/{token}/", "headers": []}, None, send)
        await gate({"type": "future-scope", "path": "/mcp/"}, None, send)
        assert reached == [] and sent == [{"type": "websocket.close", "code": 1008}]
        await gate({"type": "lifespan"}, None, send)  # the SDK session manager needs it
        assert reached == ["lifespan"]
    asyncio.run(scenario())


def test_rate_request_size_origin_and_streaming_body_caps():
    token = secrets.token_hex(32)
    async def scenario():
        gate = app.Gate(echo, token.encode(), rate=2)
        assert (await request(gate, "/mcp/", token)).status_code == 200
        assert (await request(gate, "/mcp/", token)).status_code == 200
        assert (await request(gate, "/mcp/", token)).status_code == 429
        gate = app.Gate(echo, token.encode())
        assert (await request(gate, "/mcp/", token, b"x" * (app.REQUEST + 1))).status_code == 413
        assert (await request(gate, "/mcp/", token, origin="https://other.example")).status_code == 403
        assert (await request(gate, "/mcp/", token, origin="http://testserver")).status_code == 200
        messages = iter([{"type": "http.request", "body": b"x" * app.REQUEST, "more_body": True},
                         {"type": "http.request", "body": b"x", "more_body": False}])
        received = []
        async def receive():
            return next(messages)
        async def send(message):
            received.append(message)
        await gate({"type": "http", "method": "POST", "path": "/mcp/",
                    "headers": [(b"authorization", b"Bearer " + token.encode())]}, receive, send)
        assert received[0]["status"] == 413
    asyncio.run(scenario())


def test_private_token_file_permissions_symlinks_and_format(tmp_path):
    token = secrets.token_hex(32)
    path = tmp_path / "token"
    path.write_text(token + "\n")
    path.chmod(0o600)
    assert app.load_token(path) == token.encode()
    path.chmod(0o644)
    with pytest.raises(PermissionError):
        app.load_token(path)
    path.chmod(0o600)
    link = tmp_path / "alias"
    link.symlink_to(path)
    with pytest.raises(OSError):
        app.load_token(link)
    path.write_text("invalid")
    with pytest.raises(ValueError):
        app.load_token(path)


def test_credential_comes_from_systemd_or_from_the_runtime_copy_never_from_a_value(tmp_path):
    token = secrets.token_hex(32)
    assert app.credential_path({"CREDENTIALS_DIRECTORY": "/run/credentials/unit",
                                "RUNTIME_DIRECTORY": "/run/star-workbench"}) == Path("/run/credentials/unit/token")
    # No nesting in an unprivileged LXD container: systemd sets no credential directory.
    assert app.credential_path({"RUNTIME_DIRECTORY": "/run/star-workbench"}) == Path("/run/star-workbench/token")
    for environ in ({}, {"RUNTIME_DIRECTORY": token}, {"CREDENTIALS_DIRECTORY": "", "RUNTIME_DIRECTORY": "a:b"}):
        with pytest.raises(SystemExit):
            app.credential_path(environ)
    copy = tmp_path / "token"
    copy.write_text(token + "\n")
    copy.chmod(0o400)  # exactly what the unit's ExecStartPre installs
    assert app.load_token(app.credential_path({"RUNTIME_DIRECTORY": str(tmp_path)})) == token.encode()
    text = (Path(__file__).parents[1] / "server/workbench/install.sh").read_text()
    assert "ExecStartPre=+/usr/bin/install -o star-workbench -g star-workbench -m 400 " in text
    assert "RuntimeDirectoryMode=0700" in text


def test_real_mcp_lists_tools_and_executes_write_run_read(tmp_path):
    pytest.importorskip("mcp", reason="Install project's declared MCP dependency for protocol tests")
    token = secrets.token_hex(32)
    root = tmp_path / "work"
    root.mkdir()
    bench = app.Workbench(root, tmp_path / "state", tmp_path / "audit", tmp_path / "PAUSED", sandbox=False)
    server, gate = app.create_server(bench, token.encode())
    async def scenario():
        async with server.session_manager.run():
            counter = 0
            async def rpc(method, params=None, notification=False, authenticated=True):
                nonlocal counter
                counter += 1
                payload = {"jsonrpc": "2.0", "method": method}
                if not notification:
                    payload["id"] = counter
                if params is not None:
                    payload["params"] = params
                response = await request(gate, f"/mcp/{token}/" if authenticated else "/mcp/",
                                         data=json.dumps(payload).encode())
                if not authenticated:
                    return response
                assert response.status_code in (200, 202), response.text
                return response.json() if response.content else None
            initialized = await rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                                   "clientInfo": {"name": "offline-test", "version": "1"}})
            assert "result" in initialized
            await rpc("notifications/initialized", notification=True)
            listing = await rpc("tools/list")
            assert {t["name"] for t in listing["result"]["tools"]} == set(app.TOOLS)
            hints = {t["name"]: t["annotations"]["readOnlyHint"] for t in listing["result"]["tools"]}
            assert hints["ws_read"] and hints["info"] and hints["job_output"]
            assert not any(hints[name] for name in ("ws_write", "ws_delete", "ws_apply_patch", "run",
                                                    "job_start", "job_stop", "repo_sync",
                                                    "test_python", "test_frontend"))
            async def tool(name, arguments):
                result = (await rpc("tools/call", {"name": name, "arguments": arguments}))["result"]
                assert not result.get("isError"), result
                return result.get("structuredContent") or json.loads(result["content"][0]["text"])
            await tool("ws_write", {"path": "program.py", "content": "print(6 * 7)\n"})
            result = await tool("run", {"argv": [sys.executable, "program.py"]})
            assert result["exit_code"] == 0 and result["output"].strip() == "42"
            assert (await tool("ws_read", {"path": "program.py"}))["text"] == "print(6 * 7)\n"
            assert (await rpc("tools/list", authenticated=False)).status_code == 404
            bench.kill_switch.touch()
            result = await rpc("tools/call", {"name": "ws_write", "arguments": {"path": "refused", "content": "no"}})
            assert result["result"]["isError"]
            assert not (root / "refused").exists()
    try:
        asyncio.run(scenario())
    finally:
        bench.close()
    assert token not in (tmp_path / "audit").read_text()
