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


def test_api_confusions_cli_optin_reports_twelve_diverse_source_linked_candidates(
        tmp_path, capsys):
    from star.roblox_api_confusions import load_confusions

    root = _project(tmp_path)
    examples = load_confusions()
    chosen = [examples[i] for i in (0, 10, 22, 33, 37, 41, 47, 53, 57, 65, 72, 79)]
    source = root / "ServerScriptService/Main.server.luau"
    source.write_text(
        "local custom = {}\n" +
        "".join("custom" + entry["wrong"] + "nil)\n" for entry in chosen),
        encoding="utf-8")

    assert main([str(root), "--api-confusions"]) == 1
    report = json.loads(capsys.readouterr().out)
    records = _files(report)["ServerScriptService/Main.server.luau"]
    advisory = [f for f in records["findings"]
                if f["checker"] == "roblox-api-confusions"]
    assert len(advisory) == 12
    assert [(f["line"], f["column"], f["wrong"], f["right"], f["source_url"])
            for f in advisory] == [
        (i + 2, 7, entry["wrong"], entry["right"], entry["source_url"])
        for i, entry in enumerate(chosen)
    ]
    assert all(f["rule"] == "api-confusion:possible-method-spelling"
               and f["category"] == "advisory" and f["severity"] == "info"
               and f["receiver_evidence"] == "unverified"
               and f["receiver_class"] is None
               and "custom methods may be valid" in f["message"]
               for f in advisory)
    assert records["status"] == "partial"
    assert "api-confusion-spellings-advisory" in records["checked_scope"]
    assert report["summary"]["api_confusion_candidates"] == 12
    assert report["summary"]["api_confusion_advisories"] == 12
    assert report["summary"]["api_confusion_confirmed_engine_errors"] == 0
    assert "receiver types" in " ".join(records["unverified"])
    assert report["coverage"] == "partial"
    assert "Studio verification" in " ".join(report["limitations"])


def test_optin_reuses_api_dump_only_for_unambiguous_inferred_class(
        tmp_path, capsys):
    root = _project(tmp_path)
    (root / "ServerScriptService/Main.server.luau").write_text(
        'local part = Instance.new("Part")\n'
        'part:GetAllChildren()\n'
        'local custom = {}\n'
        'function custom:GetAllChildren() return {} end\n'
        'custom:GetAllChildren()\n'
        'local ws = game:GetService("Workspace")\n'
        'ws:RayCast(Vector3.zero, Vector3.yAxis)\n'
        'ws:Raycast(Vector3.zero, Vector3.yAxis)\n'
        'part:GetChildren()\n'
        'local quoted = "part:GetAllChildren()"\n'
        'local long = [=[\npart:GetAllChildren()\n]=]\n'
        'local tick = ' + chr(96) + 'part:GetAllChildren()' + chr(96) + '\n'
        '-- part:GetAllChildren()\n'
        '--[=[ ws:RayCast() ]=]\n',
        encoding="utf-8")

    assert main([str(root), "--api-dump", str(DUMP), "--api-confusions"]) == 1
    report = json.loads(capsys.readouterr().out)
    all_findings = _files(report)["ServerScriptService/Main.server.luau"]["findings"]
    advisory = [f for f in all_findings if f.get("category") == "advisory"]
    assert [(f["line"], f["wrong"]) for f in advisory] == [
        (2, ":GetAllChildren("), (4, ":GetAllChildren("),
        (5, ":GetAllChildren("), (7, ":RayCast("),
    ]
    assert [(f["receiver_evidence"], f["receiver_class"]) for f in advisory] == [
        ("api-dump-inferred-class", "Part"),
        ("unverified", None), ("unverified", None),
        ("api-dump-inferred-class", "Workspace"),
    ]
    assert all(f["severity"] == "info" and "custom methods" in f["message"]
               for f in advisory)
    assert sum(f["rule"] == "api:unknown-member" for f in all_findings) == 2
    assert report["summary"]["api_confusion_confirmed_engine_errors"] == 0


def test_optin_does_not_change_default_cli_json(tmp_path, capsys):
    root = _project(tmp_path)
    assert main([str(root), "--api-dump", str(DUMP)]) == 0
    baseline = capsys.readouterr().out
    assert main([str(root), "--api-dump", str(DUMP)]) == 0
    assert capsys.readouterr().out == baseline
    assert json.loads(baseline) == preflight(root, api_dump=DUMP, api_confusions=False)
    assert "api_confusion_candidates" not in json.loads(baseline)["summary"]
    assert not any("api-confusion" in scope for f in json.loads(baseline)["files"]
                   for scope in f["checked_scope"])


