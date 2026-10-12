"""Offline regressions for STAR's bounded data understanding and note relationships."""
from __future__ import annotations

import json

import pytest

from star.data_analysis import MAX_PROFILE_CELLS, analyze, data_tool_schema
from star.document_tools import DocumentTools
from star.graphify_bridge import GraphifyGraph
from star.intelligence import LocalIntelligence
from star.obsidian_bridge import ObsidianVault


def _table(rows, columns=None, warnings=None):
    return [{"id": "data:quality", "name": "metrics.csv",
             "source": "metrics.csv:2-", "columns": columns or ["amount"],
             "rows": rows, "warnings": warnings or []}]


def _profile(rows, *, columns=None, warnings=None, **arguments):
    return analyze(_table(rows, columns=columns, warnings=warnings),
                   {"dataset_id": "data:quality", "operation": "profile", **arguments})


def test_profile_counts_missing_mixed_boolean_formula_and_numeric_extrema():
    output = _profile(
        [["Alpha", "1.25", True], ["", None, False],
         ["UNSHARED_CELL_SENTINEL", "=SUM(1,2)", None],
         ["2", "1e1000000", None], ["Beta", "-0.5", None]],
        columns=["label", "amount", "approved"], warnings=["An attached formula cache was missing."],
    )
    assert output["input_rows"] == 5 and output["profiled_columns"] == 3
    label, amount, approved = output["profiles"]
    assert (label["type_assessment"], label["missing_rows"], label["numeric_rows"],
            label["text_rows"]) == ("mixed", 1, 1, 3)
    assert (amount["missing_rows"], amount["numeric_rows"], amount["formula_text_rows"],
            amount["invalid_numeric_rows"]) == (1, 2, 1, 1)
    assert amount["numeric_min"] == "-0.5" and amount["numeric_max"] == "1.25"
    assert approved["type_assessment"] == "boolean"
    assert approved["boolean_rows"] == 2 and approved["missing_rows"] == 3
    assert output["counts_exact"] and output["source"] == "metrics.csv:2-"
    assert any("not evaluate" in warning for warning in output["warnings"])
    assert any("formula cache" in warning for warning in output["warnings"])
    assert "UNSHARED_CELL_SENTINEL" not in json.dumps(output)


def test_profile_empty_and_one_column_are_observational():
    output = _profile([[None], [""], ["   "]])
    assert output["profiles"][0]["type_assessment"] == "empty"
    assert output["profiles"][0]["missing_rows"] == 3
    assert output["profiles"][0]["numeric_min"] is None
    assert _profile([], columns=["amount"])["profiles"][0]["type_assessment"] == "empty"
    one = _profile([["a", "4"], ["b", "5"]], columns=["id", "amount"], column="amount")
    assert one["profiled_columns"] == 1 and one["profiles"][0]["numeric_max"] == "5"
    assert one["profiles"][0]["numeric_rows"] == 2


