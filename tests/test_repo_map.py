"""Offline tests for STAR's opt-in, bounded dependency-ranked source map."""
from __future__ import annotations

import json

import pytest

from star.repo_map import code_map, MAX_MAP_RESULT_BYTES
from star.workspace import Workspace


def write(root, name: str, source: str):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def test_code_map_prioritizes_requested_symbols_and_tracks_unique_references(tmp_path):
    write(tmp_path, "src/inventory.py",
          "class InventoryStore:\n    def load_items(self, player_id):\n        return []\n")
    write(tmp_path, "src/controller.py",
          "from inventory import InventoryStore\n"
          "def show_inventory():\n    return InventoryStore().load_items(1)\n")
    write(tmp_path, "src/unrelated.py", "def play_music():\n    return True\n")
    report = Workspace(tmp_path).call("workspace_search", {"query": "InventoryStore", "mode": "map"})
    assert report["mode"] == "map"
    assert report["scanned_files"] == 3
    assert report["dependency_links"] >= 1
    assert report["files"][0]["file"] == "src/inventory.py"
    assert any(symbol["name"] == "InventoryStore" for symbol in report["files"][0]["symbols"])
    assert report["caveat"].startswith("Code-navigation hints")
    assert len(json.dumps(report, ensure_ascii=False)) <= MAX_MAP_RESULT_BYTES


def test_luau_typescript_and_other_languages_are_included_as_heuristics(tmp_path):
    write(tmp_path, "game/Round.server.luau", "local function startRound()\nend\n")
    write(tmp_path, "frontend/Hud.tsx", "export function RoundHUD() { return null; }\n")
    write(tmp_path, "godot/Scene.gd", "func restart_round():\n\tpass\n")
    write(tmp_path, "unity/Round.cs", "public class RoundController {}\n")
    report = Workspace(tmp_path).call("workspace_search", {"query": "round", "mode": "map"})
    names = {symbol["name"] for item in report["files"] for symbol in item["symbols"]}
    assert {"startRound", "RoundHUD", "restart_round", "RoundController"} <= names
    assert report["method"] == "python-ast-plus-heuristic-symbol-graph"


def test_private_generated_and_symlink_paths_are_not_indexed(tmp_path):
    write(tmp_path, "src/approved.py", "def approved_symbol():\n    return 7\n")
    write(tmp_path, "node_modules/dependency.py", "def leaked_symbol():\n    pass\n")
    write(tmp_path, ".git/private.py", "def leaked_symbol():\n    pass\n")
    write(tmp_path, "build/secret.py", "def leaked_symbol():\n    pass\n")
    write(tmp_path, "src/secrets.json", '{"key":"private"}')
    write(tmp_path, ".env", "PRIVATE_TOKEN=secret")
    outside = tmp_path.parent / "external-private-file.py"
    outside.write_text("def leaked_symbol(): pass", encoding="utf-8")
    try:
        (tmp_path / "private_link.py").symlink_to(outside)
    except (OSError, NotImplementedError):
        pass
    report = Workspace(tmp_path).call("workspace_search", {"query": "symbol", "mode": "map"})
    assert report["scanned_files"] == 1
    assert {item["file"] for item in report["files"]} == {"src/approved.py"}
    assert "leaked_symbol" not in json.dumps(report)


def test_map_does_not_execute_workspace_source(tmp_path):
    write(tmp_path, "would_execute.py",
          'raise RuntimeError("must never run")\ndef inspected_symbol():\n    pass\n')
    report = Workspace(tmp_path).call("workspace_search",
                                      {"query": "inspected_symbol", "mode": "map"})
    assert report["files"][0]["symbols"][0]["name"] == "inspected_symbol"


def test_credential_literal_in_signature_is_redacted(tmp_path):
    token = "sk-" + "A" * 32
    write(tmp_path, "source.py",
          f"def connect(api_key='{token}'):\\n    pass\\n".replace("\\\\n", "\\n"))
    report = Workspace(tmp_path).call("workspace_search",
                                      {"query": "connect", "mode": "map"})
    serialized = json.dumps(report)
    assert token not in serialized
    assert "[REDACTED]" in serialized


def test_reindex_after_file_edits_and_keep_legacy_search(tmp_path):
    path = write(tmp_path, "module.py", "def initial_symbol():\n    return 1\n")
    ws = Workspace(tmp_path)
    before = ws.call("workspace_search", {"query": "initial_symbol", "mode": "map"})
    assert before["files"][0]["symbols"][0]["name"] == "initial_symbol"
    path.write_text("def changed_symbol():\n    return 2\n", encoding="utf-8")
    after = ws.call("workspace_search", {"query": "changed_symbol", "mode": "map"})
    assert after["files"][0]["symbols"][0]["name"] == "changed_symbol"
    assert ws.call("workspace_search", {"query": "changed_symbol", "mode": "symbols"})["mode"] == "symbols"
    assert ws.call("workspace_search", {"query": "return"})["mode"] == "text"


def test_bounded_file_scan_and_total_bytes(tmp_path, monkeypatch):
    from star import repo_map
    monkeypatch.setattr(repo_map, "MAX_MAP_FILES", 2)
    for number in range(6):
        write(tmp_path, f"mod{number}.py", f"def special{number}():\n    pass\n")
    report = Workspace(tmp_path).call("workspace_search", {"query": "special", "mode": "map"})
    assert report["scanned_files"] == 2
    assert report["incomplete"] is True
    assert len(json.dumps(report, ensure_ascii=False)) <= MAX_MAP_RESULT_BYTES
    monkeypatch.setattr(repo_map, "MAX_MAP_SOURCE_BYTES", 4)
    smaller = Workspace(tmp_path).call("workspace_search", {"query": "special", "mode": "map"})
    assert smaller["incomplete"] is True
    assert smaller["files"] == []


def test_bounded_output_and_no_input_data_mutation(tmp_path):
    for number in range(36):
        write(tmp_path, f"mod{number}.py",
              f"def module_{number}_long_function(very_long_parameter_name):\n"
              f"    return very_long_parameter_name\n")
    original = (tmp_path / "mod0.py").read_bytes()
    result = Workspace(tmp_path).call("workspace_search", {"query": "module", "mode": "map"})
    assert result["incomplete"] is True
    assert len(result["files"]) <= 12
    assert len(json.dumps(result, ensure_ascii=False)) <= MAX_MAP_RESULT_BYTES
    assert (tmp_path / "mod0.py").read_bytes() == original


@pytest.mark.parametrize("query", ["", " ", ":", "x" * 301])
def test_invalid_code_map_query_rejected(tmp_path, query):
    with pytest.raises(ValueError):
        code_map(Workspace(tmp_path), query)


def test_empty_project_reports_empty_map(tmp_path):
    result = Workspace(tmp_path).call("workspace_search", {"query": "inventory", "mode": "map"})
    assert result["files"] == []
    assert result["scanned_files"] == 0
    assert not result["incomplete"]
