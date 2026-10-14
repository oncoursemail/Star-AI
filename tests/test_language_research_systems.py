"""Systems-language research: docs, catalog-only skill packs, routing data and the prose-graded golden suite."""
import json
import re
from pathlib import Path

import pytest

from star import eval_checks, skill_packs
from star.agent_skills import SkillLibrary, _frontmatter
from star.eval_runner import load_suite
from star.skill_packs import systems_languages

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "research" / "languages"
SUITE = ROOT / "evals" / "languages" / "golden-tasks-systems-v1.json"
LANGS = {"c": "lang-c", "cpp": "lang-cpp", "rust": "lang-rust", "zig": "lang-zig", "go": "lang-go",
         "csharp": "lang-csharp", "java": "lang-java", "kotlin": "lang-kotlin", "swift": "lang-swift"}
PACKS = sorted(LANGS.values())
SECTIONS = ["## 0. Current version", "## 1. Mental model", "## 2. Type system", "## 3. Memory model",
            "## 4. Concurrency", "## 5. Error handling", "## 6. Toolchain", "## 7. Testing", "## 8. Idiomatic patterns",
            "## 9. Top 30 pitfalls", "## 10. Performance", "## 11. Security", "## 12. Game-development usage",
            "## 13. Cheat sheet", "## 14. Sources"]
ID_PREFIX = {"C": "lang-c", "CPP": "lang-cpp", "RS": "lang-rust", "ZIG": "lang-zig", "GO": "lang-go",
             "CS": "lang-csharp", "JAVA": "lang-java", "KT": "lang-kotlin", "SWIFT": "lang-swift"}


@pytest.mark.parametrize("lang", sorted(LANGS))
def test_each_language_doc_has_every_section_30_pitfalls_and_sources(lang):
    text = (DOCS / f"{lang}.md").read_text(encoding="utf-8")
    positions = [text.find(s) for s in SECTIONS]
    assert all(p >= 0 for p in positions) and positions == sorted(positions), lang
    pitfalls = text[text.find("## 9."):text.find("## 10.")]
    assert len(re.findall(r"(?m)^\d+\. ", pitfalls)) >= 30, lang
    sources = text[text.find("## 14. Sources"):]
    assert len(set(re.findall(r"https://\S+", sources))) >= 20, lang
    assert "http://" not in text
    cheat = text[text.find("## 13."):text.find("## 14.")]
    assert cheat.count("\n|") >= 27, lang          # header + separator + at least 25 rows


def test_the_brief_file_covers_odin_nim_carbon_and_mojo_with_sources():
    text = (DOCS / "odin-nim-carbon-mojo.md").read_text(encoding="utf-8")
    for name in ("## Odin", "## Nim", "## Carbon", "## Mojo", "## Sources"):
        assert name in text
    assert len(re.findall(r"https://\S+", text)) >= 10


@pytest.mark.parametrize("name", PACKS)
def test_packs_use_the_skill_format_and_stay_short_and_inert(name):
    folder = skill_packs.PACKS_DIR / name
    fields, body = _frontmatter((folder / "SKILL.md").read_text(encoding="utf-8"))
    body = body.strip()
    assert fields["name"] == name and 1 <= len(fields["description"]) <= 1024
    assert body.startswith("# ") and 1400 <= len(body) <= skill_packs.MAX_BODY_CHARS
    for forbidden in ("ignore previous", "system prompt", "api key", "http://", "https://", "execute_luau", "publish"):
        assert forbidden not in body.lower(), (name, forbidden)
    sources = (folder / "references" / "sources.md").read_text(encoding="utf-8")
    assert sources.startswith(f"# Sources for {name}") and len(re.findall(r"https://", sources)) >= 6
    assert "http://" not in sources


def test_packs_are_catalog_only_and_never_change_automatic_selection():
    assert not set(PACKS) & set(skill_packs.TRIGGERS)
    assert not set(PACKS) & set(skill_packs.DEFAULT_ENABLED)
    assert not set(PACKS) & {p.name for p in skill_packs.available()}
    assert skill_packs.select("In Rust, fix error E0502 in my Vec code", enabled=None) == []


