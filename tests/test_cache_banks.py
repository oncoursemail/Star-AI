"""No-network, opt-in KV snapshot tests. No model server, secrets or GPU required."""
from __future__ import annotations

import asyncio
import json
import threading
from types import SimpleNamespace

import httpx
import pytest

from star import cache_banks as banks
import star.warmup as warmup
from star.desktop_core import Settings

SERVER = "http://192.168.40.12:8080/v1"
KEY = "test-key-not-a-real-key"
SCOPE = "STAR::chat::c001"


@pytest.fixture
def setup(monkeypatch, tmp_path):
    monkeypatch.setenv(banks.ENV_ENABLE, "on")
    monkeypatch.setenv(banks.ENV_REVISION, "qwen-test-sha256-11223344")
    monkeypatch.setattr(banks, "server_slots", lambda *_: 2)
    monkeypatch.setattr(banks, "connection_for", lambda _: (SERVER, KEY))
    settings = Settings(provider="star_server", model="star-fast",
                        server_endpoint=SERVER, project="STAR")
    request = {
        "model": "star-fast",
        "messages": [{"role": "system", "content": "Stable trusted rules\nProject: private notes"},
                     {"role": "user", "content": "latest changing question"}],
        "tools": [{"type": "function", "function": {"name": "tool_one"}}],
        "extras": {"id_slot": 1, "cache_prompt": True,
                   "chat_template_kwargs": {"preserve_thinking": True}},
    }
    return SimpleNamespace(settings=settings, request=request, home=tmp_path)


def mock_server(seen, *, busy=False, status=200, bad_reply=None):
    def handler(request):
        seen.append((request.method, request.url.path, dict(request.url.params),
                     dict(request.headers), request.content))
        if request.method == "GET" and request.url.path == "/slots":
            return httpx.Response(200, json=[
                {"id": 0, "is_processing": False},
                {"id": 1, "is_processing": bool(busy)},
            ])
        if request.method == "POST" and request.url.path == "/slots/1":
            action = request.url.params["action"]
            response = {"id_slot": 1, "filename": json.loads(request.content)["filename"],
                        ("n_saved" if action == "save" else "n_restored"): 2500,
                        ("n_written" if action == "save" else "n_read"): 9_000_000}
            return httpx.Response(status, json=bad_reply if bad_reply is not None else response)
        raise AssertionError("Unexpected server call")
    return httpx.MockTransport(handler)


def test_off_until_two_separate_opt_ins_are_present(setup, monkeypatch):
    assert banks.plan(setup.settings, setup.request, scope=SCOPE) is not None
    monkeypatch.delenv(banks.ENV_ENABLE)
    assert banks.plan(setup.settings, setup.request, scope=SCOPE) is None
    monkeypatch.setenv(banks.ENV_ENABLE, "yes")
    assert banks.plan(setup.settings, setup.request, scope=SCOPE) is None
    monkeypatch.setenv(banks.ENV_ENABLE, "on")
    monkeypatch.delenv(banks.ENV_REVISION)
    assert banks.plan(setup.settings, setup.request, scope=SCOPE) is None
    monkeypatch.setenv(banks.ENV_REVISION, "???")
    assert banks.plan(setup.settings, setup.request, scope=SCOPE) is None


def test_cannot_touch_cloud_unpinned_slots_or_disabled_cache(setup, monkeypatch):
    monkeypatch.setattr(banks, "provider_kind", lambda _: "cloud")
    assert banks.plan(setup.settings, setup.request, scope=SCOPE) is None
    monkeypatch.setattr(banks, "provider_kind", lambda _: "lan")
    for slot in (-1, 2, None, True, "1"):
        candidate = {**setup.request, "extras": {**setup.request["extras"], "id_slot": slot}}
        assert banks.plan(setup.settings, candidate, scope=SCOPE) is None
    monkeypatch.setattr(banks, "server_slots", lambda *_: 1)
    assert banks.plan(setup.settings, setup.request, scope=SCOPE) is None
    monkeypatch.setattr(banks, "server_slots", lambda *_: 2)
    request = {**setup.request, "extras": {**setup.request["extras"], "cache_prompt": False}}
    assert banks.plan(setup.settings, request, scope=SCOPE) is None


def test_chat_model_tools_and_system_are_all_isolated(setup):
    original = banks.plan(setup.settings, setup.request, scope=SCOPE)
    other_chat = banks.plan(setup.settings, setup.request, scope="STAR::chat::another")
    assert original.filename != other_chat.filename
    updated = {**setup.request, "messages": [{"role": "system", "content": "New reviewed rules"},
                                            setup.request["messages"][1]]}
    other_system = banks.plan(setup.settings, updated, scope=SCOPE)
    assert other_system.filename == original.filename
    assert other_system.fingerprint != original.fingerprint
    changed_tools = {**setup.request, "tools": [{"type": "function", "function": {"name": "other"}}]}
    assert banks.plan(setup.settings, changed_tools, scope=SCOPE).fingerprint != original.fingerprint
    changed_history = {**setup.request, "messages": [setup.request["messages"][0],
                                                     {"role": "user", "content": "new question"}]}
    assert banks.plan(setup.settings, changed_history, scope=SCOPE).fingerprint == original.fingerprint
    renamed = {**setup.request, "model": "different-model"}
    assert banks.plan(setup.settings, renamed, scope=SCOPE).filename != original.filename


