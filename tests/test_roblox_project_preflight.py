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