def test_the_skill_library_lists_and_loads_the_bundled_language_packs(tmp_path):
    lib = SkillLibrary(workspace=None, home=tmp_path, bundled=skill_packs.PACKS_DIR)
    by_name = {s.name: s for s in lib.catalog()}
    assert set(PACKS) <= set(by_name)
    loaded = lib.load("lang-rust")
    assert "E0502" in loaded["instructions"] and "references/sources.md" in loaded["references"]


@pytest.mark.parametrize(("prompt", "expected"), (
    ("Why does my C program crash after realloc returns NULL?", "lang-c"),
    ("C23 nullptr vs NULL in gcc", "lang-c"),
    ("My C++ std::vector erase loop crashes", "lang-cpp"),
    ("rustc says E0499 when I borrow twice", "lang-rust"),
    ("How do I use build.zig with Zig 0.17?", "lang-zig"),
    ("goroutines leak in my golang service", "lang-go"),
    ("C# async method deadlocks in Unity MonoBehaviour", "lang-csharp"),
    ("Java ConcurrentModificationException in a for-each loop", "lang-java"),
    ("Kotlin coroutine never cancels", "lang-kotlin"),
    ("SwiftUI view leaks because of a closure", "lang-swift"),
))
def test_language_contexts_recognise_the_language(prompt, expected):
    assert systems_languages.languages_named(prompt)[0] == expected


@pytest.mark.parametrize("prompt", (
    "Go ahead and add a coin pickup to my Roblox game",
    "In my Roblox game: write a LocalScript that builds a ScreenGui with a ScrollingFrame.",
    "Plan C is to rebuild the lobby in Studio",
    "Write a JavaScript function that sorts scores",
    "What is the capital of France?", "", "   ",
))
def test_language_contexts_ignore_unrelated_and_roblox_prompts(prompt):
    assert systems_languages.languages_named(prompt) == []


def test_the_suite_loads_and_every_task_targets_one_pack_with_a_holdout_per_language():
    suite = load_suite(SUITE)
    tasks = suite.runnable()
    assert len(tasks) == len(suite.tasks) >= 18
    per_pack = {}
    for task in tasks:
        pack = ID_PREFIX[task["id"].rsplit("-", 1)[0]]
        assert task["helps"] == [pack]
        assert task["auto"]["code"] is False
        assert all(item["scope"] == "prose" for key in ("require", "forbid") for item in task["auto"].get(key, []))
        assert systems_languages.languages_named(task["prompt"])[:1] == [pack], task["id"]
        per_pack.setdefault(pack, []).append(task["split"])
    assert set(per_pack) == set(PACKS)
    for pack, splits in per_pack.items():
        assert len(splits) >= 2 and splits.count("holdout") == 1, pack


def test_task_ids_do_not_collide_with_other_suites():
    ours = {t["id"] for t in json.loads(SUITE.read_text(encoding="utf-8"))}
    for other in (ROOT / "evals").rglob("*.json"):
        if other == SUITE:
            continue
        try:
            data = json.loads(other.read_text(encoding="utf-8"))
        except (UnicodeError, ValueError):
            continue
        if isinstance(data, list):
            assert not ours & {t.get("id") for t in data if isinstance(t, dict)}, other


def test_reference_answers_pass_bad_answers_fail_and_empty_answers_fail():
    suite = load_suite(SUITE)
    ref = SUITE.parent / "reference"

    def no_luau(*_args, **_kwargs):
        raise AssertionError("prose-graded tasks must not call the Luau checker")

    for task in suite.runnable():
        good = eval_checks.score_answer(task, (ref / f"{task['id']}.md").read_text(encoding="utf-8"), luau_check=no_luau)
        bad = eval_checks.score_answer(task, (ref / f"{task['id']}.bad.md").read_text(encoding="utf-8"), luau_check=no_luau)
        assert good.passed, (task["id"], good.reasons)
        assert not bad.passed, task["id"]
        assert not eval_checks.score_answer(task, "", luau_check=no_luau).passed, task["id"]
