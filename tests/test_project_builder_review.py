"""Review regressions drive real builder writes and real Settings CLI loading."""
from contextvars import ContextVar
import hashlib
import json
from pathlib import Path, PureWindowsPath
import socket
import sys
from types import ModuleType, SimpleNamespace

import pytest

from star import desktop_core, project_builder as builder, providers


def module(name="Data", kind="shared", requires=(), interface=None):
    return {"name": name, "kind": kind, "purpose": f"Brief for {name}",
            "requires": list(requires), "interface": ["run"] if interface is None else interface}


def fenced(source):
    return f"```luau\n{source}\n```"


@pytest.fixture(autouse=True)
def no_external_services(monkeypatch):
    # Permit only the stdlib's synchronous wake-up socketpair on Windows.
    internal_pair = ContextVar("builder_review_socketpair", default=False)
    original_connect, original_pair = socket.socket.connect, socket.socketpair

    def blocked(*args, **kwargs):
        raise AssertionError("External services are not allowed in builder review tests")

    def connect(sock, *args, **kwargs):
        if not internal_pair.get():
            return blocked()
        return original_connect(sock, *args, **kwargs)

    def socketpair(*args, **kwargs):
        token = internal_pair.set(True)
        try:
            return original_pair(*args, **kwargs)
        finally:
            internal_pair.reset(token)

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "socketpair", socketpair)
    # Keyring is optional in the core-only CI environment; never require or use it.
    credential_store = ModuleType("keyring")
    for name in ("get_password", "set_password", "get_credential", "delete_password"):
        setattr(credential_store, name, blocked)
    monkeypatch.setitem(sys.modules, "keyring", credential_store)


@pytest.mark.parametrize("flavour", [Path, PureWindowsPath])
def test_nested_native_and_windows_paths_are_accepted(tmp_path, flavour):
    relative = flavour("src", "ReplicatedStorage", "Shared", "Data.lua")
    assert builder._file_under(tmp_path, relative) == tmp_path / "src/ReplicatedStorage/Shared/Data.lua"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("relative", [
    Path("src", "bad:stream.lua"), Path("src", "bad\x00name.lua"),
    PureWindowsPath("..", "escape"), PureWindowsPath("C:escape"),
])
def test_component_guard_still_rejects_unsafe_paths(tmp_path, relative):
    with pytest.raises(ValueError, match="escapes selected folder"):
        builder._file_under(tmp_path, relative)
    assert list(tmp_path.iterdir()) == []


def test_four_module_build_writes_native_tree_imports_and_manifest(tmp_path):
    plan = [module("Worker", "server", ["Data"]), module("View", "client", ["Data"]),
            module("Load"), module("Data", interface=["loadData", "saveData"])]
    responses = {
        "Data": "local M = {}\nfunction M.loadData() return true end\nfunction M.saveData() return true end\nreturn M",
        "Worker": "local M = {}\nfunction M.run() return dependencies.Data.loadData() end\nreturn M",
        "View": "local M = {}\nfunction M.run() return dependencies.Data.saveData() end\nreturn M",
        "Load": "local M = {}\nfunction M.run() return true end\nreturn M",
    }
    calls = []

    def generate(prompt):
        payload = json.JSONDecoder().raw_decode(prompt[prompt.index('{"module":'):])[0]
        name = payload["module"]["name"]
        calls.append(name)
        return fenced(responses[name])

    out = tmp_path / "project"
    manifest = builder.build_project(plan, out, generate)
    assert manifest["status"] == "complete" and not manifest["failed"]
    assert len(manifest["generated"]) == len(calls) == 4
    assert calls.index("Data") < calls.index("Worker")
    assert calls.index("Data") < calls.index("View")
    assert json.loads((out / "manifest.json").read_text(encoding="utf-8")) == manifest
    tree = json.loads((out / "default.project.json").read_text(encoding="utf-8"))["tree"]
    assert tree["$className"] == "DataModel"
    assert tree["ReplicatedStorage"]["$path"] == "src/ReplicatedStorage"
    assert tree["ServerScriptService"]["$path"] == "src/ServerScriptService"
    assert tree["StarterPlayer"]["StarterPlayerScripts"]["$path"] == "src/StarterPlayer/StarterPlayerScripts"
    expected = {
        "Data": Path("src", "ReplicatedStorage", "Shared", "Data.lua"),
        "Load": Path("src", "ReplicatedStorage", "Shared", "Load.lua"),
        "Worker": Path("src", "ServerScriptService", "Server", "Worker.lua"),
        "View": Path("src", "StarterPlayer", "StarterPlayerScripts", "Client", "View.lua"),
    }
    for entry in manifest["generated"]:
        assert entry["attempts"] == 1 and not entry["errors"]
        assert entry["path"] == expected[entry["name"]].as_posix()
        source = (out / expected[entry["name"]]).read_bytes()
        assert hashlib.sha256(source).hexdigest() == entry["sha256"]
        if entry["requires"]:
            assert b'Data = require(game:GetService("ReplicatedStorage"):WaitForChild("Shared"):WaitForChild("Data"))' in source


