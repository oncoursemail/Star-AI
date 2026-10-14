"""Fundamentals knowledge: skill packs, the general JSON suite and the pure-Luau golden suite (offline checks only)."""
import heapq
import json
import math
import re
from pathlib import Path

import pytest

from star import eval_runner, general_knowledge_benchmark as bench, skill_packs

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "research" / "fundamentals"
PACKS = {
    "fund-algorithms": "algorithms-and-math.md",
    "fund-game-architecture": "game-architecture-and-ai.md",
    "fund-rendering-physics": "rendering-physics-animation.md",
    "fund-netcode": "multiplayer-netcode.md",
    "fund-software-engineering": "software-engineering.md",
    "fund-unfamiliar-codebase": "unfamiliar-codebase-playbook.md",
}
GK_SUITE = ROOT / "evals" / "general_knowledge" / "fundamentals-v1.prompts.json"
GK_ORACLES = ROOT / "evals" / "general_knowledge" / "fundamentals-v1.oracles.json"
LUAU_SUITE = ROOT / "evals" / "roblox" / "golden-tasks-fundamentals-v1.json"


# --- skill packs -------------------------------------------------------------------------------------

def test_fundamentals_packs_ship_with_sources_and_the_long_form_notes():
    by_name = {p.name: p for p in skill_packs.available()}
    assert set(PACKS) <= set(by_name) and set(PACKS) == set(skill_packs.GENERAL_PACKS)
    for name, doc in PACKS.items():
        pack = by_name[name]
        assert pack.body.startswith("# ") and len(pack.body) <= skill_packs.MAX_BODY_CHARS
        refs = pack.file.parent / "references"
        sources = (refs / "sources.md").read_text(encoding="utf-8")
        assert sources.count("https://") >= 5 and doc in sources, name
        # The shipped copy must not drift from the research note it was distilled from.
        assert (refs / "notes.md").read_text(encoding="utf-8") == (DOCS / doc).read_text(encoding="utf-8"), name


def test_every_research_note_lists_sources():
    for doc in [*PACKS.values(), "README.md"]:
        text = (DOCS / doc).read_text(encoding="utf-8")
        if doc != "README.md":
            assert "## Sources" in text and text.split("## Sources", 1)[1].count("https://") >= 5, doc


def test_fundamentals_packs_are_off_until_the_gate_has_passed_them():
    assert not set(PACKS) & set(skill_packs.DEFAULT_ENABLED)
    assert skill_packs.select("How do I implement A* pathfinding on a grid in C#?") == []


@pytest.mark.parametrize("prompt, expected", [
    ("How do I implement A* pathfinding on a grid in C#?", "fund-game-architecture"),
    ("Should my game loop use a fixed timestep with an accumulator?", "fund-game-architecture"),
    ("Explain client-side prediction and server reconciliation for my multiplayer shooter", "fund-netcode"),
    ("What is the time complexity of a binary heap push?", "fund-algorithms"),
    ("Why does slerp between my quaternions spin the long way round?", "fund-algorithms"),
    ("Should I use deferred rendering or clustered forward shading?", "fund-rendering-physics"),
    ("How do I prevent SQL injection in my Node API?", "fund-software-engineering"),
    ("I'm new to this codebase, where do I start?", "fund-unfamiliar-codebase"),
    ("In my Roblox game, how do I do lag compensation for hitscan guns?", "fund-netcode"),
])
def test_general_packs_are_chosen_for_engine_independent_questions(prompt, expected):
    assert skill_packs.matching_names(prompt, enabled=list(PACKS)) == [expected]


def test_general_packs_do_not_fire_for_unrelated_prompts_and_roblox_packs_still_need_roblox():
    every = [p.name for p in skill_packs.available()]
    for prompt in ("What is the capital of France?", "hello", "How do I centre a div in my web app UI?",
                   "Explain the UI of a spreadsheet", "I sat down to rest", ""):
        assert skill_packs.select(prompt, enabled=every) == [], prompt
    # A non-Roblox prompt that names a Roblox pack's topic still gets nothing from the Roblox packs.
    assert skill_packs.matching_names("My web form must validate input and never trust the client", enabled=["roblox-secure-remotes"]) == []


