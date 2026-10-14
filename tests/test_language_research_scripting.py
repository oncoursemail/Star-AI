"""Scripting, web, shader and data language research: research notes, catalog skill packs and the golden suite.

These packs are listed by the skill catalog (star_skill_catalog / SkillLibrary) but are NOT routed automatically:
they are absent from star.skill_packs.TRIGGERS, so no prompt changes until the evaluation gate has measured them.
"""
import json
from pathlib import Path
import re

import pytest

from star import eval_checks, eval_runner, skill_packs
from star.agent_skills import SkillLibrary, _frontmatter

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "research" / "languages"
SUITE = ROOT / "evals" / "languages" / "golden-tasks-scripting-v1.json"

LANGUAGE_DOCS = ["python", "javascript-typescript", "lua-luajit", "gdscript", "verse", "ruby", "php", "dart", "elixir",
                 "haskell-ocaml", "bash", "powershell", "sql", "html-css", "webassembly", "hlsl", "glsl", "wgsl", "slang"]
PACKS = ["lang-python", "lang-javascript-typescript", "lang-lua-luajit", "lang-gdscript-verse", "lang-ruby-php",
         "lang-dart-elixir-functional", "lang-shell", "lang-sql", "lang-web-html-css-wasm", "lang-shaders"]
SECTIONS = ["## 1. Mental model", "## 2.", "## 3.", "## 4.", "## 5.", "## 6.", "## 7.", "## 8.", "## 9.",
            "## 10.", "## 11.", "## 12.", "## Sources"]
FORBIDDEN_IN_BODY = ("ignore previous", "system prompt", "api key", "http://", "https://", "execute_luau", "publish")


@pytest.mark.parametrize("name", LANGUAGE_DOCS)
def test_each_language_has_a_sourced_research_note(name):
    text = (DOCS / f"{name}.md").read_text(encoding="utf-8")
    assert text.startswith("# ") and "2026-10-13" in text.split("\n", 1)[0], name
    at = -1
    for heading in SECTIONS:
        found = text.find(heading, at + 1)
        assert found > at, (name, heading)
        at = found
    sources = text[text.rfind("## Sources"):]
    assert len(set(re.findall(r"https://[^\s)>\]]+", sources))) >= 5, name
    assert "http://" not in sources
    assert "Luau" in text, name


def test_the_index_lists_every_note():
    index = (DOCS / "SCRIPTING_INDEX.md").read_text(encoding="utf-8")
    for name in LANGUAGE_DOCS:
        assert f"({name}.md)" in index, name


@pytest.mark.parametrize("name", PACKS)
def test_language_packs_use_the_skill_format_and_stay_small(name):
    folder = skill_packs.PACKS_DIR / name
    fields, body = _frontmatter((folder / "SKILL.md").read_text(encoding="utf-8"))
    assert fields.get("name") == name and 1 <= len(fields.get("description", "")) <= 1024
    body = body.strip()
    assert body.startswith("# ") and len(body) <= skill_packs.MAX_BODY_CHARS, (name, len(body))
    lowered = body.lower()
    for word in FORBIDDEN_IN_BODY:
        assert word not in lowered, (name, word)
    sources = (folder / "references" / "sources.md").read_text(encoding="utf-8")
    assert sources.count("https://") >= 6 and "http://" not in sources, name
    assert "Not verified with the STAR knowledge service" in sources, name
    pitfalls = folder / "references" / "pitfalls.md"
    assert pitfalls.is_file() and pitfalls.stat().st_size <= 24_000, name


def test_language_packs_are_in_the_catalog_but_never_routed_automatically(tmp_path):
    catalog = {s.name: s for s in SkillLibrary(workspace=None, home=tmp_path, bundled=skill_packs.PACKS_DIR).catalog()}
    assert set(PACKS) <= set(catalog)
    assert not set(PACKS) & set(skill_packs.TRIGGERS) and not set(PACKS) & set(skill_packs.DEFAULT_ENABLED)
    assert not set(PACKS) & {p.name for p in skill_packs.available()}
    lib = SkillLibrary(workspace=None, home=tmp_path, bundled=skill_packs.PACKS_DIR)
    loaded = lib.load("lang-python")
    assert "references/sources.md" in loaded["references"] and "references/pitfalls.md" in loaded["references"]


@pytest.fixture(scope="module")
def suite():
    return eval_runner.load_suite(SUITE)


def _no_luau_check(*_args, **_kwargs):
    raise AssertionError("language tasks are graded on prose only")


def test_the_language_suite_loads_and_every_task_is_prose_graded(suite):
    assert len(suite.tasks) >= 30
    prefixes = {t["id"].split("-")[0] for t in suite.tasks}
    assert {"PY", "JS", "LUA", "GD", "VRS", "RB", "PHP", "DART", "EX", "HS", "SH", "PS", "SQL", "WEB", "WASM",
            "HLSL", "GLSL", "WGSL", "SLANG"} <= prefixes
    for task in suite.tasks:
        auto = task["auto"]
        assert task["run_mode"] == "automated" and auto["code"] is False and auto["compile"] is False, task["id"]
        assert auto.get("require"), task["id"]
        assert all(item.get("scope") == "prose" for item in auto.get("require", []) + auto.get("forbid", [])), task["id"]
        assert set(task["helps"]) <= set(PACKS), task["id"]
        assert task["split"] == "development" and task["expected_sources"], task["id"]
        assert all(s.startswith("https://") for s in task["expected_sources"]), task["id"]


def test_reference_answers_pass_bad_answers_fail_and_empty_answers_fail(suite):
    ref = SUITE.parent / "reference"
    for task in suite.tasks:
        good = eval_checks.score_answer(task, (ref / f"{task['id']}.md").read_text(encoding="utf-8"),
                                        luau_check=_no_luau_check)
        assert good.passed, (task["id"], good.reasons)
        bad = eval_checks.score_answer(task, (ref / f"{task['id']}.bad.md").read_text(encoding="utf-8"),
                                       luau_check=_no_luau_check)
        assert not bad.passed, task["id"]
        assert not eval_checks.score_answer(task, "", luau_check=_no_luau_check).passed, task["id"]


def test_selftest_of_the_runner_agrees(suite):
    scorer = lambda task, answer: eval_checks.score_answer(task, answer, luau_check=_no_luau_check)  # noqa: E731
    assert eval_runner.selftest(suite, scorer, log=lambda m: None) == 0


def test_no_reference_file_is_orphaned(suite):
    ids = {t["id"] for t in suite.tasks}
    for file in (SUITE.parent / "reference").glob("*.md"):
        assert file.name.split(".")[0] in ids, file.name
    raw = SUITE.read_text(encoding="utf-8")
    assert not eval_runner._PRIVATE_IP.search(raw)
    json.loads(raw)