@pytest.mark.parametrize("name", sorted(builder._FORBIDDEN | builder._FORBIDDEN_SERVICES | {"os", "GetService"}))
@pytest.mark.parametrize("field", ["module", "list", "mapping"])
def test_forbidden_plan_names_fail_before_model_or_cli_configuration(tmp_path, monkeypatch, capsys, name, field):
    item = module()
    if field == "module":
        item["name"] = name
    else:
        item["interface"] = [name] if field == "list" else {name: "A public operation"}
    plan = [item]
    calls = []

    def unexpected(*args, **kwargs):
        calls.append(True)
        raise AssertionError("Invalid plans must not configure or call a provider")

    monkeypatch.setattr(builder, "_configured_generator", unexpected)
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="name conflicts with forbidden API policy"):
        builder.build_project(plan, out, unexpected)
    assert calls == [] and not out.exists()
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    assert builder.main(["--plan", str(plan_path), "--out", str(out)]) == 2
    assert calls == [] and not out.exists()
    captured = capsys.readouterr()
    assert captured.err and not captured.out


@pytest.mark.parametrize("max_calls", [12, 0])
def test_cli_loads_and_validates_real_settings(tmp_path, monkeypatch, capsys, max_calls):
    # Keep Settings.load, Settings.validate and app_data real on both platforms.
    monkeypatch.setenv("APPDATA", str(tmp_path / "profile"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "profile"))
    profile = desktop_core.app_data()
    assert profile.is_relative_to(tmp_path)
    profile.mkdir(parents=True)
    (profile / "settings.json").write_text(json.dumps({
        "model": "builder-test-model", "provider": "local", "studio_target": "local_pc",
        "knowledge_endpoint": "off", "max_calls": max_calls,
    }), encoding="utf-8")
    calls = {"opened": [], "entered": 0, "closed": 0, "requests": []}

    class Client:
        def __init__(self):
            self.chat = self.completions = self

        async def __aenter__(self):
            calls["entered"] += 1
            return self

        async def __aexit__(self, *args):
            calls["closed"] += 1

        async def create(self, **kwargs):
            calls["requests"].append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(
                content=fenced("local M = {}\nfunction M.run() return true end\nreturn M")))])

    def open_client(settings):
        assert isinstance(settings, desktop_core.Settings)
        assert settings.provider == "local" and settings.model == "builder-test-model"
        assert settings.max_calls == max_calls
        calls["opened"].append(settings)
        return Client()

    # Only the provider boundary is replaced, never either imported module.
    monkeypatch.setattr(providers, "open_client", open_client)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps([module()]), encoding="utf-8")
    out = tmp_path / "out"
    result = builder.main(["--plan", str(plan_path), "--out", str(out)])
    captured = capsys.readouterr()
    if max_calls == 0:
        assert result == 2 and captured.err and not captured.out
        assert calls["opened"] == calls["requests"] == []
        assert calls["entered"] == calls["closed"] == 0
        assert not out.exists()
    else:
        assert result == 0 and not captured.err
        manifest = json.loads(captured.out)
        assert manifest["status"] == "complete" and not manifest["failed"]
        assert len(manifest["generated"]) == len(calls["opened"]) == len(calls["requests"]) == 1
        assert calls["entered"] == calls["closed"] == 1
        assert calls["requests"][0]["model"] == "builder-test-model"
        assert calls["requests"][0]["messages"][0]["role"] == "user"
        assert (out / manifest["generated"][0]["path"]).is_file()
        assert json.loads((out / "manifest.json").read_text(encoding="utf-8")) == manifest