def test_in_a_roblox_question_the_roblox_pack_wins_over_a_general_one():
    every = [p.name for p in skill_packs.available()]
    prompt = ("In my Roblox game my RemoteEvent handler trusts the client. How do I validate input, add rate limits "
              "and stop injection exploits, and which OWASP rules apply?")
    assert skill_packs.matching_names(prompt, enabled=every) == ["roblox-secure-remotes"]
    assert skill_packs.matching_names(prompt, enabled=["fund-software-engineering"]) == ["fund-software-engineering"]


# --- general JSON suite: every oracle is recomputed here, independently of the oracle file ----------

def _fixed_steps(step, cap, frames):
    acc, total = 0, 0
    for frame in frames:
        acc += min(frame, cap)
        while acc >= step:
            acc -= step
            total += 1
    return total, acc


def _astar(edges, h, start, goal):
    graph = {}
    for a, b, w in edges:
        graph.setdefault(a, []).append((b, w))
        graph.setdefault(b, []).append((a, w))
    g, came, heap, closed = {start: 0}, {}, [(h[start], start)], set()
    while heap:
        _, node = heapq.heappop(heap)
        if node in closed:
            continue
        if node == goal:
            path = [node]
            while path[-1] in came:
                path.append(came[path[-1]])
            return path[::-1], g[node]
        closed.add(node)
        for nxt, w in graph[node]:
            if g[node] + w < g.get(nxt, math.inf):
                g[nxt], came[nxt] = g[node] + w, node
                heapq.heappush(heap, (g[nxt] + h[nxt], nxt))
    return None, None