def test_profile_budgets_invalid_arguments_and_no_formula_execution():
    columns = [f"column_{number}" for number in range(41)]
    one_row = [["1"] * len(columns)]
    with pytest.raises(ValueError, match="more than 40"):
        _profile(one_row, columns=columns)
    assert _profile(one_row, columns=columns, column="column_0")["profiled_columns"] == 1
    with pytest.raises(ValueError, match="Profile exceeds"):
        _profile([["2"] * 5 for _ in range(MAX_PROFILE_CELLS // 5 + 1)],
                 columns=["a", "b", "c", "d", "e"])
    for kwargs in ({"column": "missing"}, {"group_by": "amount"},
                   {"filters": []}, {"column": None}):
        with pytest.raises(ValueError):
            _profile([["4"]], **kwargs)
    output = _profile([["=2+2"]])
    assert output["profiles"][0]["numeric_rows"] == 0
    assert output["profiles"][0]["formula_text_rows"] == 1


def test_data_tool_provenance_and_schema_distinguish_profiles_from_arithmetic():
    class Store:
        def datasets(self):
            return _table([[1], [None]])
    tool = DocumentTools(Store())
    assert "profile" in data_tool_schema()["function"]["parameters"]["properties"]["operation"]["enum"]
    response = tool.call("star_data_analyze",
                         {"dataset_id": "data:quality", "operation": "profile"},
                         enabled={"star_data_analyze"})
    assert not response["isError"]
    assert response["structuredContent"]["provenance"]["kind"] == "bounded_table_profile"
    assert response["structuredContent"]["profiles"][0]["missing_rows"] == 1
    arithmetic = tool.call("star_data_analyze",
                           {"dataset_id": "data:quality", "operation": "sum", "column": "amount"},
                           enabled={"star_data_analyze"})
    assert arithmetic["structuredContent"]["provenance"]["kind"] == "bounded_decimal_calculation"


def test_wikilink_graph_cites_lines_and_never_guesses_ambiguous_targets(tmp_path):
    vault = tmp_path / "vault"
    (vault / "Design").mkdir(parents=True)
    (vault / "Notes").mkdir()
    (vault / "Archive").mkdir()
    (vault / ".obsidian").mkdir()
    (vault / ".obsidian" / "Private.md").write_text("EXCLUDED_NOTE_SENTINEL")
    (vault / "Design" / "Decision.md").write_text("# Decision\nNo cross-project reads.\n")
    (vault / "Notes" / "Overview.md").write_text(
        "[[Design/Decision#Reason|Important]]\n[[Decision]]\n"
        "~~~md\n[[Design/Decision]]\n~~~\n[[.obsidian/Private]]\n")
    (vault / "Archive" / "Decision.md").write_text("# Other decision\n")
    (vault / "Review.md").write_text("Reviewed [[Design/Decision.md]] in v2.\n")
    obsidian = ObsidianVault(vault)
    graph = obsidian.links("Design/Decision.md")
    assert {x["path"] for x in graph["backlinks"]} == {"Notes/Overview.md", "Review.md"}
    assert {x["line"] for x in graph["backlinks"]} == {1}
    assert graph["backlinks_total"] == 2 and not graph["partial_scan"]
    assert graph["unresolved_or_ambiguous_links"] >= 2
    assert graph["backlinks_total"] == 2 and not graph["partial_scan"]
    assert graph["read_only"] is True
    assert "Private.md" not in json.dumps(graph)
    other = obsidian.links("Notes/Overview.md")
    assert other["outgoing"] == [{"path": "Design/Decision.md", "line": 1}]
    with pytest.raises(PermissionError):
        obsidian.links(".obsidian/Private.md")
    with pytest.raises(PermissionError):
        obsidian.links("../Private.md")
    with pytest.raises(ValueError):
        obsidian.links("Review.md", limit=True)
    # A non-hidden symlink cannot be used to reach excluded vault settings.
    alias = vault / "Friendly"
    try:
        alias.symlink_to(vault / ".obsidian", target_is_directory=True)
    except (OSError, NotImplementedError):
        pass  # Windows environments may disallow creating test symlinks.
    else:
        with pytest.raises(PermissionError):
            obsidian.read("Friendly/Private.md")
        with pytest.raises(PermissionError):
            obsidian.links("Friendly/Private.md")


def test_wikilink_graph_marks_preview_truncation_as_incomplete(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Target.md").write_text("Target")
    (vault / "Long.md").write_text("padding\n" * 11_000 + "[[Target]]\n")
    result = ObsidianVault(vault).links("Target.md")
    assert result["backlinks"] == []
    assert result["partial_scan"] is True
    assert result["preview_truncated_notes"] >= 1


def test_obsidian_graph_tool_requires_scope_and_relevant_prompt(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "A.md").write_text("[[B]]")
    (vault / "B.md").write_text("# B")
    hub = LocalIntelligence(home=tmp_path / "home", obsidian_vault=vault,
                            skills_enabled=False, roblox_research_enabled=False)
    assert hub.definitions("Hello") == []
    enabled = {x["name"] for x in hub.definitions("Which backlinks connect my notes?")}
    assert "star_obsidian_links" in enabled
    with pytest.raises(PermissionError):
        hub.call("star_obsidian_links", {"path": "B.md"}, enabled=set())
    assert hub.call("star_obsidian_links", {"path": "B.md"}, enabled=enabled)["backlinks_total"] == 1


def test_graphify_path_longer_than_cap_is_labeled_incomplete(tmp_path):
    location = tmp_path / "graphify-out"
    location.mkdir()
    nodes = [{"id": f"node{i}", "label": f"Node {i}"} for i in range(36)]
    edges = [{"source": f"node{i}", "target": f"node{i+1}",
              "relation": "calls", "confidence": "EXTRACTED"} for i in range(35)]
    (location / "graph.json").write_text(json.dumps({"nodes": nodes, "links": edges}))
    hub = LocalIntelligence(home=tmp_path / "home", workspace=tmp_path,
                            skills_enabled=False, roblox_research_enabled=False)
    names = {item["name"] for item in hub.definitions("Trace this graph path")}
    assert "star_graphify_path" in names
    result = hub.call("star_graphify_path", {"start": "Node 0", "end": "Node 35"},
                      enabled=names)
    assert result["found"] and result["hops"] == 35
    assert result["returned_hops"] == 29 and result["truncated"]
    assert len(result["path"]) == 30
    assert result["path"][-1]["node"]["label"] != "Node 35"
    assert "incomplete" in result["notice"] or "omitted" in result["notice"]
    short = hub.call("star_graphify_path", {"start": "Node 0", "end": "Node 1"},
                     enabled=names)
    assert short["found"] and not short["truncated"] and short["returned_hops"] == 1
    assert not GraphifyGraph(tmp_path).path_between("Missing", "Node 1")["found"]
