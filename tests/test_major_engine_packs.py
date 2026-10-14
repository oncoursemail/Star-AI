"""Unity, Unreal Engine 5 and Godot 4 packs: routing, opt-in, grounding, and their prose-checked golden suites.

Offline: no model, server, editor or network. References are scored with the same graders the runner uses.
"""
import json
from pathlib import Path

import pytest

from star import eval_checks, skill_packs
from star.agent_skills import SkillLibrary
from star.eval_runner import load_suite

ROOT = Path(__file__).resolve().parents[1]
ENGINE_PACKS = {
    "godot": ("godot-migration-and-pitfalls", "godot-multiplayer-data", "godot-rendering-performance"),
    "unity": ("unity-scripting-core", "unity-netcode-data", "unity-rendering-performance"),
    "unreal": ("unreal-cpp-gameplay", "unreal-replication-gas", "unreal-rendering-performance"),
}
ALL = {name for names in ENGINE_PACKS.values() for name in names}
SUITES = {engine: ROOT / "evals" / engine / "golden-tasks-diagnosis-v1.json" for engine in ENGINE_PACKS}
ROBLOX_SUITES = sorted((ROOT / "evals" / "roblox").glob("*.json"))

ROUTES = (
    ("unity-scripting-core", "In my Unity 6 game the Rigidbody jitters in Update and OnTriggerEnter never fires"),
    ("unity-netcode-data", "In my Unity game a client writes a NetworkVariable and it never syncs; how do I use Rpc?"),
    ("unity-rendering-performance", "Unity URP game has low FPS, how do I use the Profiler and SRP Batcher?"),
    ("unreal-cpp-gameplay", "UE5 crash: my UObject pointer without UPROPERTY gets garbage collected"),
    ("unreal-replication-gas", "In Unreal Engine 5 my Server RPC never runs, is it ownership? replication is on"),
    ("unreal-rendering-performance", "Unreal Engine 5 Lumen light leaks and shader compilation stutter in a packaged build"),
    ("godot-migration-and-pitfalls", "In Godot 4 my Godot 3 yield and KinematicBody code fails"),
    ("godot-multiplayer-data", "Godot 4 multiplayer: rpc any_peer from client to server with a MultiplayerSpawner"),
    ("godot-rendering-performance", "Godot 4 performance: low FPS, should I use MultiMesh and the profiler?"),
)


def test_engine_packs_ship_registered_and_grouped_by_engine():
    shipped = {p.name for p in skill_packs.available()}
    assert ALL <= shipped
    assert set(ENGINE_PACKS["godot"]) <= skill_packs.GODOT_PACKS
    assert set(ENGINE_PACKS["unity"]) == skill_packs.UNITY_PACKS
    assert set(ENGINE_PACKS["unreal"]) == skill_packs.UNREAL_PACKS


def test_engine_packs_are_off_until_the_gate_passes_them():
    assert ALL.isdisjoint(skill_packs.DEFAULT_ENABLED)
    assert ALL.isdisjoint(skill_packs.enabled_names({}))
    assert ALL <= skill_packs.enabled_names({skill_packs.ENV_VAR: "all"})


@pytest.mark.parametrize(("name", "prompt"), ROUTES)
def test_each_pack_routes_only_after_opt_in(name, prompt):
    assert skill_packs.matching_names(prompt) == [] or name not in skill_packs.matching_names(prompt)
    assert skill_packs.matching_names(prompt, enabled=ALL) == [name]
    assert skill_packs.matching_names(prompt, enabled={name}) == [name]


def test_engine_packs_never_fire_for_roblox_or_unrelated_prompts():
    for prompt in ("In my Roblox game: RemoteEvent handler trusts the client price; validate it on the server.",
                   "In Roblox Studio my ScreenGui UIListLayout has bad performance", "What is the capital of France?",
                   "Explain garbage collection in Java", "My Python server has lag and low FPS"):
        assert not set(skill_packs.matching_names(prompt, enabled=set(skill_packs.TRIGGERS))) & ALL, prompt


def test_a_roblox_developer_asking_about_another_engine_gets_that_engine():
    prompt = "I know Roblox. What is the Unity equivalent of a RemoteEvent for multiplayer?"
    assert skill_packs.matching_names(prompt, enabled=set(skill_packs.TRIGGERS)) == ["unity-netcode-data"]


def test_roblox_suite_requests_are_unchanged_by_the_engine_packs():
    # Every Roblox golden task routes exactly as before: engine packs cannot reach these prompts.
    for path in ROBLOX_SUITES:
        if path.name.endswith(".sha256"):
            continue
        tasks = json.loads(path.read_text(encoding="utf-8"))
        for task in tasks if isinstance(tasks, list) else []:
            assert not set(skill_packs.matching_names(task.get("prompt", ""), enabled=set(skill_packs.TRIGGERS))) & ALL, task["id"]


def test_engine_pack_bodies_stay_short_and_within_bounds():
    for pack in skill_packs.available():
        if pack.name in ALL:
            assert pack.body.startswith("# ") and len(pack.body) <= 3600, (pack.name, len(pack.body))
            assert len(skill_packs.render([pack])) <= skill_packs.MAX_BLOCK_CHARS
            sources = (pack.file.parent / "references" / "sources.md").read_text(encoding="utf-8")
            assert "2026-10-13" in sources and "own words" in sources, pack.name


def test_engine_packs_are_loadable_on_demand_from_the_skill_library(tmp_path):
    lib = SkillLibrary(workspace=None, home=tmp_path, bundled=skill_packs.PACKS_DIR)
    names = {s.name for s in lib.catalog()}
    assert ALL <= names
    loaded = lib.load("unreal-replication-gas")
    assert "references/sources.md" in loaded["references"]


def test_deep_references_exist_for_each_engine():
    for engine in ENGINE_PACKS:
        text = (ROOT / "docs" / "research" / "engines" / f"{engine}.md").read_text(encoding="utf-8")
        assert len(text.splitlines()) >= 500, engine
        assert "Roblox" in text and "## " in text and text.count("https://") >= 30, engine


@pytest.mark.parametrize("engine", sorted(SUITES))
def test_engine_golden_suites_load_and_their_references_score_as_intended(engine):
    suite = load_suite(SUITES[engine])
    assert len(suite.tasks) == 6
    reference = SUITES[engine].parent / "reference"
    for task in suite.runnable():
        auto = task["auto"]
        assert auto["code"] is False and all(item["scope"] == "prose" for item in auto["require"])
        assert set(task["helps"]) <= set(ENGINE_PACKS[engine])
        # the pack the task is meant to help is the one STAR would choose for its prompt
        assert skill_packs.matching_names(task["prompt"], enabled=ALL) == task["helps"][:1], task["id"]
        good = eval_checks.score_answer(task, (reference / f"{task['id']}.md").read_text(encoding="utf-8"), luau_check=None)
        bad = eval_checks.score_answer(task, (reference / f"{task['id']}.bad.md").read_text(encoding="utf-8"), luau_check=None)
        assert good.passed, (task["id"], good.reasons)
        assert not bad.passed, task["id"]
        assert not eval_checks.score_answer(task, "", luau_check=None).passed
    splits = {t["split"] for t in suite.tasks}
    assert splits == {"development", "holdout"}
