"""scripts/build_brain_graph.py turns Graphify graphs into the website's small, honest "STAR's brain" data."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_brain_graph.py"
spec = importlib.util.spec_from_file_location("build_brain_graph", SCRIPT)
brain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(brain)


def graph(files: dict[str, int], calls: list[tuple[str, str]], commit: str = "abc1234def") -> dict:
    nodes, links = [], []
    for path, count in files.items():
        for index in range(count):
            nodes.append({"id": f"{path}:{index}", "label": f"f{index}", "source_file": path, "community": hash(path) % 3})
    for a, b in calls:
        links.append({"source": f"{a}:0", "target": f"{b}:0", "relation": "calls", "weight": 1.0})
    return {"directed": False, "multigraph": False, "graph": {}, "nodes": nodes, "links": links, "built_at_commit": commit}


def write(tmp_path: Path, name: str, data: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_collapses_symbols_into_linked_files_with_areas_layout_and_history(tmp_path):
    old = write(tmp_path, "old.json", graph({"star/agent.py": 3, "tests/test_agent.py": 1}, [("tests/test_agent.py", "star/agent.py")], "1111111aaa"))
    new = write(tmp_path, "new.json", graph(
        {"star/agent.py": 5, "star/lessons.py": 2, "frontend/src/App.tsx": 4, "server/brain/x.py": 1, "lonely.py": 9},
        [("star/agent.py", "star/lessons.py"), ("star/agent.py", "server/brain/x.py"), ("star/lessons.py", "star/agent.py"),
         ("frontend/src/App.tsx", "frontend/src/App.tsx")]))
    out, summary, svg = tmp_path / "graph.json", tmp_path / "summary.json", tmp_path / "graph.svg"
    assert brain.main(["--current", f"1.0={new}", "--history", f"0.9.0={old}", "--out", str(out),
                       "--summary", str(summary), "--svg", str(svg)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    files = {node["f"]: node for node in data["nodes"]}
    # Only files with a link to another shown file stay; links inside one file are not drawn.
    assert set(files) == {"star/agent.py", "star/lessons.py", "server/brain/x.py"}
    assert files["star/agent.py"]["s"] == 5
    assert data["areas"][files["star/lessons.py"]["a"]]["id"] == "learning"
    assert data["areas"][files["server/brain/x.py"]["a"]]["id"] == "server"
    assert all(0 <= node["x"] <= 1 and 0 <= node["y"] <= 1 for node in data["nodes"])
    # agent<->lessons appears twice in the symbol graph and is merged into one link of weight 2.
    assert sorted(link[2] for link in data["links"]) == [1.0, 2.0]
    assert [(h["version"], h["nodes"], h["files"], h["commit"]) for h in data["history"]] == [
        ("0.9.0", 4, 2, "1111111"), ("1.0", 21, 5, "abc1234")]
    assert "Not neurons" in data["about"]
    small = json.loads(summary.read_text(encoding="utf-8"))
    assert "nodes" not in small and "links" not in small and small["current"]["files"] == 5
    assert svg.read_text(encoding="utf-8").startswith("<svg") and svg.read_text(encoding="utf-8").count("<circle") == 3


def test_is_deterministic(tmp_path):
    source = write(tmp_path, "g.json", graph({f"star/m{i}.py": i + 1 for i in range(12)},
                                             [(f"star/m{i}.py", f"star/m{(i * 5 + 1) % 12}.py") for i in range(12)]))
    first = brain.build(("1.0", source.resolve()), [])
    second = brain.build(("1.0", source.resolve()), [])
    assert first["nodes"] == second["nodes"] and first["links"] == second["links"]


def test_committed_site_data_is_small_timestamped_and_free_of_local_paths():
    data = (ROOT / "frontend" / "src" / "brainGraph.json").read_text(encoding="utf-8")
    summary = json.loads((ROOT / "frontend" / "src" / "brainSummary.json").read_text(encoding="utf-8"))
    assert len(data.encode()) < 60_000
    assert summary["generatedAt"].endswith("Z") and summary["current"]["commit"]
    versions = [entry["version"] for entry in summary["history"]]
    assert versions[0] == "0.6.0" and versions[-1] == summary["current"]["version"]
    for text in (data, json.dumps(summary)):
        assert "Users" not in text and ":\\\\" not in text and "/home/" not in text