def test_save_verified_snapshot_restore_matching_bank_only(setup):
    plan = banks.plan(setup.settings, setup.request, scope=SCOPE)
    seen = []
    t = mock_server(seen)
    assert asyncio.run(banks.restore(setup.settings, setup.home, plan, transport=t, now=100)) == {
        "performed": False, "reason": "not_cached"
    }
    saved = asyncio.run(banks.save(setup.settings, setup.home, plan, transport=t, now=100))
    assert saved == {"performed": True, "tokens": 2500, "bytes": 9_000_000}
    assert [(m, p) for m, p, *_ in seen] == [("GET", "/slots"), ("POST", "/slots/1")]
    assert seen[0][2]["model"] == "star-fast" and seen[1][2]["action"] == "save"
    assert seen[1][2]["model"] == "star-fast"
    assert seen[1][3]["authorization"] == "Bearer " + KEY
    assert json.loads(seen[1][4])["filename"] == plan.filename
    index = (setup.home / "cache-banks" / "index.json").read_text()
    assert "Project: private notes" not in index and KEY not in index
    assert asyncio.run(banks.restore(setup.settings, setup.home, plan, transport=t, now=101)) == {
        "performed": True, "tokens": 2500, "bytes": 9_000_000
    }
    changed = banks.plan(setup.settings, {
        **setup.request, "messages": [{"role": "system", "content": "new policy"}]
    }, scope=SCOPE)
    assert asyncio.run(banks.restore(setup.settings, setup.home, changed, transport=t, now=101))[
        "reason"] == "not_cached"
    assert asyncio.run(banks.restore(setup.settings, setup.home, plan, transport=t,
                                     now=101 + banks.MAX_BANK_AGE_SECONDS))["reason"] == "not_cached"


def test_busy_slot_redirect_and_wrong_receipt_fail_closed(setup):
    plan = banks.plan(setup.settings, setup.request, scope=SCOPE)
    seen = []
    assert asyncio.run(banks.save(setup.settings, setup.home, plan,
                                  transport=mock_server(seen, busy=True), now=1))["reason"] == "slot_busy_or_unknown"
    assert [method for method, *_ in seen] == ["GET"]
    assert not (setup.home / "cache-banks").exists()
    seen.clear()
    bad = {"id_slot": 0, "filename": plan.filename, "n_saved": 100, "n_written": 1024}
    assert asyncio.run(banks.save(setup.settings, setup.home, plan,
                                  transport=mock_server(seen, bad_reply=bad), now=1))["reason"] == "invalid_receipt"
    assert not (setup.home / "cache-banks").exists()
    seen.clear()
    assert asyncio.run(banks.save(setup.settings, setup.home, plan,
                                  transport=mock_server(seen, status=302), now=1))["reason"] == "unsupported_or_missing"
    assert not (setup.home / "cache-banks").exists()


def test_cancellation_before_restore_and_before_save(setup):
    plan = banks.plan(setup.settings, setup.request, scope=SCOPE)
    cancelled = threading.Event()
    cancelled.set()
    seen = []
    result = asyncio.run(banks.save(setup.settings, setup.home, plan,
                                    transport=mock_server(seen),
                                    cancel_event=cancelled))
    assert result["reason"] == "cancelled"
    assert seen == []


def test_index_invalid_or_symlinked_never_restores(setup):
    plan = banks.plan(setup.settings, setup.request, scope=SCOPE)
    folder = setup.home / "cache-banks"
    folder.mkdir()
    (folder / "index.json").write_text("{not json")
    assert asyncio.run(banks.restore(setup.settings, setup.home, plan))["reason"] == "not_cached"
    (folder / "index.json").unlink()
    try:
        (folder / "index.json").symlink_to(setup.home / "private")
    except (OSError, NotImplementedError):
        pass
    else:
        assert asyncio.run(banks.restore(setup.settings, setup.home, plan))["reason"] == "not_cached"


def test_warmup_save_is_only_after_real_success(setup, monkeypatch):
    monkeypatch.setattr(warmup, "prefix_requests", lambda *_: [setup.request])
    monkeypatch.setattr(warmup, "probe_server", lambda *a, **kw: {"ok": True, "code": "ok"})
    calls = []
    async def fake_restore(*a, **kw):
        calls.append("restore")
        return {"performed": False, "reason": "not_cached"}
    async def fake_prime(*a):
        calls.append("prime")
        return {"primed": True}
    async def fake_save(*a, **kw):
        calls.append("save")
        return {"performed": True}
    monkeypatch.setattr(banks, "restore", fake_restore)
    monkeypatch.setattr(banks, "save", fake_save)
    monkeypatch.setattr(warmup, "_prime", fake_prime)
    report = warmup.warm_up(setup.settings, home=setup.home, chat_id="c001")
    assert calls == ["restore", "prime", "save"]
    assert report["cache_bank"]["saved"] is True and report["cache_bank"]["restored"] is False
    calls.clear()
    async def failed_prime(*a):
        calls.append("prime")
        return {"primed": False}
    monkeypatch.setattr(warmup, "_prime", failed_prime)
    report = warmup.warm_up(setup.settings, home=setup.home, chat_id="c001")
    assert calls == ["restore", "prime"] and not report["primed"]
