"""Other-engine skill packs (star/skill_packs/engines.py) and their offline golden tasks (evals/engines/)."""
import json
from pathlib import Path
import re

import pytest

from star import eval_checks, skill_packs
from star.skill_packs import engines

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "evals" / "engines" / "golden-tasks-other-engines-v1.json"
RESEARCH = ROOT / "docs" / "research" / "engines"
ENGINE_NAMES = sorted(engines.ENGINE_CONTEXTS)
FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.S)
FORBIDDEN_IN_BODY = ("http://", "https://", "ignore previous", "system prompt", "api key", "execute_luau", "publish")


def by_name():
    return {p.name: p for p in skill_packs.available()}


def test_every_engine_pack_ships_with_contexts_topics_and_research():
    assert len(ENGINE_NAMES) >= 25
    assert set(engines.ENGINE_CONTEXTS) == set(engines.ENGINE_TOPICS)
    packs = by_name()
    for name in ENGINE_NAMES:
        assert name.startswith("engine-") and name in packs, name
        pack = packs[name]
        assert pack.body.startswith("# " + name)
        assert len(pack.body) <= 4600, (name, len(pack.body))
        lowered = pack.body.lower()
        for word in FORBIDDEN_IN_BODY:
            assert word not in lowered, (name, word)
        sources = (pack.file.parent / "references" / "sources.md").read_text(encoding="utf-8")
        assert sources.count("https://") >= 4 and "http://" not in sources, name
    assert (RESEARCH / "OTHER_ENGINES_INDEX.md").is_file()


def test_engine_packs_are_off_by_default_and_the_engines_shorthand_turns_them_on():
    assert set(ENGINE_NAMES).isdisjoint(skill_packs.DEFAULT_ENABLED)
    assert set(ENGINE_NAMES).isdisjoint(skill_packs.enabled_names({}))
    on = skill_packs.enabled_names({skill_packs.ENV_VAR: "engines"})
    assert set(ENGINE_NAMES) <= on and set(skill_packs.DEFAULT_ENABLED) <= on
    assert skill_packs.enabled_names({skill_packs.ENV_VAR: "engine-bevy"}) == {"engine-bevy"}


def roblox_prompts():
    prompts = []
    for path in sorted((ROOT / "evals" / "roblox").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        tasks = data if isinstance(data, list) else data.get("tasks", [])
        prompts += [t["prompt"] for t in tasks if isinstance(t, dict) and isinstance(t.get("prompt"), str)]
    return prompts


def test_no_engine_context_fires_on_roblox_or_ordinary_prompts():
    prompts = roblox_prompts() + [
        "What is the capital of France?", "I love this game, can you make the UI nicer?", "hello",
        "Explain the core idea of recursion", "How do I construct a binary tree in Python?",
        "Write a script that heaps numbers into a priority queue", "Make the source code faster",
        "Add a phaser sound effect to my sci-fi menu", "In my Roblox game: build a ScreenGui shop",
    ]
    assert len(prompts) > 50
    for prompt in prompts:
        hits = [name for name, ctx in engines.ENGINE_CONTEXTS.items() if ctx.search(prompt)]
        assert hits == [], (prompt[:80], hits)
    for prompt in prompts:
        assert all(p.name not in engines.ENGINE_CONTEXTS for p in skill_packs.select(prompt, enabled=set(ENGINE_NAMES)))


def suite():
    return json.loads(SUITE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ENGINE_NAMES)
def test_each_engine_has_golden_tasks_whose_prompt_routes_to_its_pack(name):
    tasks = [t for t in suite() if t["category"] == name]
    assert len(tasks) >= 2, name
    for task in tasks:
        picked = skill_packs.matching_names(task["prompt"], enabled=set(ENGINE_NAMES))
        assert picked == [name], (task["id"], picked)
        # Roblox packs and the default set never claim another engine's prompt on their own.
        assert all(n not in engines.ENGINE_CONTEXTS for n in skill_packs.matching_names(task["prompt"]))


def checks(task, answer):
    blocks = FENCE.findall(answer)
    return eval_checks.pattern_checks(task["auto"], blocks, answer)


def test_golden_tasks_schema_and_reference_pairs():
    tasks = suite()
    ids = [t["id"] for t in tasks]
    assert len(ids) == len(set(ids)) >= 50
    packs = by_name()
    for task in tasks:
        assert task["id"].startswith("OE-") and task["category"] in packs and task["helps"] == [task["category"]]
        assert task["run_mode"] == "automated" and task["split"] == "development"
        assert task["auto"]["require"] and task["auto"]["forbid"], task["id"]
        assert FENCE.search(task["reference_answer"]) and FENCE.search(task["bad_answer"]), task["id"]
        good = checks(task, task["reference_answer"])
        assert all(c.ok for c in good), (task["id"], [c for c in good if not c.ok])
        assert any(not c.ok for c in checks(task, task["bad_answer"])), task["id"]
        assert any(not c.ok for c in checks(task, "")), task["id"]


def test_a_named_engine_outranks_roblox_packs_when_both_are_enabled():
    prompt = "Port my Roblox RemoteEvent OnServerEvent FireServer validation to Bevy 0.17 with Commands and Query."
    assert skill_packs.matching_names(prompt, enabled={"engine-bevy", "roblox-secure-remotes"}) == ["engine-bevy"]
    assert skill_packs.matching_names(prompt, enabled={"roblox-secure-remotes"}) == ["roblox-secure-remotes"]