def test_optin_caps_advisories_and_marks_omitted_candidates(tmp_path, capsys):
    root = _project(tmp_path)
    (root / "ServerScriptService/Main.server.luau").write_text(
        "local custom = {}\n" + "custom:FindChild()\n" * 60,
        encoding="utf-8")
    assert main([str(root), "--api-confusions"]) == 1
    report = json.loads(capsys.readouterr().out)
    source = _files(report)["ServerScriptService/Main.server.luau"]
    assert len(source["findings"]) == 50
    assert all(f["category"] == "advisory" for f in source["findings"])
    assert report["summary"]["api_confusion_candidates"] == 60
    assert report["summary"]["api_confusion_advisories"] == 50
    assert report["summary"]["api_confusion_confirmed_engine_errors"] == 0
    assert any("truncated" in warning for warning in source["unverified"])
    assert len(json.dumps(report)) < 30_000


def test_optin_does_not_scan_source_above_existing_budget(tmp_path):
    root = _project(tmp_path)
    (root / "ServerScriptService/Main.server.luau").write_text(
        "-- " + "x" * (MAX_CHECK_SOURCE_BYTES + 2) + "\n"
        + "custom:FindChild()\n", encoding="utf-8")
    report = preflight(root, api_dump=DUMP, api_confusions=True)
    file = _files(report)["ServerScriptService/Main.server.luau"]
    assert file["checked_scope"] == []
    assert file["findings"] == []
    assert report["summary"]["api_confusion_candidates"] == 0


def test_optin_keeps_malformed_luau_corpus_hits_advisory(tmp_path):
    root = _project(tmp_path)
    (root / "ServerScriptService/Main.server.luau").write_text(
        'local part = Instance.new("Part")\npart:GetAllChildren(\n',
        encoding="utf-8")
    report = preflight(root, api_dump=DUMP, api_confusions=True)
    hits = [f for f in _files(report)["ServerScriptService/Main.server.luau"]["findings"]
            if f.get("category") == "advisory"]
    assert len(hits) == 1 and hits[0]["line"] == 2
    assert hits[0]["receiver_evidence"] == "api-dump-inferred-class"
    assert hits[0]["category"] == "advisory"
    assert report["summary"]["api_confusion_confirmed_engine_errors"] == 0
    assert "Luau is not executed or typechecked" in " ".join(report["limitations"])


def test_optin_bad_dump_and_missing_corpus_fail_closed(tmp_path, capsys, monkeypatch):
    from star import roblox_api_confusions as api

    root = _project(tmp_path)
    bad = tmp_path / "api.json"
    bad.write_text("{}", encoding="utf-8")
    assert main([str(root), "--api-dump", str(bad), "--api-confusions"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "invalid"

    original = api.DATA
    monkeypatch.setattr(api, "DATA", tmp_path / "absent-corpus.json")
    api.load_confusions.cache_clear()
    try:
        assert main([str(root), "--api-dump", str(DUMP)]) == 0
        assert json.loads(capsys.readouterr().out)["status"] == "checked"
        assert main([str(root), "--api-dump", str(DUMP), "--api-confusions"]) == 2
        invalid = json.loads(capsys.readouterr().out)
        assert invalid["status"] == "invalid"
        assert invalid["files"] == [] and invalid["coverage"] == "none"
        assert "corpus" in invalid["error"].lower()
    finally:
        monkeypatch.setattr(api, "DATA", original)
        api.load_confusions.cache_clear()


def test_optin_never_writes_project_runs_code_or_calls_network(tmp_path, monkeypatch):
    root = _project(tmp_path)
    (root / "ServerScriptService/Main.server.luau").write_text(
        'local part = Instance.new("Part")\npart:GetAllChildren()\n',
        encoding="utf-8")
    before = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in root.rglob("*") if p.is_file()}

    def forbidden(*args, **kwargs):
        raise AssertionError("optional preflight attempted side effects")

    monkeypatch.setattr(Path, "write_text", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    monkeypatch.setattr("subprocess.run", forbidden)
    monkeypatch.setattr("socket.create_connection", forbidden)
    report = preflight(root, api_dump=DUMP, api_confusions=True)
    assert report["summary"]["api_confusion_advisories"] == 1
    assert before == {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*") if p.is_file()
    }
