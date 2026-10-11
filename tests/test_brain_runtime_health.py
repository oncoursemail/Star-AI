"""Real-completion readiness must be transactional and recover after failures."""
from __future__ import annotations
import asyncio
from types import SimpleNamespace

import httpx
import pytest

from star.brain_runtime_health import start_verified_brain
from star.desktop_core import Settings


class FakeRuntime:
    def __init__(self, *, running=False, router=False):
        self.running, self.router = running, router
        self.started = self.stopped = 0
    def status(self):
        return "running" if self.running else "not started"
    def router_running(self):
        return self.router
    def start(self, *_a, **_kw):
        self.started += 1
        self.running = True
    def stop(self):
        self.stopped += 1
        self.running = False


def installed():
    return SimpleNamespace(executable="C:/fake/llama-server.exe",
                           model="C:/fake/qwen.gguf", projector="C:/fake/mmproj.gguf")


async def valid_probe(settings):
    assert settings.provider == "local"
    assert settings.model == "qwen-test"
    return {"ok":True, "sample":"STAR is ready.", "model":"qwen-test"}


def test_verified_start_persists_only_after_real_chat(tmp_path):
    settings_file=tmp_path/"settings.json"
    original=Settings(provider="groq", model="openai/gpt-oss-20b")
    original.save(settings_file)
    runtime=FakeRuntime()
    queries=[]
    def query(_):
        queries.append(True)
        return [] if len(queries) == 1 else ["qwen-test"]
    result=start_verified_brain(runtime,installed(),settings_file,tmp_path,
        model_query=query,chat_probe=valid_probe,sleep=lambda _:None,max_attempts=3)
    assert len(queries)==2 and runtime.started==1 and runtime.stopped==0
    assert result["chat_ready"] and result["sample"]=="STAR is ready."
    new=Settings.load(settings_file)
    assert new.provider=="local" and new.model=="qwen-test"
    assert original.provider=="groq" # caller's previous Settings not mutated


def test_invalid_chat_rolls_back_settings_and_stops_new_engine(tmp_path):
    settings_file=tmp_path/"settings.json"
    Settings(provider="groq", model="openai/gpt-oss-20b").save(settings_file)
    before=settings_file.read_bytes()
    runtime=FakeRuntime()
    async def failing(_):
        raise RuntimeError("Error code: 500. System message must be at the beginning")
    with pytest.raises(RuntimeError,match="chat test"):
        start_verified_brain(runtime,installed(),settings_file,tmp_path,
            model_query=lambda _:["qwen-test"],chat_probe=failing,sleep=lambda _:None,
            max_attempts=2)
    assert settings_file.read_bytes()==before
    assert runtime.started==runtime.stopped==1


def test_existing_engine_remains_owned_by_user_on_probe_failure(tmp_path):
    runtime=FakeRuntime(running=True)
    async def bad(_):return {"ok":False,"sample":""}
    with pytest.raises(RuntimeError,match="no visible answer"):
        start_verified_brain(runtime,installed(),tmp_path/"settings.json",tmp_path,
            model_query=lambda _:["qwen-test"],chat_probe=bad,max_attempts=1)
    assert runtime.started==0 and runtime.stopped==0 and runtime.running


def test_transient_http_errors_are_bounded_and_rolled_back(tmp_path):
    runtime=FakeRuntime()
    calls=[]
    def down(_):
        calls.append(1)
        raise httpx.ConnectError("not ready")
    with pytest.raises(TimeoutError,match="did not become ready"):
        start_verified_brain(runtime,installed(),tmp_path/"settings.json",tmp_path,
            model_query=down, chat_probe=valid_probe,sleep=lambda _:None,max_attempts=3)
    assert len(calls)==3 and runtime.stopped==1


def test_router_cannot_be_overridden_and_no_process_started(tmp_path):
    runtime=FakeRuntime(router=True)
    with pytest.raises(RuntimeError,match="router"):
        start_verified_brain(runtime,installed(),tmp_path/"settings.json",tmp_path,
            model_query=lambda _:["model"],chat_probe=valid_probe,max_attempts=1)
    assert runtime.started==0


def test_unsupported_probe_payload_is_not_silently_accepted(tmp_path):
    runtime=FakeRuntime()
    async def no_answer(_):return {"ok":True, "sample":""}
    with pytest.raises(RuntimeError,match="no visible answer"):
        start_verified_brain(runtime,installed(),tmp_path/"settings.json",tmp_path,
            model_query=lambda _:["qwen-test"],chat_probe=no_answer,max_attempts=1)
    assert runtime.stopped==1
