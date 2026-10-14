"""Build the website's "STAR's brain" data from Graphify code graphs.

"Brain" here means STAR's code and knowledge structure as Graphify sees it (functions, classes and modules, and the
calls and imports between them). It is not a neural network and says nothing about how well STAR answers.

Run Graphify first, in a clean checkout of each version (graphify-out/ is git-ignored):

    git worktree add --detach ../brain-v0.9.0 v0.9.0
    cd ../brain-v0.9.0 && graphify extract . --code-only

Then, from the repository root:

    python scripts/build_brain_graph.py \
        --current "1.0=../brain-next/graphify-out/graph.json" \
        --history "0.6.0=../brain-v0.6.0/graphify-out/graph.json" \
        --history "0.8.1=../brain-v0.8.1/graphify-out/graph.json" \
        --history "0.9.0=../brain-v0.9.0/graphify-out/graph.json"

It writes frontend/src/brainGraph.json (about 30 kB, loaded only when the section comes into view: the most connected
files, their links and a precomputed force-directed layout), frontend/src/brainSummary.json (the totals and per-version
counts the page prerenders) and frontend/public/site/brain-graph.svg (the static image shown before the canvas).
Pure Python, no network, deterministic: the same graphs give the same files.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]
KEEP_FILES = 260
KEEP_LINKS = 720
SVG_LINKS = 420

# Areas colour the graph. Order matters: the first matching rule wins.
AREAS = [
    ("learning", "Learning", "#C9A2FF", ("star/night", "star/lessons", "star/learned", "star/practice", "star/corrections",
                                          "star/worked_examples", "star/failure_ledger", "star/eval", "server/night_school",
                                          "server/training")),
    ("roblox", "Roblox", "#FF8F66", ("star/roblox", "star/luau", "star/studio", "star/rbx", "star/map_plan", "examples/")),
    ("interface", "Interface", "#5CC8FF", ("frontend/", "star/react_shell", "star/desktop")),
    ("server", "Server", "#5BE3A1", ("server/",)),
    ("core", "Core", "#FFC857", ("star/",)),
    ("tests", "Tests and evaluations", "#A3B1BD", ("tests/", "evals/")),
    ("other", "Scripts and other", "#E9D8A6", ("",)),
]


def area_of(path: str) -> int:
    for index, (_, _, _, prefixes) in enumerate(AREAS):
        if any(path.startswith(prefix) for prefix in prefixes):
            return index
    return len(AREAS) - 1


def load(path: Path) -> dict:
    graph = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("links"), list):
        raise SystemExit(f"{path}: not a Graphify graph.json (needs 'nodes' and 'links')")
    return graph


def totals(graph: dict) -> dict:
    files = {node.get("source_file") or "" for node in graph["nodes"]}
    files.discard("")
    communities = {node.get("community") for node in graph["nodes"] if node.get("community") is not None}
    return {"nodes": len(graph["nodes"]), "edges": len(graph["links"]), "communities": len(communities),
            "files": len(files)}


def file_graph(graph: dict):
    """Collapse symbols into files: a file's size is its symbol count, a link's weight the number of symbol links."""
    file_of = {node["id"]: node.get("source_file") or "" for node in graph["nodes"]}
    symbols = Counter(path for path in file_of.values() if path)
    weights: dict[tuple[str, str], float] = defaultdict(float)
    for link in graph["links"]:
        a, b = file_of.get(link.get("source")), file_of.get(link.get("target"))
        if not a or not b or a == b:
            continue
        key = (a, b) if a < b else (b, a)
        weights[key] += float(link.get("weight") or 1.0)
    return symbols, weights


def layout(count: int, links: list[tuple[int, int, float]], groups: list[int], iterations: int = 320) -> list[tuple[float, float]]:
    """Fruchterman-Reingold force layout in the unit square, seeded so it is reproducible."""
    rng = random.Random(7)
    # Start each area around its own point on a circle, so related files begin near each other.
    anchors = {g: (0.5 + 0.3 * math.cos(2 * math.pi * g / len(AREAS)), 0.5 + 0.3 * math.sin(2 * math.pi * g / len(AREAS)))
               for g in range(len(AREAS))}
    pos = [[anchors[groups[i]][0] + rng.uniform(-.08, .08), anchors[groups[i]][1] + rng.uniform(-.08, .08)] for i in range(count)]
    k = math.sqrt(1.0 / max(count, 1)) * 0.9
    temperature = 0.1
    for step in range(iterations):
        disp = [[0.0, 0.0] for _ in range(count)]
        for i in range(count):
            xi, yi = pos[i]
            for j in range(i + 1, count):
                dx, dy = xi - pos[j][0], yi - pos[j][1]
                dist2 = dx * dx + dy * dy or 1e-9
                force = k * k / dist2
                disp[i][0] += dx * force; disp[i][1] += dy * force
                disp[j][0] -= dx * force; disp[j][1] -= dy * force
        for a, b, w in links:
            dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
            dist = math.sqrt(dx * dx + dy * dy) or 1e-9
            force = dist / k * min(1.0 + math.log1p(w) * 0.35, 3.0)
            disp[a][0] -= dx * force; disp[a][1] -= dy * force
            disp[b][0] += dx * force; disp[b][1] += dy * force
        for i in range(count):
            # A weak pull to the centre keeps small islands on the canvas.
            disp[i][0] += (0.5 - pos[i][0]) * 1.4; disp[i][1] += (0.5 - pos[i][1]) * 1.4
            length = math.sqrt(disp[i][0] ** 2 + disp[i][1] ** 2) or 1e-9
            pos[i][0] += disp[i][0] / length * min(length, temperature)
            pos[i][1] += disp[i][1] / length * min(length, temperature)
        temperature = max(0.002, temperature * 0.985)
    # Fit the 2nd-98th percentile box to the unit square (each axis on its own: the canvas is wide), clamping the
    # few outliers to the edge instead of letting them shrink everything else.
    def fit(values):
        ordered = sorted(values)
        low, high = ordered[int(len(ordered) * .02)], ordered[int(len(ordered) * .98) - 1]
        span = (high - low) or 1.0
        return [min(1.0, max(0.0, (v - low) / span)) for v in values]
    return list(zip(fit([p[0] for p in pos]), fit([p[1] for p in pos])))


def build(current: tuple[str, Path], history: list[tuple[str, Path]]) -> dict:
    label, path = current
    graph = load(path)
    symbols, weights = file_graph(graph)
    degree = Counter()
    for (a, b), w in weights.items():
        degree[a] += w; degree[b] += w
    ranked = sorted(symbols, key=lambda f: (-(degree[f] + symbols[f] * 0.5), f))[:KEEP_FILES]
    index = {f: i for i, f in enumerate(ranked)}
    links = sorted(((index[a], index[b], w) for (a, b), w in weights.items() if a in index and b in index),
                   key=lambda link: (-link[2], link[0], link[1]))[:KEEP_LINKS]
    # A file with no link left among the shown ones would float alone; leave it out and renumber.
    linked = sorted({i for a, b, _ in links for i in (a, b)})
    ranked = [ranked[i] for i in linked]
    renumber = {old: new for new, old in enumerate(linked)}
    links = [(renumber[a], renumber[b], w) for a, b, w in links]
    groups = [area_of(f) for f in ranked]
    coords = layout(len(ranked), links, groups)
    area_files = Counter(area_of(f) for f in symbols)
    versions = []
    for version, history_path in history + [current]:
        past = graph if history_path == path else load(history_path)
        versions.append({"version": version, **totals(past), "commit": (past.get("built_at_commit") or "")[:7]})
    return {
        "about": "STAR's code structure as Graphify sees it: files, their functions and classes, and the calls and "
                 "imports between them. Not neurons, and not a measure of answer quality.",
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "graphify": "graphify extract . --code-only",
        "current": {"version": label, "commit": (graph.get("built_at_commit") or "")[:7], **totals(graph)},
        "areas": [{"id": a[0], "label": a[1], "color": a[2], "files": area_files.get(i, 0)} for i, a in enumerate(AREAS)],
        "shown": {"files": len(ranked), "links": len(links)},
        "nodes": [{"f": f, "a": groups[i], "s": symbols[f], "x": round(coords[i][0], 4), "y": round(coords[i][1], 4)}
                  for i, f in enumerate(ranked)],
        "links": [[a, b, round(w, 1)] for a, b, w in links],
        "history": versions,
    }


def svg(data: dict) -> str:
    width, height, pad = 1000, 640, 28
    def point(node):
        return pad + node["x"] * (width - 2 * pad), pad + node["y"] * (height - 2 * pad)
    nodes = data["nodes"]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" '
           f'aria-label="A map of STAR\'s code: {len(nodes)} most connected files, coloured by area">',
           f'<rect width="{width}" height="{height}" fill="#090B0E"/>',
           '<g stroke-opacity=".32" stroke-width="1">']
    for a, b, _ in data["links"][:SVG_LINKS]:
        (x1, y1), (x2, y2) = point(nodes[a]), point(nodes[b])
        color = data["areas"][nodes[a]["a"]]["color"]
        out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}"/>')
    out.append("</g><g>")
    for node in nodes:
        x, y = point(node)
        radius = 2 + math.sqrt(node["s"]) * 0.75
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{min(radius, 13):.1f}" fill="{data["areas"][node["a"]]["color"]}" fill-opacity="1"/>')
    out.append("</g></svg>")
    return "\n".join(out) + "\n"


def parse_pair(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("use VERSION=path/to/graph.json")
    version, path = value.split("=", 1)
    return version.strip(), Path(path).expanduser().resolve()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--current", required=True, type=parse_pair, help="VERSION=graph.json of the version shown")
    parser.add_argument("--history", action="append", default=[], type=parse_pair, help="VERSION=graph.json, oldest first")
    parser.add_argument("--out", default=str(ROOT / "frontend" / "src" / "brainGraph.json"))
    parser.add_argument("--summary", default=str(ROOT / "frontend" / "src" / "brainSummary.json"))
    parser.add_argument("--svg", default=str(ROOT / "frontend" / "public" / "site" / "brain-graph.svg"))
    args = parser.parse_args(argv)
    data = build(args.current, args.history)
    Path(args.out).write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")
    summary = {key: value for key, value in data.items() if key not in ("nodes", "links")}
    Path(args.summary).write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    Path(args.svg).write_text(svg(data), encoding="utf-8")
    current = data["current"]
    print(f"{current['version']}: {current['nodes']} symbols, {current['edges']} links, {current['files']} files, "
          f"{current['communities']} communities; showing {data['shown']['files']} files and {data['shown']['links']} links")
    for entry in data["history"]:
        print(f"  {entry['version']:>6} {entry['nodes']:>6} symbols {entry['edges']:>6} links {entry['files']:>4} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
