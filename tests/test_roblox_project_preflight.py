"""CLI-level regressions for the read-only Roblox project source preflight."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from star.roblox_project_preflight import MAX_CHECK_SOURCE_BYTES, main, preflight

DUMP = Path(__file__).parent / "fixtures" / "roblox_api_small.json"


def _project(tmp_path: Path) -> Path:
    source = tmp_path / "game"
    server = source / "ServerScriptService"
    client = source / "StarterPlayer" / "StarterPlayerScripts"
    for directory in (server, client):
        directory.mkdir(parents=True)
    (server / "Main.server.luau").write_text(
        'local part = Instance.new("Part")\npart.Anchored = true\n', encoding="utf-8")
    (client / "Hud.client.lua").write_text("print('ready')\n", encoding="utf-8")
    return source


def _files(report):
    return {f["file"]: f for f in report["files"]}


def test_cli_entrypoint_checks_valid_project_and_preserves_script_metadata(tmp_path, capsys):
    source = _project(tmp_path)
    assert main([str(source), "--api-dump", str(DUMP)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "checked" and report["coverage"] == "static-only"
    assert report["findings"] == 0
    files = _files(report)
    assert len(files) == 2
    assert files["ServerScriptService/Main.server.luau"]["script_class"] == "Script"
    assert "inline-server-remote-trust" in files[
        "ServerScriptService/Main.server.luau"]["checked_scope"]
    assert files["StarterPlayer/StarterPlayerScripts/Hud.client.lua"]["script_class"] == "LocalScript"
    assert "inline-server-remote-trust" not in files[
        "StarterPlayer/StarterPlayerScripts/Hud.client.lua"]["checked_scope"]
    assert "Roblox Studio" in " ".join(report["limitations"])


def test_injected_api_typo_server_trust_and_busy_loop_are_located(tmp_path, capsys):
    root = _project(tmp_path)
    (root / "ServerScriptService/Main.server.luau").write_text(
        'local part = Instance.new("Part")\n'
        'part:Destry()\n'
        'remote.OnServerEvent:Connect(function(player, amount)\n'
        '    coins.Value += amount\n'
        'end)\n'
        'while true do busyWork() end\n',
        encoding="utf-8")
    assert main([str(root), "--api-dump", str(DUMP)]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "findings"
    hit = _files(report)["ServerScriptService/Main.server.luau"]["findings"]
    positions = {(f["rule"], f["line"]) for f in hit}
    assert ("api:unknown-member", 2) in positions
    assert any(rule == "SEC-CLIENT-AMOUNT" and line >= 3 for rule, line in positions)
    assert ("loop-without-yield", 6) in positions
    assert all(f["checker"] and f["severity"] and f["message"] for f in hit)
    assert report["findings"] >= 3


def test_missing_dump_cannot_claim_complete_coverage(tmp_path, capsys):
    root = _project(tmp_path)
    assert main([str(root)]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "partial"
    assert report["coverage"] == "partial"
    assert all("api-names-where-type-is-inferred" not in f["checked_scope"]
               for f in report["files"])
    assert any("API names unchecked" in x for f in report["files"] for x in f["unverified"])


def test_script_over_budget_reports_unchecked_file(tmp_path):
    root = _project(tmp_path)
    long = root / "ServerScriptService/Main.server.luau"
    long.write_text("-- " + "x" * (MAX_CHECK_SOURCE_BYTES + 2), encoding="utf-8")
    result = preflight(root, api_dump=DUMP)
    assert result["status"] == "partial"
    file = _files(result)["ServerScriptService/Main.server.luau"]
    assert file["status"] == "partial"
    assert file["checked_scope"] == []
    assert "budget" in file["unverified"][0]


def test_unscanned_assets_and_outside_service_code_are_explicitly_unsupported(tmp_path):
    root = _project(tmp_path)
    (root / "README.md").write_text("not Roblox code", encoding="utf-8")
    (root / "Custom").mkdir()
    (root / "Custom/Extra.server.luau").write_text("return 1", encoding="utf-8")
    result = preflight(root, api_dump=DUMP)
    assert result["status"] == "unsupported"
    assert result["unsupported_files"] == ["Custom/Extra.server.luau", "README.md"]
    assert len(result["files"]) == 2


@pytest.mark.parametrize("malformed", [
    "not JSON", "{}", "[]", '{"Classes": []}',
    '{"Classes":[{"Name":"Part","Superclass":"Unknown","Members":[]}]}',
])
def test_malformed_api_dump_fails_closed(tmp_path, malformed, capsys):
    root = _project(tmp_path)
    dump = tmp_path / "bad.json"
    dump.write_text(malformed, encoding="utf-8")
    assert main([str(root), "--api-dump", str(dump)]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "invalid"
    assert report["files"] == [] and report["coverage"] == "none"
    assert "dump" in report["error"].lower()


def test_invalid_project_structure_and_missing_input_are_not_passes(tmp_path, capsys):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert main([str(empty), "--api-dump", str(DUMP)]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "invalid"
    assert main([str(tmp_path / "missing"), "--api-dump", str(DUMP)]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "invalid"


def test_init_module_source_is_matched_by_existing_place_tree(tmp_path):
    root = _project(tmp_path)
    folder = root / "ServerScriptService/Shop"
    folder.mkdir()
    (folder / "init.luau").write_text('local p = Instance.new("Prat")\nreturn {}',
                                   encoding="utf-8")
    result = preflight(root, api_dump=DUMP)
    hit = _files(result)["ServerScriptService/Shop/init.luau"]
    assert hit["script_class"] == "ModuleScript"
    assert hit["status"] == "partial"
    assert hit["findings"][0]["line"] == 1
    assert hit["findings"][0]["rule"] == "api:unknown-class"


def test_source_preflight_does_not_write_or_run_code_or_call_network(tmp_path, monkeypatch):
    root = _project(tmp_path)
    before = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in root.rglob("*") if p.is_file()}

    def forbidden(*args, **kwargs):
        raise AssertionError("preflight attempted side effects")

    monkeypatch.setattr(Path, "write_text", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    monkeypatch.setattr("subprocess.run", forbidden)
    monkeypatch.setattr("socket.create_connection", forbidden)
    report = preflight(root, api_dump=DUMP)
    assert report["status"] == "checked"
    after = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in root.rglob("*") if p.is_file()}
    assert before == after


def test_identical_source_has_deterministic_json_report(tmp_path, capsys):
    root = _project(tmp_path)
    assert main([str(root), "--api-dump", str(DUMP)]) == 0
    first = capsys.readouterr().out
    assert main([str(root), "--api-dump", str(DUMP)]) == 0
    assert capsys.readouterr().out == first


# These deterministic fixtures drive the actual preflight() entrypoint, not a
# guessed filesystem resolver or an isolated parser. They use the source tree
# admitted by roblox_place.read_tree, including init.luau conversion.
def _require_project(tmp_path, scripts):
    root = tmp_path / "requires"
    for relative, source in scripts.items():
        file = root / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(source, encoding="utf-8")
    return root


@pytest.mark.parametrize(("scripts", "counts"), [
    pytest.param({
        "ServerScriptService/Main.server.luau": "local m = require(script.Parent.Config)",
        "ServerScriptService/Config.luau": "return {}",
    }, (1, 0, 0, 0), id="single-module"),
    pytest.param({
        "ServerScriptService/Feature/Main.server.luau":
            "local m = require(script.Parent.Parent.Config)",
        "ServerScriptService/Config.luau": "return {}",
    }, (1, 0, 0, 0), id="nested-parent"),
    pytest.param({
        "ServerScriptService/Main.server.luau":
            'local m = require(game:GetService("ReplicatedStorage").Shared.Config)',
        "ReplicatedStorage/Shared/Config.luau": "return {}",
    }, (1, 0, 0, 0), id="static-service"),
    pytest.param({
        "ServerScriptService/Main.server.luau": "local m = require(script.Parent.Kit)",
        "ServerScriptService/Kit/init.luau": "return {}",
    }, (1, 0, 0, 0), id="folder-init-module"),
    pytest.param({
        "ServerScriptService/Kit/init.luau": "return require(script.Helper)",
        "ServerScriptService/Kit/Helper.luau": "return {}",
    }, (1, 0, 0, 0), id="module-child"),
    pytest.param({
        "ServerScriptService/A.luau": "return require(script.Parent.B)",
        "ServerScriptService/B.luau": "return require(script.Parent.A)",
    }, (2, 1, 0, 0), id="two-module-cycle"),
    pytest.param({
        "ServerScriptService/Loop.luau": "return require(script)",
    }, (1, 1, 0, 0), id="self-cycle"),
    pytest.param({
        "ServerScriptService/Main.server.luau": "return require(script.Parent.Missing)",
    }, (0, 0, 1, 0), id="missing-static-module"),
    pytest.param({
        "ServerScriptService/Main.server.luau": "return require(script.Parent.Lib)",
        "ServerScriptService/Lib/Child.luau": "return {}",
    }, (0, 0, 1, 0), id="nonmodule-folder"),
    pytest.param({
        "ServerScriptService/Main.server.luau": "return require(chosenModule)",
    }, (0, 0, 0, 1), id="dynamic-variable"),
    pytest.param({
        "ServerScriptService/Main.server.luau":
            "local loader = require\nreturn loader(script.Parent.Config)",
        "ServerScriptService/Config.luau": "return {}",
    }, (0, 0, 0, 1), id="require-alias"),
    pytest.param({
        "ServerScriptService/Main.server.luau":
            'return require(script.Parent["Config"])',
        "ServerScriptService/Config.luau": "return {}",
    }, (0, 0, 0, 1), id="bracket-expression"),
    pytest.param({
        "ServerScriptService/Main.server.luau":
            'return require(game:GetService("Players").Helpers)',
    }, (0, 0, 0, 1), id="outside-supported-service"),
    pytest.param({
        "ServerScriptService/Main.server.luau":
            "return require(script.Parent.Parent.Config)",
        "ServerScriptService/Config.luau": "return {}",
    }, (0, 0, 0, 1), id="parent-outside-boundary"),
    pytest.param({
        "ServerScriptService/Main.server.luau":
            'return require(script.Parent.Config',
        "ServerScriptService/Config.luau": "return {}",
    }, (0, 0, 0, 1), id="malformed-require"),
    pytest.param({
        "ServerScriptService/Main.server.luau":
            "local function require(value) return value end\nreturn require(script.Parent.Config)",
        "ServerScriptService/Config.luau": "return {}",
    }, (0, 0, 0, 1), id="shadowed-require"),
    pytest.param({
        "ServerScriptService/Main.server.luau":
            "local script = {}\nreturn require(script.Parent.Missing)",
    }, (0, 0, 0, 1), id="shadowed-script-root"),
    pytest.param({
        "ServerScriptService/Main.server.luau":
            "local game = {}\nreturn require(game:GetService('ReplicatedStorage').Config)",
    }, (0, 0, 0, 1), id="shadowed-game-root"),
    pytest.param({
        "ServerScriptService/Main.server.luau":
            "local function load(require) return require(script.Parent.Absent) end",
    }, (0, 0, 0, 1), id="parameter-shadowed-require"),
    pytest.param({
        "ServerScriptService/Main.server.luau":
            "local function load(script) return require(script.Parent.Absent) end",
    }, (0, 0, 0, 1), id="parameter-shadowed-script"),
    pytest.param({
        "ServerScriptService/Main.server.luau":
            "local function load(game) return require(game:GetService('ReplicatedStorage').Absent) end",
    }, (0, 0, 0, 1), id="parameter-shadowed-game"),
    pytest.param({
        "ServerScriptService/Main.server.luau":
            '-- require(script.Parent.Missing)\n'
            '--[=[ require(script.Parent.Missing) ]=]\n'
            'local msg = "require(script.Parent.Missing)"\n'
            'local example = [==[require(script.Parent.Missing)]==]\n'
            'return true',
    }, (0, 0, 0, 0), id="strings-and-comments"),
    pytest.param({
        "ServerScriptService/Main.server.luau":
            "return require(script.Parent.Config)",
        "ServerScriptService/Config.luau": "return {}",
        "ServerScriptService/ConfigOld.luau": "return {}",
    }, (1, 0, 0, 0), id="exactly-named-target"),
])
def test_module_require_graph_real_preflight_fixtures(tmp_path, scripts, counts):
    root = _require_project(tmp_path, scripts)
    report = preflight(root, api_dump=DUMP, module_requires=True)
    graph = report["module_require_graph"]
    assert (len(graph["edges"]), len(graph["cycles"]),
            len(graph["missing"]), len(graph["unresolved"])) == counts
    assert graph["scanned_calls"] == sum(counts[:1] + counts[2:])
    assert not graph["truncated"] and not graph["skipped_sources"]
    assert all(edge["from"] in scripts and edge["to"] in scripts
               and edge["line"] >= 1 for edge in graph["edges"])
    assert all(item["file"] in scripts and item["line"] >= 1
               for item in graph["missing"] + graph["unresolved"])
    assert graph["status"] == ("findings" if counts[1] or counts[2] else
                               "partial" if counts[3] else "checked-static")
    assert report["summary"]["module_require_edges"] == counts[0]
    assert report["summary"]["module_require_missing"] == counts[2]
    assert report["summary"]["module_require_unresolved"] == counts[3]
    assert "Roblox" in " ".join(report["limitations"])


def test_module_require_cycle_and_missing_are_distinct_with_source_lines(tmp_path):
    root = _require_project(tmp_path, {
        "ServerScriptService/A.luau": "-- heading\nreturn require(script.Parent.B)",
        "ServerScriptService/B.luau": "return require(script.Parent.A)",
        "ServerScriptService/Main.server.luau":
            "require(script.Parent.Absent)\nrequire(script.Parent.A)",
    })
    graph = preflight(root, api_dump=DUMP, module_requires=True)["module_require_graph"]
    assert graph["cycles"] == [{"modules": [
        "ServerScriptService/A.luau", "ServerScriptService/B.luau"]}]
    assert graph["missing"] == [{
        "file": "ServerScriptService/Main.server.luau", "line": 1,
        "target": "ServerScriptService/Absent", "reason": "missing-from-source-tree",
    }]
    assert any(edge["from"] == "ServerScriptService/A.luau" and edge["line"] == 2
               for edge in graph["edges"])


def test_require_graph_off_preserves_default_report_and_cli_json(tmp_path, capsys):
    root = _require_project(tmp_path, {
        "ServerScriptService/Main.server.luau": "return require(script.Parent.Config)",
        "ServerScriptService/Config.luau": "return {}",
    })
    before = preflight(root, api_dump=DUMP)
    assert before == preflight(root, api_dump=DUMP, module_requires=False)
    assert "module_require_graph" not in before
    assert "module_require_edges" not in before["summary"]
    assert main([str(root), "--api-dump", str(DUMP)]) == 1
    default_json = capsys.readouterr().out
    assert main([str(root), "--api-dump", str(DUMP)]) == 1
    assert capsys.readouterr().out == default_json
    assert main([str(root), "--api-dump", str(DUMP), "--module-requires"]) == 1
    optin = json.loads(capsys.readouterr().out)
    assert optin["module_require_graph"]["status"] == "checked-static"
    assert "module-requires-static" in optin["files"][0]["checked_scope"]


def test_require_graph_failing_cli_missing_and_bad_tree_are_fail_closed(tmp_path, capsys):
    root = _require_project(tmp_path, {
        "ServerScriptService/Main.server.luau": "return require(script.Parent.Absent)",
    })
    assert main([str(root), "--api-dump", str(DUMP), "--module-requires"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "findings"
    assert report["module_require_graph"]["missing"][0]["line"] == 1
    assert main([str(root / "no-project"), "--module-requires"]) == 2
    invalid = json.loads(capsys.readouterr().out)
    assert invalid["status"] == "invalid" and invalid["files"] == []


def test_require_graph_source_budget_is_partial_not_a_clean_bill(tmp_path):
    root = _require_project(tmp_path, {
        "ServerScriptService/Main.server.luau":
            "--" + "x" * (MAX_CHECK_SOURCE_BYTES + 1) + "\n"
            + "return require(script.Parent.Undeclared)",
        "ServerScriptService/Util.luau": "return {}",
    })
    graph = preflight(root, api_dump=DUMP, module_requires=True)["module_require_graph"]
    assert graph["status"] == "partial"
    assert graph["scanned_calls"] == 0 and not graph["missing"]
    assert graph["skipped_sources"] == ["ServerScriptService/Main.server.luau"]
    assert graph["coverage"] == "partial"


def test_require_graph_limits_call_count_and_reports_truncation(tmp_path):
    root = _require_project(tmp_path, {
        "ServerScriptService/Main.server.luau":
            "local m = require(script.Parent.Config)\n" * 270,
        "ServerScriptService/Config.luau": "return {}",
    })
    graph = preflight(root, api_dump=DUMP, module_requires=True)["module_require_graph"]
    assert graph["scanned_calls"] == 256
    assert len(graph["edges"]) == 256
    assert graph["truncated"] and graph["status"] == "partial"
    assert graph["coverage"] == "partial"


def test_require_graph_has_deterministic_json_and_no_side_effects(tmp_path, monkeypatch, capsys):
    root = _require_project(tmp_path, {
        "ServerScriptService/Main.server.luau": "require(script.Parent.Shared)",
        "ServerScriptService/Shared.luau": "return {}",
    })
    before = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in root.rglob("*") if p.is_file()}
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Optional require preflight attempted a side effect")
    monkeypatch.setattr(Path, "write_text", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    monkeypatch.setattr("subprocess.run", forbidden)
    monkeypatch.setattr("socket.create_connection", forbidden)
    a = preflight(root, api_dump=DUMP, module_requires=True)
    b = preflight(root, api_dump=DUMP, module_requires=True)
    assert a == b
    assert before == {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*") if p.is_file()
    }
    assert main([str(root), "--api-dump", str(DUMP), "--module-requires"]) == 1
    assert json.loads(capsys.readouterr().out) == a
