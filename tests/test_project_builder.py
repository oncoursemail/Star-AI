"""Offline tests drive real generation, filesystem writes, repair and CLI paths."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import pytest

from star import project_builder as builder


def module(name="Example", kind="shared", requires=(), interface=None):
    return {"name": name, "kind": kind, "purpose": f"Brief for {name}",
            "interface": ["run"] if interface is None else interface, "requires": list(requires)}


def fenced(source):
    return f"```luau\n{source}\n```"


def good(body="return true"):
    return fenced(f"local M = {{}}\nfunction M.run() {body} end\nreturn M")


def payload(prompt):
    return json.JSONDecoder().raw_decode(prompt[prompt.index('{"module":'):])[0]


class ScriptedModel:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.prompts = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Network access is not allowed in builder tests")
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)


def assert_project(root, manifest):
    assert json.loads((root / "manifest.json").read_text()) == manifest
    project = json.loads((root / "default.project.json").read_text())
    assert project["tree"]["$className"] == "DataModel"
    assert project["tree"]["StarterPlayer"]["StarterPlayerScripts"]["$className"] == "StarterPlayerScripts"

    def inspect(node):
        if "$path" in node:
            assert (root / node["$path"]).is_dir()
        for key, child in node.items():
            if not key.startswith("$") and isinstance(child, dict):
                inspect(child)
    inspect(project["tree"])
    for item in manifest["generated"]:
        assert hashlib.sha256((root / item["path"]).read_bytes()).hexdigest() == item["sha256"]


def test_five_modules_real_files_order_and_interface_only_context(tmp_path):
    plan = {"modules": [module("Final", "server", ["Worker", "Items"]),
                         module("Client", "client", ["Items"]),
                         module("Worker", "server", ["Items"]),
                         module("Items", interface={"run": "() -> boolean: item readiness"}),
                         module("Utilities")]}
    plan["modules"][3]["source"] = "NOT_IN_ANY_PROMPT"
    original = json.dumps(plan)
    prompts = []

    def fake(prompt):
        prompts.append(prompt)
        name = payload(prompt)["module"]["name"]
        body = "return dependencies.Items.run()" if name in {"Worker", "Client"} else "return true"
        return good(body).replace("local M", f"-- IMPLEMENTATION_{name}\nlocal M")

    root = tmp_path / "game"
    manifest = builder.build_project(plan, root, fake)
    assert manifest["status"] == "complete"
    assert len(manifest["generated"]) == len(prompts) == 5
    assert not manifest["failed"]
    assert json.dumps(plan) == original
    order = [payload(p)["module"]["name"] for p in prompts]
    assert manifest["order"] == order
    assert order.index("Items") < order.index("Worker") < order.index("Final")
    assert order.index("Items") < order.index("Client")
    for prompt in prompts:
        data = payload(prompt)
        assert set(data) == {"module", "dependency_interfaces"}
        assert set(data["module"]) == {"name", "kind", "purpose", "interface", "requires"}
        assert {d["name"] for d in data["dependency_interfaces"]} == set(data["module"]["requires"])
        assert all(set(d) == {"name", "kind", "interface"} for d in data["dependency_interfaces"])
        assert "IMPLEMENTATION_" not in prompt and "NOT_IN_ANY_PROMPT" not in prompt
        for other in plan["modules"]:
            if other["name"] != data["module"]["name"]:
                assert other["purpose"] not in prompt
    assert all(g["attempts"] == 1 and not g["errors"] for g in manifest["generated"])
    final = (root / "src/ServerScriptService/Server/Final.lua").read_text()
    assert 'Worker = require(game:GetService("ServerScriptService"):WaitForChild("Server"):WaitForChild("Worker"))' in final
    client = (root / "src/StarterPlayer/StarterPlayerScripts/Client/Client.lua").read_text()
    assert 'Items = require(game:GetService("ReplicatedStorage"):WaitForChild("Shared"):WaitForChild("Items"))' in client
    assert_project(root, manifest)


def test_client_dependency_uses_runtime_clone(tmp_path):
    plan = [module("Hud", "client", ["Input"]), module("Input", "client")]
    manifest = builder.build_project(plan, tmp_path, ScriptedModel([good(), good()]))
    source = (tmp_path / manifest["generated"][1]["path"]).read_text()
    assert 'Input = require(script.Parent:WaitForChild("Input"))' in source
    assert "GetService(\"StarterPlayer\")" not in source


@pytest.mark.parametrize("bad,error", [
    ("", "non-empty fenced"),
    (fenced("local M = {}\nreturn M"), "Missing public interface: run"),
    (good("loadstring('untrusted')"), "Forbidden API"),
    (fenced("local M = {}\nfunction M.run() return true\nreturn M"), "Unbalanced"),
])
def test_repair_once_with_failure_not_previous_source(tmp_path, bad, error):
    fake = ScriptedModel([bad, good()])
    manifest = builder.build_project([module()], tmp_path, fake)
    assert not manifest["failed"]
    assert manifest["generated"][0]["attempts"] == len(fake.prompts) == 2
    assert error in fake.prompts[1]
    assert fake.prompts[1].startswith(fake.prompts[0] + "\nPrevious failure: ")
    assert payload(fake.prompts[0]) == payload(fake.prompts[1])
    assert_project(tmp_path, manifest)


def test_double_failure_blocks_dependents_but_not_independent_modules(tmp_path):
    plan = [module("Next", requires=["Dependent"]), module("Dependent", requires=["Bad"]),
            module("Bad"), module("Independent")]
    prompts = []

    def fake(prompt):
        name = payload(prompt)["module"]["name"]
        prompts.append(name)
        return "not code" if name == "Bad" else good()

    manifest = builder.build_project(plan, tmp_path, fake)
    assert manifest["status"] == "incomplete"
    assert prompts.count("Bad") == 2 and prompts.count("Independent") == 1
    assert len(prompts) == 3
    assert [g["name"] for g in manifest["generated"]] == ["Independent"]
    failed = {f["name"]: f for f in manifest["failed"]}
    assert failed["Bad"]["attempts"] == len(failed["Bad"]["errors"]) == 2
    assert failed["Dependent"]["attempts"] == failed["Next"]["attempts"] == 0
    assert failed["Dependent"]["blocked_by"] == ["Bad"]
    assert failed["Next"]["blocked_by"] == ["Dependent"]
    assert all(not (tmp_path / f["path"]).exists() for f in failed.values())
    assert_project(tmp_path, manifest)


@pytest.mark.parametrize("repair", [True, False])
def test_model_exceptions_do_not_escape_or_leak(tmp_path, repair):
    detail = "opaque provider error that must not be copied"
    fake = ScriptedModel([RuntimeError(detail), good() if repair else RuntimeError(detail)])
    result = builder.build_project([module()], tmp_path, fake)
    assert len(fake.prompts) == 2
    assert bool(result["generated"]) is repair
    assert detail not in "\n".join(fake.prompts) + json.dumps(result)
    assert_project(tmp_path, result)


@pytest.mark.parametrize("name", ["../escape", "/escape", "a/b", "..", "A\\B", "", "C:\\escape", "\\\\host\\folder",
                                  "name:stream", "a\x00b", "init", "INIT", "CON", "lpt1", "NUL", "Thing.lua", "return"])
def test_path_guard_rejects_unsafe_or_reserved_module_names(tmp_path, name):
    fake = ScriptedModel([])
    with pytest.raises(ValueError):
        builder.build_project([module(name)], tmp_path / "out", fake)
    assert not fake.prompts and not (tmp_path / "out").exists()


@pytest.mark.parametrize("relative", ["../escape", "/escape", "C:\\escape", "C:escape", "\\\\host\\folder", "a\\..\\b", "name:stream", "."])
def test_relative_path_guard(tmp_path, relative):
    with pytest.raises(ValueError):
        builder._file_under(tmp_path, Path(relative))


def test_parent_traversal_in_output_rejected_before_model(tmp_path):
    fake = ScriptedModel([])
    with pytest.raises(ValueError, match="traversal"):
        builder.build_project([module()], tmp_path / "one/../out", fake)
    assert not fake.prompts and list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("existing", ["manifest.json", "default.project.json", "src/ReplicatedStorage/Shared/Example.lua", "unrelated.txt"])
def test_existing_files_not_overwritten(tmp_path, existing):
    root = tmp_path / "out"
    target = root / existing
    target.parent.mkdir(parents=True)
    target.write_text("sentinel")
    fake = ScriptedModel([])
    with pytest.raises(FileExistsError):
        builder.build_project([module()], root, fake)
    assert not fake.prompts and target.read_text() == "sentinel"


def symlink(link, target, directory=True):
    try:
        link.symlink_to(target, target_is_directory=directory)
    except (OSError, NotImplementedError):
        pytest.skip("Host does not permit symlinks")


@pytest.mark.parametrize("relative", [".", "src", "src/ReplicatedStorage", "manifest.json", "default.project.json"])
@pytest.mark.parametrize("broken", [False, True])
def test_symlink_paths_rejected_before_model(tmp_path, relative, broken):
    root, outside = tmp_path / "out", tmp_path / "outside"
    if not broken:
        outside.mkdir()
    link = root if relative == "." else root / relative
    link.parent.mkdir(parents=True, exist_ok=True)
    symlink(link, outside)
    fake = ScriptedModel([])
    with pytest.raises(ValueError, match="symlinks"):
        builder.build_project([module()], root, fake)
    assert not fake.prompts
    assert not outside.exists() if broken else list(outside.iterdir()) == []


@pytest.mark.parametrize("hardlink", [False, True])
def test_link_inserted_during_generation_cannot_overwrite_outside(tmp_path, hardlink):
    root, outside = tmp_path / "out", tmp_path / "sentinel.txt"
    outside.write_text("unchanged")

    def fake(prompt):
        target = root / "src/ReplicatedStorage/Shared/Example.lua"
        if hardlink:
            os.link(outside, target)
        else:
            symlink(target, outside, directory=False)
        return good()

    with pytest.raises((ValueError, FileExistsError)):
        builder.build_project([module()], root, fake)
    assert outside.read_text() == "unchanged"


def test_root_redirected_during_generation_rejected(tmp_path):
    root, outside = tmp_path / "out", tmp_path / "outside"
    outside.mkdir()

    def fake(prompt):
        root.rename(tmp_path / "moved")
        symlink(root, outside)
        return good()

    with pytest.raises(ValueError, match="symlinks"):
        builder.build_project([module()], root, fake)
    assert list(outside.iterdir()) == []


def test_windows_reparse_point_guard_is_executed(tmp_path, monkeypatch):
    root = tmp_path / "out"
    root.mkdir()
    original = Path.lstat
    monkeypatch.setattr(builder.stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024, raising=False)

    def lstat(path, *args, **kwargs):
        value = original(path, *args, **kwargs)
        if path == root:
            return SimpleNamespace(st_mode=value.st_mode, st_file_attributes=1024)
        return value

    monkeypatch.setattr(Path, "lstat", lstat)
    with pytest.raises(ValueError, match="reparse"):
        builder.build_project([module()], root, ScriptedModel([]))


@pytest.mark.parametrize("plan", [
    [], {}, {"modules": "bad"}, [None], [module(), module()], [module("A"), module("a")],
    [module(interface=[])], [module(interface=["run", "run"])], [module(interface=[{}])],
    [module(interface={"run": ""})], [dict(module(), kind=[])], [dict(module(), purpose=" ")],
    [dict(module(), requires="Other")], [dict(module(), requires=[{}])],
    [module(requires=["Missing"])], [module(requires=["Example"])],
    [module("A", requires=["B", "B"]), module("B")],
    [module("A", requires=["B"]), module("B", requires=["A"])],
    [module("A", "shared", ["B"]), module("B", "server")],
    [module("A", "client", ["B"]), module("B", "server")],
    [module("A", "server", ["B"]), module("B", "client")],
])
def test_invalid_plans_fail_before_files_or_calls(tmp_path, plan):
    fake = ScriptedModel([])
    with pytest.raises(ValueError):
        builder.build_project(plan, tmp_path / "out", fake)
    assert not fake.prompts and not (tmp_path / "out").exists()


def test_dependency_order_is_stable_and_not_recursion_limited():
    plan = [module(f"M{i}", requires=[f"M{i-1}"] if i else []) for i in reversed(range(1500))]
    assert [m["name"] for m in builder.ordered_modules(plan)] == [f"M{i}" for i in range(1500)]


@pytest.mark.parametrize("source", [
    'local M = {}\nlocal text = "function M.run() return M"\nreturn M',
    'local M = {}\nlocal text = [=[function M.run() return M]=]\nreturn M',
    'local M = {}\n-- function M.run() end\nreturn M',
    'local M = {}\n--[=[function M.run() end]=]\nreturn M',
    'local M = {}\nlocal Other = {}\nfunction Other.run() end\nreturn M',
    'local M = {}\nlocal function hidden() function M.run() end end\nreturn M',
    'local M = {}\nif false then function M.run() end end\nreturn M',
    'local M = {}\nfunction M.run() return true end',
    'local M = {}\nfunction M.run() end\nreturn Other',
    'local M = {}\nfunction M.run() end\nreturn M.run',
    'local M = {}\nfunction M.run() end\nM = {}\nreturn M',
    'local M = {}\nfunction M.run() end\nM.run = nil\nreturn M',
    'local M = {}\nfunction M.run() end\nlocal M = {}\nreturn M',
    'local M = {}\nfunction M.run() end\nreturn M\nprint("after return")',
])
def test_static_check_rejects_nonexported_or_replaced_interface(source):
    code, error = builder.validate_code(fenced(source), ["run"])
    assert code is None and error


@pytest.mark.parametrize("source", [
    'local M = {}\nfunction M:run() return true end\nreturn M',
    'local M = {}\nM.run = function() return true end\nreturn M;',
    'local Other = {}\nfunction Other.run() if true then return true else return false end end\nreturn Other',
    'local M = {}\nfunction M.run() for i = 1, 2 do print(i) end return true end\nreturn M',
    'local M = {}\nfunction M.run() local i = 0 repeat i += 1 until i == 1 return i end\nreturn M',
    'local M = {}\n--[==[ require(1) ]=] still comment ]==]\nfunction M.run() return "loadstring() --" end\nreturn M',
])
def test_static_check_accepts_documented_forms_without_rewriting(source):
    code, error = builder.validate_code(fenced(source), {"run": "A public operation"})
    assert error is None
    assert code == source + "\n"


@pytest.mark.parametrize("body", [
    "loadstring('text')", "local evaluate = loadstring", "getfenv()", "setfenv(1, {})",
    "require(123)", "require(-123)", "require('asset')", "require(script.Parent.Other)",
    'game:HttpGet("example")', 'game["HttpGet"](game, "example")',
    'game:GetService("HttpService")', "game:GetService('DataStoreService')",
    'game:GetService([=[MessagingService]=])', 'game:GetService("TeleportService")',
    'game:GetService("InsertService")', 'game:GetService("Http" .. "Service")',
    'game:GetService("\\072ttpService")', 'game["GetService"](game, "HttpService")',
    'game["\\072ttpGet"](game, "example")', 'local s = "--"; loadstring("text")',
    'writefile("file", "contents")', 'request({})', 'os.execute("command")', 'local system = os',
    'local value = `value {loadstring("text")}`', 'local dependencies = {}', 'dependencies = {}',
])
def test_forbidden_and_dynamic_apis_fail_real_build_after_two_attempts(tmp_path, body):
    fake = ScriptedModel([good(body), good(body)])
    result = builder.build_project([module()], tmp_path, fake)
    assert len(fake.prompts) == result["failed"][0]["attempts"] == 2
    assert not result["generated"]
    assert not (tmp_path / result["failed"][0]["path"]).exists()
    assert_project(tmp_path, result)


@pytest.mark.parametrize("response", [None, {}, "no fence", fenced("   "), fenced("-- comment only"),
    good() + "\n" + good(), "```python\nprint('wrong language')\n```", "preface\n" + good(),
    fenced('local M = {}\nlocal s = "unfinished'), fenced("--[=[unfinished"),
    fenced("local M = {]\nreturn M"), fenced("local M = {}\nend\nreturn M")])
def test_malformed_responses_are_validation_failures(response):
    assert builder.validate_code(response, ["run"])[1]


def test_crlf_fence_is_accepted():
    assert builder.validate_code(good().replace("\n", "\r\n"), ["run"])[1] is None


def install_fake_provider(monkeypatch, tmp_path, responses, *, provider="local", model="configured-model", finish_reason="stop"):
    calls = {"loaded": [], "validated": 0, "opened": [], "closed": 0, "requests": []}
    responses = iter(responses)

    class Settings:
        @classmethod
        def load(cls, path):
            calls["loaded"].append(path)
            return settings

        def validate(self):
            calls["validated"] += 1

    settings = Settings()
    settings.model, settings.provider = model, provider

    class Client:
        def __init__(self):
            self.chat = self.completions = self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            calls["closed"] += 1

        async def create(self, **kwargs):
            calls["requests"].append(kwargs)
            response = next(responses)
            if isinstance(response, Exception):
                raise response
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish_reason,
                message=SimpleNamespace(content=response))])

    def open_client(selected):
        assert selected is settings
        calls["opened"].append(selected.provider)
        return Client()

    desktop, providers = ModuleType("star.desktop_core"), ModuleType("star.providers")
    desktop.Settings, desktop.app_data = Settings, lambda: tmp_path / "settings-home"
    providers.open_client = open_client
    monkeypatch.setitem(sys.modules, "star.desktop_core", desktop)
    monkeypatch.setitem(sys.modules, "star.providers", providers)
    return calls


def write_plan(tmp_path, plan=None):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps([module()] if plan is None else plan), encoding="utf-8-sig")
    return path


@pytest.mark.parametrize("provider", ["local", "star_server", "groq"])
def test_cli_uses_configured_provider_real_generation_and_closes_clients(tmp_path, monkeypatch, capsys, provider):
    calls = install_fake_provider(monkeypatch, tmp_path, [good(), good()], provider=provider)
    plan = write_plan(tmp_path, [module("Base"), module("Consumer", requires=["Base"])])
    out = tmp_path / "project"
    assert builder.main(["--plan", str(plan), "--out", str(out)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert_project(out, result)
    assert calls["loaded"] == [tmp_path / "settings-home/settings.json"]
    assert calls["validated"] == 1
    assert calls["opened"] == [provider, provider] and calls["closed"] == 2
    assert len(calls["requests"]) == 2
    for request in calls["requests"]:
        assert set(request) == {"model", "messages"}
        assert request["model"] == "configured-model"
        assert len(request["messages"]) == 1 and request["messages"][0]["role"] == "user"


@pytest.mark.parametrize("reason", ["length", "content_filter", "tool_calls", None])
def test_cli_does_not_accept_truncated_or_filtered_code(tmp_path, monkeypatch, capsys, reason):
    calls = install_fake_provider(monkeypatch, tmp_path, [good(), good()], finish_reason=reason)
    plan = write_plan(tmp_path)
    assert builder.main(["--plan", str(plan), "--out", str(tmp_path / "out")]) == 1
    result = json.loads(capsys.readouterr().out)
    assert not result["generated"] and result["failed"][0]["attempts"] == 2
    assert calls["closed"] == 2


def test_cli_closes_provider_on_request_exception_and_repairs(tmp_path, monkeypatch, capsys):
    calls = install_fake_provider(monkeypatch, tmp_path, [RuntimeError("opaque failure"), good()])
    plan = write_plan(tmp_path)
    assert builder.main(["--plan", str(plan), "--out", str(tmp_path / "out")]) == 0
    assert calls["closed"] == 2
    assert "opaque failure" not in capsys.readouterr().out


def test_cli_empty_model_does_not_call_provider_or_create_output(tmp_path, monkeypatch, capsys):
    calls = install_fake_provider(monkeypatch, tmp_path, [], model="")
    plan = write_plan(tmp_path)
    assert builder.main(["--plan", str(plan), "--out", str(tmp_path / "out")]) == 2
    assert not calls["opened"] and not (tmp_path / "out").exists()
    assert capsys.readouterr().err


@pytest.mark.parametrize("failure", ["json", "plan", "output"])
def test_cli_preflight_precedes_provider_configuration(tmp_path, monkeypatch, capsys, failure):
    def unexpected():
        raise AssertionError("Provider must not be configured for invalid inputs")
    monkeypatch.setattr(builder, "_configured_generator", unexpected)
    plan = write_plan(tmp_path, [] if failure == "plan" else None)
    out = tmp_path / "out"
    if failure == "json":
        plan.write_text("{")
    if failure == "output":
        out.mkdir()
        (out / "sentinel.txt").write_text("untouched")
    assert builder.main(["--plan", str(plan), "--out", str(out)]) == 2
    assert capsys.readouterr().err
    assert (out / "sentinel.txt").read_text() == "untouched" if failure == "output" else not out.exists()


def test_module_entrypoint_help_does_not_initialize_a_provider():
    completed = subprocess.run([sys.executable, "-m", "star.project_builder", "--help"],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=15)
    assert completed.returncode == 0
    assert "--plan" in completed.stdout and "--out" in completed.stdout


def test_multiple_public_functions_and_allowed_roblox_apis(tmp_path):
    source = ('local RunService = game:GetService("RunService")\n'
              'local M = {}\nfunction M.run() return RunService:IsRunning() end\n'
              'M.elapsed = function() return os.clock() end\nreturn M')
    result = builder.build_project([module(interface={"run": "() -> boolean", "elapsed": "() -> number"})],
                                   tmp_path, ScriptedModel([fenced(source)]))
    assert not result["failed"]
    assert_project(tmp_path, result)


def test_missing_second_public_function_is_not_a_pass(tmp_path):
    fake = ScriptedModel([good(), good()])
    result = builder.build_project([module(interface=["run", "elapsed"])], tmp_path, fake)
    assert result["failed"][0]["error"] == "Missing public interface: elapsed"
    assert not result["generated"]