def _qmul(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return (w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2)


def _axis_angle(axis, angle):
    s = math.sin(angle / 2)
    return (math.cos(angle / 2), axis[0] * s, axis[1] * s, axis[2] * s)


def _bt(tree, results, ran):
    kind = tree[0]
    if kind in ("action", "condition"):
        if kind == "action":
            ran.append(tree[1])
        return results[tree[1]]
    for child in tree[1]:
        status = _bt(child, results, ran)
        if kind == "sequence" and status != "Success":
            return status
        if kind == "selector" and status != "Failure":
            return status
    return "Success" if kind == "sequence" else "Failure"


def _kahn(after):
    nodes = set(after) | {d for deps in after.values() for d in deps}
    indeg = {n: len(after.get(n, ())) for n in nodes}
    order, ready = [], sorted(n for n in nodes if indeg[n] == 0)
    while ready:
        n = ready.pop(0)
        order.append(n)
        for m, deps in after.items():
            if n in deps:
                indeg[m] -= 1
                if indeg[m] == 0:
                    ready = sorted(ready + [m])
    return order


def recomputed():
    total, rest = _fixed_steps(16, 50, [40, 10, 30, 120])
    path, cost = _astar([("S", "A", 1), ("S", "B", 4), ("A", "B", 2), ("A", "C", 5), ("B", "C", 1), ("B", "D", 5),
                         ("C", "G", 3), ("D", "G", 1)], {"S": 6, "A": 5, "B": 4, "C": 3, "D": 1, "G": 0}, "S", "G")
    q = _qmul(_axis_angle((1, 0, 0), math.pi / 2), _axis_angle((0, 0, 1), math.pi / 2))
    v = _qmul(_qmul(q, (0, 1, 0, 0)), (q[0], -q[1], -q[2], -q[3]))
    moves = [1, 1, 2, 2, -1, 3, 3, 1]
    ran = []
    status = _bt(("selector", [("sequence", [("condition", "EnemyVisible"), ("action", "Attack")]),
                               ("sequence", [("condition", "LowHealth"), ("action", "FindCover"), ("action", "Heal")]),
                               ("action", "Patrol")]),
                 {"EnemyVisible": "Failure", "Attack": "Success", "LowHealth": "Success", "FindCover": "Failure",
                  "Heal": "Success", "Patrol": "Success"}, ran)
    counter = 10
    a = counter            # A reads
    b = counter            # B reads
    counter = a + 5        # A writes
    counter = b + 3        # B writes
    a = counter            # A reads
    counter = a + 1        # A writes
    return {
        "GF-01": {"total_steps": total, "final_accumulator_ms": rest},
        "GF-02": {"max_probes": math.floor(math.log2(1_000_000)) + 1},
        "GF-03": {"path": path, "cost": cost},
        "GF-04": {"x": round(v[1]), "y": round(v[2]), "z": round(v[3])},
        "GF-05": {"reconciled_x": 4 + sum(moves[5:]), "inputs_replayed": len(moves[5:])},
        "GF-06": {"rewind_to_tick": 5000 - (120 // 2 + 100) // (1000 // 50)},
        "GF-07": {"root_status": status, "actions_run": ran},
        "GF-08": {"final_value": counter, "lost_increment": (10 + 5 + 3 + 1) - counter},
        "GF-09": {"vulnerable": ["S1", "S3", "S5"]},   # reviewed by hand: concatenation, raw identifier, % formatting
        "GF-10": {"order": _kahn({"Physics": {"Input"}, "Animation": {"Physics"}, "AI": {"Input"},
                                  "Render": {"Animation", "AI"}, "Audio": {"AI"}})},
    }


def test_general_suite_loads_with_the_existing_loader_and_every_oracle_is_recomputed():
    suite = bench.load_suite(GK_SUITE)
    oracles = bench.load_oracles(suite, GK_ORACLES)
    assert suite.data["suite_id"] == "star-fundamentals-development-v1"
    expected = {k: v["expected"] for k, v in oracles.data["cases"].items()}
    assert expected == recomputed()


def test_general_suite_scores_the_oracle_answers_as_passing_and_a_wrong_answer_as_incorrect():
    suite = bench.load_suite(GK_SUITE)
    oracles = bench.load_oracles(suite, GK_ORACLES)
    plan = bench.prepare(suite, 1)
    rows = []
    for request in plan["requests"]:
        answer = dict(oracles.data["cases"][request["task_id"]]["expected"])
        if request["task_id"] == "GF-03":
            answer["cost"] = 8
        response = json.dumps(answer)
        rows.append({"task_id": request["task_id"], "attempt": 1, "request_sha256": request["request_sha256"],
                     "response": response, "response_sha256": bench.digest(response.encode("utf-8")),
                     "outcome": "completed", "error_code": None})
    run = {"schema_version": 1, "kind": "general_foundation_raw_run", "suite_id": suite.data["suite_id"],
           "suite_sha256": suite.sha256, "oracle_sha256": oracles.sha256, "grader_sha256": bench.grader_digest(),
           "identity": {"app_commit": "a" * 40, "source_sha256": "a" * 64, "request_builder_sha256": "d" * 64,
                        "adapter_sha256": "e" * 64, "backend_build": "fixture-build",
                        "model": {"model_id": "fixture", "revision": "r", "weights_sha256": "b" * 64,
                                  "tokenizer_sha256": "c" * 64, "quantization": "q4"},
                        "mode": "direct_text", "options": {"temperature": 0, "top_p": 1, "max_output_tokens": 128,
                                                           "seed": None, "stop": [], "tools": []}},
           "repeats": 1, "rows": rows}
    report = bench.score_run(suite, oracles, run)
    assert report["counts"] == {"pass": 9, "incorrect": 1}


def test_general_suite_prompts_never_contain_the_answers():
    suite = json.loads(GK_SUITE.read_text(encoding="utf-8"))
    assert "expected" not in json.dumps(suite) and "derivation" not in json.dumps(suite)


# --- pure-Luau golden suite ---------------------------------------------------------------------------

def test_luau_suite_loads_and_every_task_has_harness_files():
    suite = eval_runner.load_suite(LUAU_SUITE)
    assert [t["id"] for t in suite.tasks] == [f"FND-0{i}" for i in range(1, 8)]
    for task in suite.tasks:
        body = suite.test_body(task)
        assert task["auto"]["unit_test"]["checks"] == len(re.findall(r"^\s*check\(", body, re.M)), task["id"]
        for kind in ("", ".bad"):
            answer = (suite.directory / "reference" / f"{task['id']}{kind}.md").read_text(encoding="utf-8")
            assert answer.lstrip().startswith("```luau\n--!strict"), (task["id"], kind)


def test_luau_suite_ids_do_not_collide_with_the_other_suites():
    ours = {t["id"] for t in json.loads(LUAU_SUITE.read_text(encoding="utf-8"))}
    for other in (ROOT / "evals" / "roblox").glob("*.json"):
        if other != LUAU_SUITE:
            assert not ours & {t["id"] for t in json.loads(other.read_text(encoding="utf-8"))}, other.name


def test_each_luau_task_routes_to_the_pack_it_is_meant_to_help():
    for task in json.loads(LUAU_SUITE.read_text(encoding="utf-8")):
        assert skill_packs.matching_names(task["prompt"], enabled=task["helps"]) == task["helps"], task["id"]
